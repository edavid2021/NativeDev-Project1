import os
import logging
import json
import datetime
import base64
import requests
import uuid
from io import BytesIO
from flask import Flask, request, redirect, render_template, jsonify, send_file
from werkzeug.utils import secure_filename
from google.cloud import storage, datastore
from dotenv import load_dotenv
from storage import delete_file, get_signed_url

# Load environment variables
load_dotenv()
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./cloudEnv.json"

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET")

# Google Cloud clients
storage_client = storage.Client()
datastore_client = datastore.Client()
bucket_name = "jpeg-hw"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Extract blob name from URL
def get_blob_name_from_url(url):
    if f"{bucket_name}/" in url:
        return url.split(f"{bucket_name}/")[1]
    return url

@app.route('/image/<blob_name>')
def serve_image(blob_name):
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        # Download image into memory
        image_bytes = blob.download_as_bytes()

        # Send the image file directly
        return send_file(
            BytesIO(image_bytes),
            mimetype=blob.content_type,
            download_name=blob_name
        )

    except Exception as e:
        logging.error(f"Error serving image: {e}")
        return "Image not found", 404

# Gemini metadata extraction
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
            title = text_response.split("Title:")[1].split("Description:")[0].strip()
            description = text_response.split("Description:")[1].strip()
        else:
            lines = text_response.strip().split('\n')
            title = lines[0]
            description = ' '.join(lines[1:]) if len(lines) > 1 else description

        return {"title": title, "description": description}
    except (KeyError, IndexError) as e:
        logging.error(f"Error extracting metadata: {e}")
        return {"title": "Untitled Image", "description": "No description available"}

# Home route — image gallery
@app.route('/')
def gallery():
    """Display all images with proxy URLs."""
    query = datastore_client.query(kind='images')
    images = list(query.fetch())

    return render_template('gallery.html', images=images)

# Upload page
@app.route('/upload', methods=['GET'])
def upload_page():
    return render_template('upload_image.html')

# Handle image upload
@app.route('/upload-image', methods=['POST'])
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

        # Extract metadata from Gemini
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
            'blob_name': unique_filename,
            'title': metadata["title"],
            'description': metadata["description"],
            'upload_date': datetime.datetime.now()
        })
        datastore_client.put(entity)

        return redirect('/')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Delete endpoint
@app.route('/delete-file', methods=['POST'])
def delete_file_endpoint():
    """Deletes an image and metadata from GCS and Datastore."""
    data = request.json
    file_name = data.get('file')

    if not file_name:
        return jsonify({"error": "File name is required"}), 400

    success = delete_file(file_name)
    
    if success:
        return jsonify({"message": f"Successfully deleted {file_name} and its metadata."}), 200
    else:
        return jsonify({"error": "Failed to delete file and metadata."}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)