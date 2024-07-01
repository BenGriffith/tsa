#!/bin/bash
cd "$(dirname "$0")/.."
cp requirements.txt tsa/scrape_weekly_pdf/
cp requirements.txt tsa/publish_dates_from_weekly_pdf/
