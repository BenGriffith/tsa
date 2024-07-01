import os

import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.preview import generative_models

MODEL = "gemini-1.5-pro-preview-0409"
PROJECT = os.getenv("PROJECT")
REGION = os.getenv("REGION")


def generate(text, generation_config, safety_settings):
    vertexai.init(project=PROJECT, location=REGION)
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
