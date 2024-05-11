import io

import pdfplumber
from google.cloud import storage


def get_pdf():
    client = storage.Client()
    bucket = client.get_bucket("tsa-throughput")
    blob = bucket.get_blob("tsa-total-throughput-april-28-2024-to-may-4-2024.pdf")

    pdf_bytes = blob.download_as_bytes()

    pdf_file_like = io.BytesIO(pdf_bytes)

    with pdfplumber.open(pdf_file_like) as pdf:
        page = pdf.pages[0]

        table_settings = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}

        table_lattice = page.extract_table(table_settings=table_settings)
        columns = table_lattice[0]
        rows = table_lattice[1:]
        for row in rows:
            row_data = dict(zip(columns, row))


if __name__ == "__main__":
    pdf = get_pdf()
