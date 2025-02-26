import os
import logging
import json
import datetime
import base64
import requests
import uuid
from io import BytesIO
from flask import Flask, request, redirect, render_template, jsonify, url_for, session, flash
from werkzeug.utils import secure_filename
from google.cloud import storage, datastore
from dotenv import load_dotenv
from storage import delete_file, get_signed_url

# Load environment variables
load_dotenv()
# Set up Google Cloud Authentication
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./cloudEnv.json"

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET")  # Change this to a secure secret key

# Initialize Google Cloud clients
storage_client = storage.Client()
datastore_client = datastore.Client()
bucket_name = "jpeg-hw"

# Google Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Store securely

# Authentication Middleware
def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# Extracts blob name from URL
def get_blob_name_from_url(url):
    if f"{bucket_name}/" in url:
        return url.split(f"{bucket_name}/")[1]
    return url  # Return original if parsing fails

# Gemini API for Image Metadata Extraction
def get_image_metadata(image_data):
    encoded_image = base64.b64encode(image_data).decode('utf-8')

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    headers = {'Content-Type': 'application/json'}
    
    payload = {
        "contents": [{
            "parts": [
                {"text": "Provide a title (5-10 words) and description (1-2 sentences) for this image. Format: Title: [title] Description: [description]"},
                {"inline_data": {"mime_type": "image/jpeg", "data": encoded_image}}
            ]
        }]
    }
    
    params = {'key': GEMINI_API_KEY}
    response = requests.post(url, headers=headers, json=payload, params=params)
    result = response.json()

    try:
        text_response = result['candidates'][0]['content']['parts'][0]['text']
        title, description = "Untitled Image", "No description available"

        if "Title:" in text_response and "Description:" in text_response:
            title_part = text_response.split("Title:")[1].split("Description:")[0].strip()
            description_part = text_response.split("Description:")[1].strip()
            title, description = title_part, description_part
        else:
            lines = text_response.strip().split('\n')
            title, description = lines[0], ' '.join(lines[1:]) if len(lines) > 1 else description

        return {"title": title, "description": description}
    except (KeyError, IndexError) as e:
        logging.error(f"Error extracting metadata: {e}")
        return {"title": "Untitled Image", "description": "No description available"}

# Authentication Routes
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email, password = request.form.get('email'), request.form.get('password')

        # Check if email exists
        query = datastore_client.query(kind='users')
        query.add_filter('email', '=', email)
        if list(query.fetch(limit=1)):
            flash('Email already exists')
            return redirect(url_for('signup'))

        # Create user
        entity = datastore.Entity(datastore_client.key('users'))
        entity.update({'email': email, 'password': password})  # Use hashed passwords in production
        datastore_client.put(entity)

        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email, password = request.form.get('email'), request.form.get('password')

        # Validate user
        query = datastore_client.query(kind='users')
        query.add_filter('email', '=', email)
        query.add_filter('password', '=', password)
        if list(query.fetch(limit=1)):
            session['user_email'] = email
            return redirect(url_for('gallery'))

        flash('Invalid credentials')
        return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_email', None)
    return redirect(url_for('login'))

# Image Gallery
@app.route('/')
@login_required
def gallery():
    """Fetch user-specific images and signed URLs."""
    user_email = session['user_email']

    # Fetch all images (debugging)
    query = datastore_client.query(kind='images')
    all_images = list(query.fetch())
    logging.info(f"All images in Datastore: {all_images}")  # Debugging

    # Fetch only user-specific images
    query = datastore_client.query(kind='images')
    query.add_filter("useremail", "=", user_email)
    user_images = list(query.fetch())

    if not user_images:
        logging.warning(f"No images found for user: {user_email}")

    for image in user_images:
        blob_name = image.get('blob_name')
        if blob_name:
            signed_url = get_signed_url(user_email, blob_name)
            image['signed_url'] = signed_url
            logging.info(f"Signed URL for {blob_name}: {signed_url}")

    return render_template('gallery.html', images=user_images)
@app.route('/upload', methods=['GET'])
@login_required
def upload_page():
    return render_template('upload_image.html')

@app.route('/upload-image', methods=['POST'])
@login_required
def upload_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image part in the request"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        unique_filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        base_filename = os.path.splitext(unique_filename)[0]

        image_data = file.read()
        metadata = get_image_metadata(image_data)

        bucket = storage_client.bucket(bucket_name)

        # Upload image
        image_blob = bucket.blob(unique_filename)
        image_blob.upload_from_file(BytesIO(image_data), content_type=file.content_type)

        # Upload metadata JSON
        json_blob = bucket.blob(f"{base_filename}.json")
        json_blob.upload_from_string(json.dumps(metadata), content_type="application/json")

        # Store in Datastore
        entity = datastore.Entity(datastore_client.key('images'))
        entity.update({
            'useremail': session['user_email'],
            'blob_name': unique_filename,
            'title': metadata["title"],
            'description': metadata["description"],
            'upload_date': datetime.datetime.now()
        })
        datastore_client.put(entity)

        return redirect(url_for('gallery'))

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/delete-file', methods=['POST'])
@login_required
def delete_file_endpoint():
    """Deletes user-specific image and its metadata from GCP and removes it from Datastore."""
    data = request.json
    file_name = data.get('file')

    if not file_name:
        return jsonify({"error": "File name is required"}), 400

    user_email = session['user_email']
    success = delete_file(file_name, user_email)
    
    if success:
        return jsonify({"message": f"Successfully deleted {file_name} and its metadata."}), 200
    else:
        return jsonify({"error": "Failed to delete file and metadata."}), 500
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)