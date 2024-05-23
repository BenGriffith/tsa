import io
from datetime import datetime

import numpy as np
import pdfplumber
from google.cloud import storage
from PyPDF2 import PdfReader, PdfWriter


def pdf_file_like():
    client = storage.Client()
    bucket = client.bucket("tsa-throughput")
    blob = bucket.get_blob("tsa-total-throughput-data-may-5-2024-to-may-11-2024.pdf")
    pdf_bytes = blob.download_as_bytes()
    pdf_file_like = io.BytesIO(pdf_bytes)
    return pdf_file_like


def read_pdf_dates(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        table_settings = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}
        dates = set()

        for page in pdf.pages:
            table_lattice = page.extract_table(table_settings=table_settings)
            columns = table_lattice[0]
            rows = table_lattice[1:]
            np_rows = np.array(rows)
            first_elements = np_rows[:, 0]
            dates.update(filter(None, first_elements))

    return dates


def create_pdfs_by_date(dates, pdf_file):
    client = storage.Client()
    bucket = client.bucket("tsa-throughput")
    pdf_reader = PdfReader(pdf_file)

    with pdfplumber.open(pdf_file) as pdf:
        table_settings = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}

        for date in dates:
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


def process_pdf_dates():
    # def process_pdf_dates(context):
    pdf_file = pdf_file_like()
    dates = read_pdf_dates(pdf_file)
    create_pdfs_by_date(dates, pdf_file)


if __name__ == "__main__":
    process_pdf_dates()
