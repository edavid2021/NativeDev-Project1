import os
from flask import Flask, redirect, request, send_file, render_template, jsonify
from storage import upload_file, get_list_of_files  # Import storage.py functions

# Ensure the 'files' directory exists for temporary local storage
os.makedirs('files', exist_ok=True)

app = Flask(__name__)

# Define your GCP bucket name here
GCP_BUCKET_NAME = "your-gcp-bucket-name"

@app.route('/')
def index():
    # Fetch the list of files from the GCP bucket
    images = get_list_of_files(GCP_BUCKET_NAME)
    return render_template('index.html', images=images)

@app.route('/upload', methods=["POST"])
def upload():
    # Handle file upload
    uploaded_file = request.files.get('form_file')  # Get uploaded file
    if not uploaded_file:
        return "No file uploaded.", 400  # Handle case where no file is provided

    # Save the file temporarily in the 'files' directory
    temp_file_path = os.path.join("files", uploaded_file.filename)
    uploaded_file.save(temp_file_path)

    # Upload the file to the GCP bucket
    try:
        upload_file(GCP_BUCKET_NAME, temp_file_path)
    except Exception as e:
        return f"Error uploading to GCP bucket: {str(e)}", 500
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    # Redirect back to the index page
    return redirect("/")

@app.route('/files')
def list_files():
    # Fetch the list of files from the GCP bucket
    try:
        files = get_list_of_files(GCP_BUCKET_NAME)
    except Exception as e:
        return f"Error fetching files from GCP bucket: {str(e)}", 500

    return jsonify(files)  # Return the list as JSON for clarity

@app.route('/files/<filename>')
def get_file(filename):
    # Serve a specific file by downloading it from the GCP bucket
    temp_file_path = os.path.join("files", filename)
    try:
        # Download the file from the GCP bucket to the local temp directory
        from storage import download_file  # Import only when needed
        download_file(GCP_BUCKET_NAME, filename)
        return send_file(temp_file_path)
    except Exception as e:
        return f"Error fetching file from GCP bucket: {str(e)}", 500
    finally:
        # Clean up temporary file after serving
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

if __name__ == '__main__':
    # Development only: run "python app.py" and open http://localhost:8080
    app.run(host="localhost", port=8080, debug=True)