import base64
import io
import json
import os
from datetime import datetime

import numpy as np
import pdfplumber
from fastapi import FastAPI, Request
from google.cloud import storage
from google.cloud import pubsub_v1
from PyPDF2 import PdfReader, PdfWriter

PROJECT = os.environ["PROJECT"]
TOPIC = os.environ["TOPIC"]

app = FastAPI()


def pdf_file_like(bucket_name, blob_name):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.get_blob(blob_name)
    pdf_bytes = blob.download_as_bytes()
    pdf_file_like = io.BytesIO(pdf_bytes)
    return pdf_file_like


def matching_pages_generator(pdf, date, table_settings):
    for i, page in enumerate(pdf.pages, start=1):
        table_lattice = page.extract_table(table_settings)
        rows = table_lattice[1:]
        np_rows = np.array(rows)
        first_elements = np_rows[:, 0]
        if date in first_elements:
            yield i


def create_pdf_by_date(bucket_name, date, pdf_file):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    pdf_reader = PdfReader(pdf_file)
    date_format = datetime.strptime(date, "%m/%d/%Y").strftime("%Y-%m-%d")

    with pdfplumber.open(pdf_file) as pdf:
        table_settings = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}

        for page_count in matching_pages_generator(pdf, date, table_settings):
            pdf_writer = PdfWriter()
            pdf_writer.add_page(pdf_reader.pages[page_count - 1])

            output_pdf = f"{date_format}/{page_count}.pdf"
            blob = bucket.blob(output_pdf)
            with blob.open("wb") as daily_pdf:
                pdf_writer.write(daily_pdf)

    return date_format


def publish_message(bucket, pdf_date):
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT, TOPIC)

    message_json = json.dumps({"bucket": bucket, "pdf_date": pdf_date})
    message_bytes = message_json.encode("utf-8")
    publisher.publish(topic_path, message_bytes)


@app.post("/process_pdf_by_date/")
async def process_pdf_by_date(request: Request):
    pubsub_message = await request.json()
    pubsub_message = pubsub_message["message"]
    pubsub_message = base64.b64decode(pubsub_message["data"]).decode("utf-8")
    message_json = json.loads(pubsub_message)

    bucket_name = message_json["bucket"]
    blob_name = message_json["blob"]
    pdf_date = message_json["pdf_date"]
    pdf_file = pdf_file_like(bucket_name, blob_name)

    try:
        print(f"Processing started for {pdf_date}")
        date_format = create_pdf_by_date(bucket_name, pdf_date, pdf_file)
        print(f"Processing completed for {pdf_date}")
        publish_message(bucket_name, date_format)
        print(f"Message published for {pdf_date}")
        return {f"Processing completed for {pdf_date}", 200}
    except Exception as e:
        return {f"Error encountered: {e}", 500}
