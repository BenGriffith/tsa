import json
import os

import requests
from bs4 import BeautifulSoup
from google.cloud import storage
from model import extract_date

BUCKET = os.getenv("BUCKET")
SOURCE_PDF_PREFIX = os.getenv("SOURCE_PDF_PREFIX")
PROCESSED_DATES = os.getenv("PROCESSED_DATES")
DOMAIN = "https://www.tsa.gov/"
TSA_URL = "https://www.tsa.gov/foia/readingroom"
MOST_RECENT_LINKS_COUNT = 3


def create_processed_dates_blob(blob):
    blob.upload_from_string('{"processed_dates": []}', content_type="application/json")
    json_string = blob.download_as_text()
    json_data = json.loads(json_string)
    return json_data


def update_processed_dates_blob(processed_dates):
    client = storage.Client()
    bucket = client.bucket(BUCKET)
    blob = bucket.blob(f"{SOURCE_PDF_PREFIX}/{PROCESSED_DATES}")

    json_string = blob.download_as_text()
    json_data = json.loads(json_string)
    json_data["processed_dates"].extend(processed_dates)

    blob.upload_from_string(json.dumps(json_data), content_type="application/json")


def read_tsa_dates_from_gcs():
    client = storage.Client()
    bucket = client.bucket(BUCKET)
    blob = bucket.blob(f"{SOURCE_PDF_PREFIX}/{PROCESSED_DATES}")
    if blob.exists():
        json_string = blob.download_as_text()
        return json.loads(json_string)
    return create_processed_dates_blob(blob)


def read_pdf():
    response = requests.get(TSA_URL)
    soup = BeautifulSoup(response.text, "html.parser")
    link_elements = soup.find_all("a", class_="foia-reading-link")

    links = []
    for link_element in link_elements[:MOST_RECENT_LINKS_COUNT]:
        text = link_element.text
        if "tsa throughput" not in text.lower():
            continue

        links.append(link_element["href"])
    return links


def write_pdf(link, blob_name):
    response = requests.get(f"{DOMAIN}{link}")

    client = storage.Client()
    bucket = client.bucket(BUCKET)
    blob = bucket.blob(f"{SOURCE_PDF_PREFIX}/{blob_name}")
    blob.upload_from_string(response.content, content_type="application/pdf")
    if blob.exists:
        return True


def process_pdf(context):

    links_to_process = read_pdf()
    links_processed = read_tsa_dates_from_gcs()
    links_processed_set = set(links_processed["processed_dates"])
    links_to_not_process = set()

    for link in links_to_process:
        first_date, second_date = extract_date(link).split(", ")
        if first_date in links_processed_set or second_date in links_processed_set:
            links_to_not_process.add(link)

    links_to_process_set = set(links_to_process)
    links_to_be_processed = links_to_process_set - links_to_not_process

    dates_processed = []
    for link in links_to_be_processed:
        blob_name = link.split("/")[-1]
        blob_created = write_pdf(link, blob_name)
        if blob_created:
            dates_processed += extract_date(blob_name).split(", ")

    if dates_processed:
        update_processed_dates_blob(dates_processed)

    return "Processing complete", 200
