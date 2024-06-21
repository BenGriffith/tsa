import os
import calendar

from datetime import datetime
import hashlib

from google.cloud import bigquery


PROJECT_ID = os.environ["PROJECT_ID"]
DATASET_ID = os.environ["DATASET_ID"]


class TableManager:
    def __init__(self, tsa_data):
        self.bq_client = bigquery.Client()
        self.tsa_data = tsa_data

    def exists(self, table, key, key_value):
        table_id = f"{PROJECT_ID}.{DATASET_ID}.{table}"
        query = (
            f"""SELECT COUNTIF({key} = {key_value}) AS record_count FROM `{table_id}`"""
        )
        query_result = self.bq_client.query(query).result()
        record_count = next(query_result).get("record_count", 0)
        return record_count > 0

    def insert_row(self, table, row):
        table_id = f"{PROJECT_ID}.{DATASET_ID}.{table}"
        self.bq_client.insert_rows_json(table_id, [row])

    def get_id(self, string):
        full_hash = hashlib.sha256(string.encode("utf-8")).hexdigest()
        truncated_hash = int(full_hash[:8], 16)
        return truncated_hash

    def execute(self):
        for row in self.tsa_data:
            tsa_date, tsa_hour, code, name, city, state, checkpoint, passengers = (
                row.values()
            )
            tsa_date = datetime.strptime(tsa_date, "%m/%d/%Y").strftime("%Y-%m-%d")

            time_id = self.get_id(tsa_date)
            hour_id = self.get_id(tsa_hour)
            airport_id = self.get_id(code)
            checkpoint_id = self.get_id(checkpoint)
            city_id = self.get_id(city)
            state_id = self.get_id(state)

            # dim_hour
            if not self.exists("dim_hour", "hour_id", hour_id):
                hour_of_day = datetime.strptime(tsa_hour, "%H:%M").hour
                self.insert_row(
                    "dim_hour", {"hour_id": hour_id, "hour_of_day": hour_of_day}
                )

            # dim_time
            if not self.exists("dim_time", "time_id", time_id):
                _tsa_date = datetime.strptime(tsa_date, "%Y-%m-%d")
                day_of_week = calendar.day_name[
                    calendar.weekday(_tsa_date.year, _tsa_date.month, _tsa_date.day)
                ]
                month = calendar.month_name[_tsa_date.month]
                quarter = ""
                year = ""

            # dim_airport
            # dim_checkpoint
            # dim_city
            # dim_state
