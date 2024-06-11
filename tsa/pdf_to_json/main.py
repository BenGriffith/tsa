import base64
import json

from fastapi import FastAPI, Request
from google.cloud import storage

from model import pdf_to_json

app = FastAPI()


def extract_json_from_pdf(bucket_name, pdf_date):
    client = storage.Client()
    bucket = client.get_bucket(bucket_name)
    pdf_date_blobs = bucket.list_blobs(prefix=f"{pdf_date}/", delimiter="/")
    for i, pdf_date_blob in enumerate(pdf_date_blobs, start=1):
        if i == 0:
            continue
        uri = f"gs://{bucket_name}/{pdf_date_blob.name}"
        json_response = pdf_to_json(uri)
        print(json_response)


@app.post("/process_tsa_data/")
async def process_pdf_dates(request: Request):
    pubsub_message = await request.json()
    pubsub_message = pubsub_message["message"]
    pubsub_message = base64.b64decode(pubsub_message["data"]).decode("utf-8")
    message_json = json.loads(pubsub_message)

    bucket_name = message_json["bucket"]
    pdf_date = message_json["pdf_date"]

    extract_json_from_pdf(bucket_name, pdf_date)
