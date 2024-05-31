import base64
import io
import json
from datetime import datetime

import numpy as np
import pdfplumber
from google.cloud import storage
from PyPDF2 import PdfReader, PdfWriter


def pdf_file_like(bucket_name, blob_name):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.get_blob(blob_name)
    pdf_bytes = blob.download_as_bytes()
    pdf_file_like = io.BytesIO(pdf_bytes)
    return pdf_file_like


def create_pdfs_by_date(bucket_name, date, pdf_file):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    pdf_reader = PdfReader(pdf_file)

    with pdfplumber.open(pdf_file) as pdf:
        table_settings = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}

        pdf_writer = PdfWriter()
        for i, page in enumerate(pdf.pages, start=1):
            table_lattice = page.extract_table(table_settings)
            rows = table_lattice[1:]
            np_rows = np.array(rows)
            first_elements = np_rows[:, 0]
            if date in first_elements:
                pdf_writer.add_page(pdf_reader.pages[i - 1])

        date_format = datetime.strptime(date, "%m/%d/%Y").strftime("%Y-%m-%d")
        output_pdf = f"{date_format}.pdf"
        blob = bucket.blob(output_pdf)
        with blob.open("wb") as daily_pdf:
            pdf_writer.write(daily_pdf)


def process_pdf_by_date(event, context):
    pubsub_message = base64.b64decode(event["data"]).decode("utf-8")
    message_json = json.loads(pubsub_message)

    bucket_name = message_json["bucket"]
    blob_name = message_json["blob"]
    pdf_date = message_json["pdf_date"]

    pdf_file = pdf_file_like(bucket_name, blob_name)
    create_pdfs_by_date(bucket_name, pdf_date, pdf_file)
