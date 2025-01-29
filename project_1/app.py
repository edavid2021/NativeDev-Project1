import os
import logging
from flask import Flask, request, redirect, render_template, jsonify
from storage import upload_file, get_list_of_files, delete_file  # Import storage functions

# Ensure the 'files' directory exists for temporary local storage
os.makedirs('files', exist_ok=True)

app = Flask(__name__)

# Define your GCP bucket name
GCP_BUCKET_NAME = "jpeg-hw"

@app.route('/')
def index():
    """Fetch the list of files from the GCP bucket and render them."""
    images = get_list_of_files(GCP_BUCKET_NAME)
    return render_template('index.html', images=images)

@app.route('/upload', methods=["POST"])
def upload():
    """Handles file upload and stores it in GCP."""
    uploaded_file = request.files.get('form_file')
    if not uploaded_file:
        return "No file uploaded.", 400  

    # Save the file temporarily
    temp_file_path = os.path.join("files", uploaded_file.filename)
    uploaded_file.save(temp_file_path)

    # Upload the file to GCP bucket
    try:
        upload_file(GCP_BUCKET_NAME, temp_file_path)
        logging.info(f"File uploaded: {uploaded_file.filename}")
    except Exception as e:
        return f"Error uploading to GCP bucket: {e}", 500
    finally:
        os.remove(temp_file_path)  # Clean up local temp file

    return redirect("/")

@app.route('/delete-file', methods=['POST'])
def delete_file_endpoint():
    """Deletes a file from GCP bucket."""
    data = request.json
    file_name = data.get('file')

    if not file_name:
        return jsonify({"error": "File name is required"}), 400

    success = delete_file(GCP_BUCKET_NAME, file_name)
    if success:
        return jsonify({"message": f"Deleted {file_name}"}), 200
    else:
        return jsonify({"error": "Failed to delete the file"}), 500

@app.route('/files')
def list_files():
    """Returns a JSON list of all files in the GCP bucket."""
    try:
        files = get_list_of_files(GCP_BUCKET_NAME)
        return jsonify(files)
    except Exception as e:
        return jsonify({"error": f"Error fetching files: {e}"}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)