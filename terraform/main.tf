provider "google" {
  project = var.project_id
}


# Pub/Sub
resource "google_pubsub_topic" "pdf_topic" {
  name = "pdf-topic"
}

resource "google_pubsub_topic" "create_pdf_topic" {
  name = "create-pdf-topic"
}

resource "google_pubsub_topic" "tsa_data_to_bigquery_topic" {
  name = "tsa-data-to-bigquery-topic"
}

resource "google_pubsub_subscription" "create_pdf_by_date_subscription" {
  name  = "create-pdf-by-date-subscription"
  topic = google_pubsub_topic.create_pdf_topic.name
  push_config {
    push_endpoint = "${google_cloud_run_v2_service.create_pdf_by_date.uri}/process_pdf_by_date/"
  }

  ack_deadline_seconds = 600
}

resource "google_pubsub_subscription" "tsa_data_to_bigquery_subscription" {
  name  = "tsa-data-to-bigquery-subscription"
  topic = google_pubsub_topic.tsa_data_to_bigquery_topic.name
  push_config {
    push_endpoint = "${google_cloud_run_v2_service.tsa_data_to_bigquery.uri}/process_tsa_data/"
  }

  ack_deadline_seconds = 600
}


# Cloud Storage
resource "google_storage_bucket" "tsa_throughput" {
  name          = var.bucket
  location      = var.location
  force_destroy = true

  provisioner "local-exec" {
    command = "${path.module}/../scripts/cloud_functions_setup.sh"
  }
}

resource "google_storage_bucket_object" "source_folder" {
  name    = "${var.source_pdf_prefix}/"
  content = " "
  bucket  = google_storage_bucket.tsa_throughput.name
}

resource "google_storage_bucket_object" "cloud_function" {
  name    = "cloud-function/"
  content = " "
  bucket  = google_storage_bucket.tsa_throughput.name
}

data "archive_file" "scrape_pdf_function" {
  type        = "zip"
  source_dir  = "${path.root}/../tsa/scrape_pdf"
  output_path = "${path.root}/../scrape_pdf.zip"
}

resource "google_storage_bucket_object" "scrape_pdf" {
  name   = "cloud-function/scrape_pdf.zip"
  bucket = google_storage_bucket.tsa_throughput.name
  source = data.archive_file.scrape_pdf_function.output_path
}

data "archive_file" "create_pdf_function" {
  type        = "zip"
  source_dir  = "${path.root}/../tsa/create_pdf"
  output_path = "${path.root}/../create_pdf.zip"
}

resource "google_storage_bucket_object" "create_pdf" {
  name   = "cloud-function/create_pdf.zip"
  bucket = google_storage_bucket.tsa_throughput.name
  source = data.archive_file.create_pdf_function.output_path
}

resource "google_storage_notification" "pdf_notification" {
  bucket             = google_storage_bucket.tsa_throughput.name
  topic              = google_pubsub_topic.pdf_topic.id
  payload_format     = "JSON_API_V1"
  event_types        = ["OBJECT_FINALIZE"]
  object_name_prefix = "${var.source_pdf_prefix}/"

  depends_on = [google_pubsub_topic_iam_binding.binding]
}


# Networking
resource "google_vpc_access_connector" "serverless_connector" {
  name          = "serverless-connector"
  region        = var.region
  network       = "default"
  ip_cidr_range = "10.8.0.0/28"
}


# IAM
resource "google_service_account" "scheduler_sa" {
  account_id   = "scheduler-sa"
  display_name = "Scheduler Service Account"
}

resource "google_project_iam_member" "scheduler_invoker" {
  project = var.project_id
  role    = "roles/cloudfunctions.invoker"
  member  = "serviceAccount:${google_service_account.scheduler_sa.email}"
}

data "google_storage_project_service_account" "gcs_account" {}

resource "google_pubsub_topic_iam_binding" "binding" {
  topic   = google_pubsub_topic.pdf_topic.id
  role    = "roles/pubsub.publisher"
  members = ["serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"]
}


