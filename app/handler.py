import sys
import warnings
import librosa
import noisereduce as nr
import soundfile as sf
import boto3
import ffmpeg
import logging
from itertools import count
import os
from urllib.parse import unquote_plus
from pathlib import Path

sys.path.append(Path(__file__).parent.parent.as_posix())
from app.utils import get_s3_mock_event

warnings.filterwarnings("ignore")

noisy_audio_dir = Path(__file__).resolve().parent / "noisy_audios"
noise_dir = Path(__file__).resolve().parent / "noise"
s3 = boto3.resource("s3")
logger = logging.getLogger()
logger.setLevel(logging.ERROR)

# Load the noise
noise, _ = sf.read(noise_dir / "noise.wav")
allowed_extensions = ["3gp", "m4a"]
audio_chunk_size = 10 * 60  # 10 minutes
output_path = "/tmp/{}.{}"


def download_s3_object(bucket_name, key: str, output_path):
    print("Downloading")
    print(f"Bucket name: {bucket_name} || Key: {key} || out: {output_path}")
    s3.meta.client.download_file(bucket_name, key, output_path)


def upload_s3_object(input_path, bucket_name, key: str):
    print("Uploading")
    print(f"Bucket name: {bucket_name} || Key: {key} || in: {input_path}")
    s3.meta.client.upload_file(input_path, bucket_name, key)


def extract_s3_key_components(key: str):
    split_index = key.rfind("/")
    if split_index == -1:
        prefix, name_with_ext = "", key
    else:
        prefix, name_with_ext = key[:split_index], key[split_index + 1 :]

    split_index = name_with_ext.rfind(".")
    if split_index == -1:
        raise Exception("Invalid object key")

    name, ext = name_with_ext[:split_index], name_with_ext[split_index + 1 :]
    return prefix, name, ext


def reduce_noise(name, ext):
    chunk_number = 0
    chunk_paths = []
    for c in count(start=0, step=audio_chunk_size):
        data, rate = librosa.core.load(output_path.format(name, ext), sr=None, offset=c, duration=audio_chunk_size)
        if data.size == 0:
            break

        ## Most memory consuming line
        reduced_noise = nr.reduce_noise(audio_clip=data, noise_clip=noise, verbose=False)

        chunk_output_path = output_path.format(f"{name}_{chunk_number}", "flac")
        sf.write(chunk_output_path, reduced_noise, rate)
        chunk_paths.append(chunk_output_path)
        chunk_number += 1

    return chunk_paths


def lambda_handler(event, context):

    for record in event["Records"]:
        output_paths = []
        prefix, name, ext = "", "", ""
        try:
            bucket_name = record["s3"]["bucket"]["name"]
            s3_obj_key = record["s3"]["object"]["key"]
            s3_obj_key = unquote_plus(s3_obj_key)
            prefix, name, ext = extract_s3_key_components(s3_obj_key)
            if ext not in allowed_extensions:
                raise Exception("Invalid file extension")

            download_s3_object(bucket_name, s3_obj_key, output_path.format(name, ext))
            output_paths.append(output_path.format(name, ext))
            chunk_paths = reduce_noise(name, ext)
            if not chunk_paths:
                raise Exception("Invalid data in file")

            output_paths += chunk_paths
            ffmpeg_inputs = [ffmpeg.input(in_file) for in_file in chunk_paths]

            (
                ffmpeg.concat(*ffmpeg_inputs, v=0, a=1)
                .output(output_path.format(name, "ogg"))
                .global_args("-loglevel", "error")
                .run(overwrite_output=True)
            )
            output_paths.append(output_path.format(name, "ogg"))

            new_object_key = f"{prefix}/{name}.ogg"
            upload_s3_object(
                output_path.format(name, "ogg"),
                os.environ["OUTPUT_BUCKET_NAME"],
                new_object_key,
            )
        except Exception as e:
            logger.exception("Failed to process files")
            return False
        finally:
            for path in output_paths:
                Path(path).unlink(missing_ok=True)

    return True


if __name__ == "__main__":
    event = get_s3_mock_event()
    lambda_handler(event, "")
