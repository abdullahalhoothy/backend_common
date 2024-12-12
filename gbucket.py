import time

from google.cloud import storage
from google.oauth2 import service_account


def get_google_cloud_bucket_conn(bucket_name: str, cred_path: str):
    """Setup Google Cloud Storage client"""
    credentials = service_account.Credentials.from_service_account_file(cred_path)
    storage_client = storage.Client(credentials=credentials)
    bucket = storage_client.bucket(bucket_name)
    return bucket


def upload_file_to_google_cloud_bucket(file, bucket_name, bucket_path, cred_path):
    """Upload file to google bucket"""
    bucket = get_google_cloud_bucket_conn(bucket_name, cred_path)
    blob = bucket.blob(f"{bucket_path}/{file.filename}-{time.time()}")
    blob.upload_from_file(file.file, content_type=file.content_type)
    # blob.make_public()
    return blob.public_url
