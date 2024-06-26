import base64
import json
import io

from fastapi import FastAPI, Request
from google.cloud import storage
import pdfplumber

from tables.manager import TableManager


app = FastAPI()


def pdf_file_like(bucket_name, blob_name):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.get_blob(blob_name)
    pdf_bytes = blob.download_as_bytes()
    pdf_file_like = io.BytesIO(pdf_bytes)
    return pdf_file_like


def table_to_json(columns, rows):
    json_data = []
    previous_values = {column: None for column in columns}
    for row in rows:
        row = dict(zip(columns, row))
        for key, value in row.items():
            if value is None:
                row[key] = previous_values[key]
            else:
                previous_values[key] = value
        json_data.append(row)
    return json_data


def clean_name(column):
    new_column = ""
    for char in column:
        if char not in "\n, ".split(","):
            new_column += char
    return new_column.lower()


def pdf_to_json(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        table_settings = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}
        table_lattice = pdf.pages[0].extract_table(table_settings)
        airport_column_index = table_lattice[0].index("Airport")
        table_lattice[0][airport_column_index + 1] = "name"
        columns = [clean_name(column) for column in table_lattice[0]]
        rows = table_lattice[1:]
        json_data = table_to_json(columns, rows)
    return json_data


def extract_json_from_pdf(bucket_name, pdf_date):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    pdf_date_blobs = bucket.list_blobs(prefix=f"{pdf_date}/", delimiter="/")

    for i, pdf_date_blob in enumerate(pdf_date_blobs, start=1):
        if i == 1:
            continue
        pdf_file = pdf_file_like(bucket_name, pdf_date_blob.name)
        json_data = pdf_to_json(pdf_file)
        TableManager(json_data).execute()


@app.post("/process_tsa_data/")
async def process_pdf_dates(request: Request):
    pubsub_message = await request.json()
    pubsub_message = pubsub_message["message"]
    pubsub_message = base64.b64decode(pubsub_message["data"]).decode("utf-8")
    message_json = json.loads(pubsub_message)

    bucket_name = message_json["bucket"]
    pdf_date = message_json["pdf_date"]
    try:
        extract_json_from_pdf(bucket_name, pdf_date)
        return f"Processing completed for {pdf_date}", 200
    except Exception as e:
        return f"Error encountered: {e}", 500
