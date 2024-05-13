import json

import requests
import vertexai
from bs4 import BeautifulSoup
from google.cloud import storage
from vertexai.generative_models import GenerativeModel
from vertexai.preview import generative_models

MODEL = "gemini-1.5-pro-preview-0409"
BUCKET = "tsa-throughput"
PROCESSED_DATES = "processed-tsa-dates.json"
DOMAIN = "https://www.tsa.gov/"
TSA_URL = "https://www.tsa.gov/foia/readingroom"
MOST_RECENT_LINKS_COUNT = 5


def generate(text, generation_config, safety_settings):
    vertexai.init()
    model = GenerativeModel(MODEL)
    response = model.generate_content(
        contents=[text],
        generation_config=generation_config,
        safety_settings=safety_settings,
        stream=False,
    )
    return response.text.strip(" \n")


def extract_date(filename):
    text = f"""
    you are an assistant and assigned with the task of extracting dates from an input string

    input string: \"{filename}\",

    return the dates using the format YYYY-MM-DD, YYYY-MM-DD
    """

    generation_config = {
        "max_output_tokens": 8192,
        "temperature": 1,
        "top_p": 0.95,
    }

    block_medium_and_above = generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE

    safety_settings = {
        generative_models.HarmCategory.HARM_CATEGORY_HATE_SPEECH: block_medium_and_above,
        generative_models.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: block_medium_and_above,
        generative_models.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: block_medium_and_above,
        generative_models.HarmCategory.HARM_CATEGORY_HARASSMENT: block_medium_and_above,
    }

    filename_date = generate(text, generation_config, safety_settings)
    return filename_date


def create_processed_dates_blob(blob):
    blob.upload_from_string('{"processed_dates": []}')
    json_string = blob.download_as_text()
    json_data = json.loads(json_string)
    return json_data


def read_tsa_dates_from_gcs():
    client = storage.Client()
    bucket = client.bucket(BUCKET)
    blob = bucket.blob(PROCESSED_DATES)
    if blob.exists():
        json_string = blob.download_as_text()
        json_data = json.loads(json_string)
        return json_data
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
    blob = bucket.blob(blob_name)
    blob.upload_from_string(response.content, content_type="application/pdf")


def process_pdf():
    links_to_process = read_pdf()
    links_processed = read_tsa_dates_from_gcs()
    links_processed_set = set(links_processed["processed_dates"])
    links_to_not_process = set()

    for link in links_to_process:
        first_date, second_date = extract_date(link).split(", ")
        if first_date in links_processed or second_date in links_processed:
            links_to_not_process.add(link)

    links_to_process_set = set(links_to_process)
    links_to_be_processed = links_to_process_set - links_to_not_process

    dates_processed = []
    for link in links_to_be_processed:
        blob_name = link.split("/")[-1]
        write_pdf(link, blob_name)

    # get dates from links to be processed
    # get dates already processed
    # check if dates to be processed already exist in file
    # links processed should be added to processed links


if __name__ == "__main__":
    process_pdf()
