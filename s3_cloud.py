import io
import uuid
import boto3
from aiohttp import ClientError


def save_file_on_cloud(file):
    session = boto3.session.Session()
    s3 = session.client(
        service_name='s3',
        endpoint_url='https://storage.yandexcloud.net'
    )
    try:
        file_bytes = bytes(file.getbuffer())
        file_name = str(uuid.uuid4()) + ".jpg"
        s3.put_object(Bucket="avito-store", Key=file_name, Body=file_bytes)

        return file_name
    finally:
        s3.close()


def load_from_cloud(file_name):
    session = boto3.session.Session()
    s3 = session.client(
        service_name='s3',
        endpoint_url='https://storage.yandexcloud.net'
    )
    try:
        file_obj = io.BytesIO()
        s3.download_fileobj("avito-storage", file_name, file_obj)
        file_obj.seek(0)
        return file_obj.read()
    except ClientError as e:
        return None
    finally:
        s3.close()