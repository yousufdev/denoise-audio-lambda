import pytest
from shutil import copy
from app import handler
from app.utils import get_s3_mock_event


@pytest.fixture()
def s3_event():
    """Generates S3 Event"""

    s3_event = get_s3_mock_event()
    return s3_event


def test_lambda_handler(s3_event, mocker):
    mocker.patch("app.handler.download_s3_object", return_value=None)
    mocker.patch("app.handler.upload_s3_object", return_value=None)
    for event in s3_event["Records"]:
        file_path = event["s3"]["object"]["key"]
        copy(file_path, "/tmp")

    try:
        handler.lambda_handler(s3_event, None)
    except Exception:
        assert False
