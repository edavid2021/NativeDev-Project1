import os
import logging
from google.cloud import storage

logging.basicConfig(level=logging.INFO)

# Initialize the storage client
storage_client = storage.Client.create_anonymous_client()

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
    """Retrieve all files from a GCS bucket with public URLs."""
    try:
        logging.info(f"Fetching file list from bucket: {bucket_name}")
        bucket = storage_client.bucket(bucket_name)
        blobs = bucket.list_blobs()
        
        files = []
        for blob in blobs:
            public_url = f"https://storage.googleapis.com/{bucket_name}/{blob.name}"
            files.append({"name": blob.name, "url": public_url})
        
        return files
    except Exception as e:
        logging.error(f"Error listing files: {e}")
        return []

def upload_file(bucket_name, file_path):
    """Uploads a file to a GCS bucket and makes it publicly accessible."""
    try:
        file_name = file_path.split("/")[-1]  # Extract file name
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)

        # Upload file
        blob.upload_from_filename(file_path)
        
        # Make file publicly accessible
        blob.make_public()

        public_url = f"https://storage.googleapis.com/{bucket_name}/{file_name}"
        logging.info(f"Uploaded {file_name} to {bucket_name} and made it public.")
        return public_url
    except Exception as e:
        logging.error(f"Error uploading file: {e}")
        return None

def download_file(bucket_name, file_name, destination_path):
    """Downloads a file from a GCS bucket to a local path."""
    try:
        logging.info(f"Downloading file: {bucket_name}/{file_name} to {destination_path}")
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        blob.download_to_filename(destination_path)
        logging.info(f"Download successful: {destination_path}")
        return destination_path
    except Exception as e:
        logging.error(f"Error downloading file: {e}")
        return None

# Example Usage
if __name__ == "__main__":
    bucket_name = "jpeg-hw"
    file_name = "test.txt"
    destination_path = f"./downloads/{file_name}"

    # Upload file
    uploaded_url = upload_file(bucket_name, file_name)
    logging.info(f"Uploaded file URL: {uploaded_url}")

    # List files in the bucket
    logging.info("Files in bucket:")
    logging.info(get_list_of_files(bucket_name))

    # Download the file
    download_file(bucket_name, file_name, destination_path)

    # Delete the file (optional)
    # delete_file(bucket_name, file_name)