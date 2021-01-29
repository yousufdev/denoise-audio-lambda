import os
import json


def get_s3_mock_event():
    with open(os.environ["S3_MOCK_EVENT"]) as event_json:
        s3_event = json.load(event_json)
        return s3_event