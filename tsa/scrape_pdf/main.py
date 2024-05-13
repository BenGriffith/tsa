import requests
import vertexai
from bs4 import BeautifulSoup
from google.cloud import storage
from vertexai.generative_models import GenerativeModel
from vertexai.preview import generative_models

MODEL = "gemini-1.5-pro-preview-0409"
BUCKET = "tsa-throughput"
DOMAIN = "https://www.tsa.gov/"
TSA_URL = "https://www.tsa.gov/foia/readingroom"


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


def read_tsa_dates_from_gcs():
    client = storage.Client()
    bucket = client.bucket(BUCKET)
    blobs = bucket.list_blobs()
    tsa_dates = [extract_date(blob.name) for blob in blobs]


def read_pdf():
    response = requests.get(TSA_URL)
    soup = BeautifulSoup(response.text, "html.parser")
    link_elements = soup.find_all("a", class_="foia-reading-link")

    links = []
    for link_element in link_elements[:1]:
        text = link_element.text
        if "tsa throughput" not in text.lower():
            continue

        links.append(link_element["href"])
    return links


def write_pdf(links):
    response = requests.get(f"{DOMAIN}{links[0]}")

    client = storage.Client()
    bucket = client.bucket("tsa-throughput")
    blob = bucket.blob("tsa-total-throughput-april-28-2024-to-may-4-2024.pdf")
    blob.upload_from_string(response.content, content_type="application/pdf")


def process_pdf():
    pass


if __name__ == "__main__":
    # links = read_pdf()
    # write_pdf(links)
    read_tsa_dates_from_gcs()
