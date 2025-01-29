import os
import time
import logging
from datetime import datetime, timedelta
from google.cloud import datastore, storage

logging.basicConfig(level=logging.INFO)

datastore_client = datastore.Client()
storage_client = storage.Client()

# Datastore Operations
def list_db_entries():
    query = datastore_client.query(kind="photos")
    return list(query.fetch())

def add_db_entry(object):
    required_keys = {"name", "url", "user", "timestamp"}
    if not required_keys.issubset(object.keys()):
        raise ValueError(f"Missing required fields: {required_keys - object.keys()}")

    entity = datastore.Entity(key=datastore_client.key('photos'))
    entity.update(object)
    datastore_client.put(entity)

def fetch_db_entry(filters):
    query = datastore_client.query(kind='photos')
    for attr, value in filters.items():
        query.add_filter(attr, "=", value)
    return list(query.fetch())

# Cloud Storage Operations
def generate_signed_url(bucket_name, blob_name, expiration=3600): 
    """Generate a signed URL for accessing a private file."""
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expiration),  # URL valid for 1 hour
            method="GET"
        )
        return signed_url
    except Exception as e:
        logging.error(f"Error generating signed URL: {e}")
        return None
    
def delete_file(bucket_name, file_name):
    """Delete a file from the GCS bucket."""
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        blob.delete()
        logging.info(f"Deleted file: {file_name} from bucket: {bucket_name}")
        return True
    except Exception as e:
        logging.error(f"Error deleting file: {e}")
        return False

def get_list_of_files(bucket_name):
    """Retrieve files from a GCS bucket with signed URLs."""
    try:
        logging.info(f"Fetching file list from bucket: {bucket_name}")
        blobs = storage_client.list_blobs(bucket_name)
        files = []
        for blob in blobs:
            signed_url = generate_signed_url(bucket_name, blob.name)
            if signed_url:
                files.append({"name": blob.name, "url": signed_url})
        return files
    except Exception as e:
        logging.error(f"Error listing files: {e}")
        return []

def upload_file(bucket_name, file_name):
    try:
        logging.info(f"Uploading file: {bucket_name}/{file_name}")
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        blob.upload_from_filename(file_name)
        logging.info("Upload successful!")
    except Exception as e:
        logging.error(f"Error uploading file: {e}")

def download_file(bucket_name, file_name):
    try:
        logging.info(f"Downloading file: {bucket_name}/{file_name}")
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        blob.download_to_filename(file_name)
        logging.info(f"Download successful: {file_name}")
    except Exception as e:
        logging.error(f"Error downloading file: {e}")

# Example Usage
if __name__ == "__main__":
    bucket_name = "jpeg-bucket"
    file_name = "test.txt"

    # Upload file and add metadata to Datastore
    upload_file(bucket_name, file_name)
    file_url = f"https://storage.cloud.google.com/{bucket_name}/{file_name}"
    add_db_entry({
        "name": file_name,
        "url": file_url,
        "user": "your-username",
        "timestamp": int(time.time())
    })

    # List files in the bucket
    logging.info("Files in bucket:")
    logging.info(get_list_of_files(bucket_name))

    # Download the file
    download_file(bucket_name, file_name)

    # Fetch metadata from Datastore
    logging.info("Datastore entries:")
    logging.info(fetch_db_entry({"user": "your-username"}))