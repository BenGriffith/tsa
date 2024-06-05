import os

import vertexai
from vertexai.generative_models import GenerativeModel, Part
from vertexai.preview import generative_models

MODEL = "gemini-1.5-flash-001"
PROJECT = os.getenv("PROJECT")
REGION = os.getenv("REGION")


def generate(document, text, generation_config, safety_settings):
    vertexai.init(project=PROJECT, location=REGION)
    model = GenerativeModel(MODEL)
    responses = model.generate_content(
        contents=[document, text],
        generation_config=generation_config,
        safety_settings=safety_settings,
        stream=True,
    )
    return [response for response in responses]


def pdf_to_json(uri):
    document = Part.from_uri(uri, "application/pdf")
    text = """You are a data extraction specialist. The page title and page title date should be excluded. Return a JSON format."""

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

    json_response = generate(document, text, generation_config, safety_settings)
    return json_response
