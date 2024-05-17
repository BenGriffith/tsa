#!/bin/bash
cd "$(dirname "$0")/.."
cp requirements.txt tsa/scrape_pdf/
cd tsa/scrape_pdf/
zip -r ../../scrape_pdf.zip .
cd ../../
gsutil cp scrape_pdf.zip gs://tsa-throughput/cloud-function/scrape_pdf.zip
