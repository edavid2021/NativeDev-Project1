import os
import logging
import time
import json
from datetime import timedelta
from google.cloud import storage, datastore
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)

# Set up Google Cloud Authentication
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./cloudEnv.json"

# Initialize Google Cloud clients
storage_client = storage.Client()
datastore_client = datastore.Client()

# Default bucket name
bucket_name = "jpeg-hw"

def generate_signed_url(blob_name, expiration=3600):
    """Generate a signed URL for a blob in GCS."""
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expiration),
            method="GET"
        )
        return signed_url
    except Exception as e:
        logging.error(f"Error generating signed URL: {e}")
        return None

def store_signed_url(user_email, file_name, signed_url, expiration_time):
    """Stores signed URL metadata in Google Cloud Datastore."""
    try:
        key = datastore_client.key("SignedURL", f"{user_email}_{file_name}")
        entity = datastore.Entity(key)
        entity.update({
            "user_email": user_email,
            "file_name": file_name,
            "signed_url": signed_url,
            "expires_at": expiration_time
        })
        datastore_client.put(entity)
        logging.info(f"Stored signed URL for {file_name} in Datastore.")
    except Exception as e:
        logging.error(f"Error storing signed URL: {e}")

# Fetches an existing signed URL or generates a new one if expired
def get_signed_url(user_email, file_name, expiration=3600):
    key = datastore_client.key("SignedURL", f"{user_email}_{file_name}")
    entity = datastore_client.get(key)

    if entity:
        expires_at = entity["expires_at"]
        current_time = time.time()

        if current_time < expires_at:
            logging.info(f"Returning cached signed URL for {file_name}")
            return entity["signed_url"]

    # Generate a new signed URL if expired or missing
    new_signed_url = generate_signed_url(file_name, expiration)
    expiration_time = time.time() + expiration  # Store new expiration time
    store_signed_url(user_email, file_name, new_signed_url, expiration_time)

    return new_signed_url

# Uploads a file to GCS and generates a signed URL
def upload_file(file_path, user_email):
    try:
        file_name = os.path.basename(file_path)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)

        # Upload file
        blob.upload_from_filename(file_path)

        # Generate signed URL after upload
        signed_url = generate_signed_url(file_name)
        expiration_time = time.time() + 3600  # 1-hour expiration

        # Store signed URL in Datastore
        store_signed_url(user_email, file_name, signed_url, expiration_time)

        logging.info(f"Uploaded {file_name} and stored signed URL.")
        return signed_url
    except Exception as e:
        logging.error(f"Error uploading file: {e}")
        return None

# Deletes a file from GCS and removes its metadata from Datastore
def delete_file(blob_name, user_email):
    try:
        bucket = storage_client.bucket(bucket_name)
        
        # Delete image file
        image_blob = bucket.blob(blob_name)
        if image_blob.exists():
            image_blob.delete()
            print(f"Deleted image: {blob_name}")

        # Delete associated JSON metadata file
        json_filename = f"{blob_name.rsplit('.', 1)[0]}.json"
        json_blob = bucket.blob(json_filename)
        if json_blob.exists():
            json_blob.delete()
            print(f"Deleted metadata: {json_filename}")

        # Remove the entry from Datastore
        query = datastore_client.query(kind='images')
        query.add_filter("blob_name", "=", blob_name)
        query.add_filter("useremail", "=", user_email)
        results = list(query.fetch())

        if results:
            for entity in results:
                datastore_client.delete(entity.key)
            print(f"Deleted Datastore entry for: {blob_name}")

        return True
    except Exception as e:
        print(f"Error deleting file {blob_name}: {e}")
        return False

# Uploads metadata JSON file for image descriptions
def upload_metadata(file_name, metadata):
    try:
        json_blob_name = f"{os.path.splitext(file_name)[0]}.json"
        bucket = storage_client.bucket(bucket_name)
        json_blob = bucket.blob(json_blob_name)
        
        json_blob.upload_from_string(
            json.dumps(metadata),
            content_type="application/json"
        )
        logging.info(f"Uploaded metadata file {json_blob_name} to GCS.")
        return True
    except Exception as e:
        logging.error(f"Error uploading metadata: {e}")
        return False

# Fetches image metadata JSON file from GCS
def get_image_metadata(file_name):
    try:
        json_blob_name = f"{os.path.splitext(file_name)[0]}.json"
        bucket = storage_client.bucket(bucket_name)
        json_blob = bucket.blob(json_blob_name)

        if json_blob.exists():
            metadata = json.loads(json_blob.download_as_string())
            return metadata
        else:
            return {"title": "Untitled Image", "description": "No description available"}
    except Exception as e:
        logging.error(f"Error fetching metadata: {e}")
        return {"title": "Untitled Image", "description": "No description available"}

# Example Usage
if __name__ == "__main__":
    user_email = "testuser@example.com"
    file_name = "test.txt"

    # Upload file and generate signed URL
    signed_url = upload_file(file_name, user_email)
    logging.info(f"Uploaded file signed URL: {signed_url}")