import warnings
import boto3
import logging
import os
import subprocess
from urllib.parse import unquote_plus
from pathlib import Path
from app.utils import get_s3_mock_event

warnings.filterwarnings("ignore")


s3 = boto3.resource("s3")
logger = logging.getLogger()
logger.setLevel(logging.ERROR)


allowed_extensions = ["3gp", "m4a"]
storage_path = "/tmp/{}.{}"


def download_s3_object(bucket_name: str, key: str, file_path: str):
    print("Downloading")
    print(f"Bucket name: {bucket_name} || Key: {key} || out: {file_path}")
    s3.meta.client.download_file(bucket_name, key, file_path)


def upload_s3_object(file_path, bucket_name, key: str):
    print("Uploading")
    print(f"Bucket name: {bucket_name} || Key: {key} || in: {file_path}")
    s3.meta.client.upload_file(file_path, bucket_name, key)


def extract_s3_key_components(key: str):
    split_index = key.rfind("/")
    if split_index == -1:
        prefix, name_with_ext = "", key
    else:
        prefix, name_with_ext = key[:split_index], key[split_index + 1 :]

    split_index = name_with_ext.rfind(".")
    if split_index == -1:
        raise ValueError("Invalid object key")

    name, ext = name_with_ext[:split_index], name_with_ext[split_index + 1 :]
    return prefix, name, ext


def lambda_handler(event, context):

    ## This will only contain a single record a as per, https://stackoverflow.com/questions/40765699/how-many-records-can-be-in-s3-put-event-lambda-trigger
    for record in event["Records"]:
        files_to_delete = []
        prefix, name, ext = "", "", ""
        s3_obj_size_kb = record["s3"]["object"]["size"] / 1000
        if s3_obj_size_kb < 100:
            print(f"object_size: {s3_obj_size_kb}KB, skipping because it might not contain useful data")
            continue
        try:
            bucket_name = record["s3"]["bucket"]["name"]
            s3_obj_key = record["s3"]["object"]["key"]
            s3_obj_key = unquote_plus(s3_obj_key)
            prefix, name, ext = extract_s3_key_components(s3_obj_key)
            if ext not in allowed_extensions:
                raise ValueError("Invalid file extension")

            raw_file_path = storage_path.format(name, ext)
            processed_file_path = storage_path.format(name, "ogg")

            download_s3_object(bucket_name, s3_obj_key, raw_file_path)
            files_to_delete.append(raw_file_path)

            # single quoting input and output filename because names can have spaces
            cmd = f"ffmpeg -i '{raw_file_path}' -af 'lv2=plugin=https\\\\://github.com/lucianodato/speech-denoiser' -c:a libopus -b:a 48k -ar 16k '{processed_file_path}' -loglevel error -y"
            process = subprocess.run(cmd, shell=True)
            if process.returncode != 0:
                raise SystemError(process.stderr)

            files_to_delete.append(processed_file_path)

            new_object_key = f"{prefix}/{name}.ogg"
            upload_s3_object(
                processed_file_path,
                os.environ["OUTPUT_BUCKET_NAME"],
                new_object_key,
            )
        except Exception:
            logger.exception("Failed to process files")
            raise
        finally:
            for path in files_to_delete:
                Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    event = get_s3_mock_event()
    lambda_handler(event, {})
