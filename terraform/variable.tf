variable "project_id" {
  type = string
  default = "playground"
}

variable "location" {
  type = string
  default = "us"
}

variable "region" {
  type = string
  default = "us-central1"
}

variable "bucket" {
  type = string
  default = "tsa-throughput"
}

variable "processed_dates" {
  type = string
  default = "processed-tsa-dates.json"
}
