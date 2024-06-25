import os
import calendar
import uuid

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

    def exists_in_bridge(self, table, first_key, first_value, second_key, second_value):
        table_id = f"{PROJECT_ID}.{DATASET_ID}.{table}"
        query = f"""SELECT COUNTIF({first_key} = {first_value} AND {second_key} = {second_value}) AS record_count FROM `{table_id}`"""
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
                quarter = (_tsa_date.month - 1) // 3
                year = _tsa_date.year
                self.insert_row(
                    "dim_time",
                    {
                        "time_id": time_id,
                        "date": tsa_date,
                        "day_of_week": day_of_week,
                        "month": month,
                        "quarter": quarter,
                        "year": year,
                    },
                )

            # dim_airport
            if not self.exists("dim_airport", "airport_id", airport_id):
                self.insert_row(
                    "dim_airport",
                    {"airport_id": airport_id, "code": code, "name": name},
                )

            # dim_checkpoint
            if not self.exists("dim_checkpoint", "checkpoint_id", checkpoint_id):
                self.insert_row(
                    "dim_checkpoint",
                    {"checkpoint_id": checkpoint_id, "name": checkpoint},
                )

            # dim_city
            if not self.exists("dim_city", "city_id", city_id):
                self.insert_row("dim_city", {"city_id": city_id, "name": city})

            # dim_state
            if not self.exists("dim_state", "state_id", state_id):
                self.insert_row("dim_state", {"state_id": state_id, "name": state})

            # bridge tables
            if not self.exists_in_bridge(
                "airport_checkpoint_bridge",
                "airport_id",
                airport_id,
                "checkpoint_id",
                checkpoint_id,
            ):
                self.insert_row(
                    "airport_checkpoint_bridge",
                    {"airport_id": airport_id, "checkpoint_id": checkpoint_id},
                )

            if not self.exists_in_bridge(
                "city_state_bridge", "city_id", city_id, "state_id", state_id
            ):
                self.insert_row(
                    "city_state_bridge", {"city_id": city_id, "state_id": state_id}
                )

            # fact_passenger_checkpoint
            self.insert_row(
                "fact_passenger_checkpoint",
                {
                    "date": tsa_date,
                    "event_id": str(uuid.uuid4()),
                    "time_id": time_id,
                    "hour_id": hour_id,
                    "airport_id": airport_id,
                    "checkpoint_id": checkpoint_id,
                    "city_id": city_id,
                    "state_id": state_id,
                    "passengers": passengers,
                },
            )
