import base64
import json
import os
import re
from datetime import datetime, timedelta

from google.cloud import pubsub_v1

PROJECT = os.environ["PROJECT"]
TOPIC = os.environ["TOPIC"]


def read_pdf_dates(blob_name):
    date_pattern = re.compile(r"(\w+)-(\d{1,2})-(\d{4})")
    dates = date_pattern.findall(blob_name)

    start_date, end_date = dates
    start_month, start_day, start_year = start_date
    end_month, end_day, end_year = end_date

    start_date = datetime.strptime(f"{start_year}-{start_month}-{start_day}", "%Y-%b-%d")
    end_date = datetime.strptime(f"{end_year}-{end_month}-{end_day}", "%Y-%b-%d")

    date_list = []
    current_date = start_date
    while current_date <= end_date:
        date_list.append(current_date.strftime("%-m/%d/%Y"))
        current_date += timedelta(days=1)
    return date_list


def publish_pdf_date_messages(bucket_name, blob_name, pdf_dates):
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT, TOPIC)

    for pdf_date in pdf_dates:
        message_json = json.dumps(
            {
                "bucket": bucket_name,
                "blob": blob_name,
                "pdf_date": pdf_date,
            }
        )
        message_bytes = message_json.encode("utf-8")
        publisher.publish(topic_path, data=message_bytes)


def process_pdf_dates(event, context):
    pubsub_message = base64.b64decode(event["data"]).decode("utf-8")
    message_json = json.loads(pubsub_message)

    bucket_name = message_json["bucket"]
    blob_name = message_json["name"]

    pdf_dates = read_pdf_dates(blob_name)
    publish_pdf_date_messages(bucket_name, blob_name, pdf_dates)
