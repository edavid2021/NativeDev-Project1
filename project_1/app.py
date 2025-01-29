from flask import Flask, render_template, request, redirect, url_for
from google.cloud import storage
import os

app = Flask(__name__)

# Configure Google Cloud Storage
BUCKET_NAME = "your-google-cloud-storage-bucket-name"

# Initialize Cloud Storage client
storage_client = storage.Client()

def upload_to_gcs(file, bucket_name):
    """Uploads a file to Google Cloud Storage."""
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file.filename)
    blob.upload_from_file(file)
    return blob.public_url

def list_gcs_files(bucket_name):
    """Lists all files in a Google Cloud Storage bucket."""
    bucket = storage_client.bucket(bucket_name)
    blobs = bucket.list_blobs()
    return [blob.public_url for blob in blobs]

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files["file"]
        if file:
            upload_to_gcs(file, BUCKET_NAME)
            return redirect(url_for("index"))
    files = list_gcs_files(BUCKET_NAME)
    return render_template("index.html", files=files)

if __name__ == "__main__":
    app.run(debug=True)