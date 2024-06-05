import base64
import json

from model import pdf_to_json


def extract_json_from_pdf(bucket_name, blob_name):
    uri = f"gs://{bucket_name}/{blob_name}"
    json_response = pdf_to_json(uri)
    print(json_response)


def process_pdf_dates(event, context):
    pubsub_message = base64.b64decode(event["data"]).decode("utf-8")
    message_json = json.loads(pubsub_message)

    bucket_name = message_json["bucket"]
    blob_name = message_json["name"]

    extract_json_from_pdf(bucket_name, blob_name)