# Cloud Functions
resource "google_cloudfunctions_function" "scrape_pdf" {
  name                          = "scrape-pdf"
  region                        = var.region
  description                   = "scrape pdf from TSA FOIA"
  runtime                       = "python39"
  available_memory_mb           = 512
  timeout                       = 180
  source_archive_bucket         = google_storage_bucket.tsa_throughput.name
  source_archive_object         = google_storage_bucket_object.scrape_pdf.name
  entry_point                   = "process_pdf"
  vpc_connector                 = google_vpc_access_connector.serverless_connector.name
  vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"

  environment_variables = {
    PROJECT           = var.project_id
    REGION            = var.region
    BUCKET            = var.bucket
    PROCESSED_DATES   = var.processed_dates
    SOURCE_PDF_PREFIX = var.source_pdf_prefix
  }

  trigger_http = true

  depends_on = [google_project_iam_member.scheduler_invoker]
}

resource "google_cloudfunctions_function" "create_pdf" {
  name                          = "create-pdf"
  region                        = var.region
  description                   = "create pdfs by date"
  runtime                       = "python39"
  available_memory_mb           = 512
  timeout                       = 540
  source_archive_bucket         = google_storage_bucket.tsa_throughput.name
  source_archive_object         = google_storage_bucket_object.create_pdf.name
  entry_point                   = "process_pdf_dates"
  vpc_connector                 = google_vpc_access_connector.serverless_connector.name
  vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"

  environment_variables = {
    PROJECT = var.project_id
    TOPIC   = google_pubsub_topic.create_pdf_topic.name
  }

  event_trigger {
    event_type = "google.pubsub.topic.publish"
    resource   = google_pubsub_topic.pdf_topic.name
  }
}


# Cloud Run
resource "google_cloud_run_v2_service" "create_pdf_by_date" {
  name     = "create-pdf-by-date"
  location = var.region

  template {
    scaling {
      max_instance_count = 10
      min_instance_count = 0
    }

    containers {
      image = "gcr.io/${var.project_id}/create-pdf-by-date:latest"

      env {
        name  = "PROJECT"
        value = var.project_id
      }

      env {
        name  = "TOPIC"
        value = google_pubsub_topic.tsa_data_to_bigquery_topic.name
      }

      resources {
        limits = {
          cpu    = "4"
          memory = "2 Gi"
        }
      }
      command = ["uvicorn"]
      args    = ["main:app", "--host", "0.0.0.0", "--port", "8080"]
    }

    timeout = "900s"

    vpc_access {
      connector = google_vpc_access_connector.serverless_connector.id
      egress    = "ALL_TRAFFIC"
    }
  }
}

resource "google_cloud_run_v2_service" "tsa_data_to_bigquery" {
  name     = "tsa-data-to-bigquery"
  location = var.region

  template {
    scaling {
      max_instance_count = 10
      min_instance_count = 0
    }

    containers {
      image = "gcr.io/${var.project_id}/tsa-data-to-bigquery:latest"

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }

      env {
        name = "DATASET_ID"
        value = google_bigquery_dataset.tsa.dataset_id
      }

      resources {
        limits = {
          cpu    = "4"
          memory = "2 Gi"
        }
      }
      command = ["uvicorn"]
      args    = ["main:app", "--host", "0.0.0.0", "--port", "8080"]
    }

    timeout = "900s"

    vpc_access {
      connector = google_vpc_access_connector.serverless_connector.id
      egress    = "ALL_TRAFFIC"
    }
  }
}

resource "google_cloud_run_service_iam_member" "create_pdf_by_date_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_service.create_pdf_by_date.location
  service  = google_cloud_run_v2_service.create_pdf_by_date.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "tsa_data_to_bigquery_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_service.tsa_data_to_bigquery.location
  service  = google_cloud_run_v2_service.tsa_data_to_bigquery.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}


# Cloud Scheduler
resource "google_cloud_scheduler_job" "scrape_pdf_job" {
  name        = "scrape-pdf-job"
  region      = var.region
  description = "job to scrape pdf from TSA FOIA"

  schedule  = "0 0 * * 4"
  time_zone = "Etc/UTC"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions_function.scrape_pdf.https_trigger_url
    oidc_token {
      service_account_email = google_service_account.scheduler_sa.email
    }
  }
}


# BigQuery
resource "google_bigquery_dataset" "tsa" {
  dataset_id = "tsa"
  location = var.location
}

