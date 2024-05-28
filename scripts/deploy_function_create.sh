#!/bin/bash
cd "$(dirname "$0")/.."
cp requirements.txt tsa/create_pdf/
cd tsa/create_pdf/
zip -r ../../create_pdf.zip .
cd ../../
gsutil cp create_pdf.zip gs://tsa-throughput/cloud-function/create_pdf.zip