resource "google_bigquery_table" "fact_passenger_checkpoint" {
  dataset_id = google_bigquery_dataset.tsa.dataset_id
  table_id = "fact_passenger_checkpoint"
  deletion_protection = false

  time_partitioning {
    type = "DAY"
    field = "date"
  }

  schema = jsonencode([
    {
      "name": "date",
      "type": "date",
      "mode": "required"
    },
    {
      "name": "event_id",
      "type": "integer",
      "mode": "required"
    },
    {
      "name": "time_id",
      "type": "integer",
      "mode": "required"
    },
    {
      "name": "hour_id",
      "type": "integer",
      "mode": "required"
    },
    {
      "name": "airport_id",
      "type": "integer",
      "mode": "required"
    },
    {
      "name": "checkpoint_id",
      "type": "integer",
      "mode": "required"
    },
    {
      "name": "city_id",
      "type": "integer",
      "mode": "required"
    },
    {
      "name": "state_id",
      "type": "integer",
      "mode": "required"
    },
    {
      "name": "passengers",
      "type": "integer",
      "mode": "required"
    }
  ])
}

resource "google_bigquery_table" "dim_time" {
  dataset_id = google_bigquery_dataset.tsa.dataset_id
  table_id = "dim_time"
  deletion_protection = false

  schema = jsonencode([
    {
      "name": "time_id",
      "type": "integer",
      "mode": "required"
    },
    {
      "name": "date",
      "type": "date",
      "mode": "required"
    },
    {
      "name": "day_of_week",
      "type": "string",
      "mode": "required"
    },
    {
      "name": "month",
      "type": "string",
      "mode": "required"
    },
    {
      "name": "quarter",
      "type": "integer",
      "mode": "required"
    },
    {
      "name": "year",
      "type": "integer",
      "mode": "required"
    }
  ])
}

resource "google_bigquery_table" "dim_hour" {
  dataset_id = google_bigquery_dataset.tsa.dataset_id
  table_id = "dim_hour"
  deletion_protection = false

  schema = jsonencode([
    {
      "name": "hour_id",
      "type": "integer",
      "mode": "required"
    },
    {
      "name": "hour_of_day",
      "type": "integer",
      "mode": "required"
    }
  ])
}

resource "google_bigquery_table" "dim_city" {
  dataset_id = google_bigquery_dataset.tsa.dataset_id
  table_id = "dim_city"
  deletion_protection = false

  schema = jsonencode([
    {
      "name": "city_id",
      "type": "integer",
      "mode": "required"
    },
    {
      "name": "name",
      "type": "string",
      "mode": "required"
    }
  ])
}

resource "google_bigquery_table" "dim_state" {
  dataset_id = google_bigquery_dataset.tsa.dataset_id
  table_id = "dim_state"
  deletion_protection = false

  schema = jsonencode([
    {
      "name": "state_id",
      "type": "integer",
      "mode": "required"
    },
    {
      "name": "name",
      "type": "string",
      "mode": "required"
    }
  ])
}

resource "google_bigquery_table" "city_state_bridge" {
  dataset_id = google_bigquery_dataset.tsa.dataset_id
  table_id = "city_state_bridge"
  deletion_protection = false

  schema = jsonencode([
    {
      "name": "city_id",
      "type": "integer",
      "mode": "required"
    },
    {
      "name": "state_id",
      "type": "integer",
      "mode": "required"
    }
  ])
}

resource "google_bigquery_table" "dim_airport" {
  dataset_id = google_bigquery_dataset.tsa.dataset_id
  table_id = "dim_airport"
  deletion_protection = false

  schema = jsonencode([
    {
      "name": "airport_id",
      "type": "integer",
      "mode": "required"
    },
    {
      "name": "code",
      "type": "string",
      "mode": "required"
    },
    {
      "name": "name",
      "type": "string",
      "mode": "required"
    }
  ])
}

resource "google_bigquery_table" "dim_checkpoint" {
  dataset_id = google_bigquery_dataset.tsa.dataset_id
  table_id = "dim_checkpoint"
  deletion_protection = false

  schema = jsonencode([
    {
      "name": "checkpoint_id",
      "type": "integer",
      "mode": "required"
    },
    {
      "name": "name",
      "type": "string",
      "mode": "required"
    }
  ])
}

resource "google_bigquery_table" "airport_checkpoint_bridge" {
  dataset_id = google_bigquery_dataset.tsa.dataset_id
  table_id = "airport_checkpoint_bridge"
  deletion_protection = false

  schema = jsonencode([
    {
      "name": "airport_id",
      "type": "integer",
      "mode": "required"
    },
    {
      "name": "checkpoint_id",
      "type": "integer",
      "mode": "required"
    }
  ])
}
