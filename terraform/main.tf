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

resource "google_pubsub_subscription" "create_pdf_subscription" {
  name = "create-pdf-subscription"
  topic = google_pubsub_topic.create_pdf_topic.name
}


# Cloud Storage
resource "google_storage_bucket" "tsa_throughput" {
  name = var.bucket
  location = var.location
  force_destroy = true

  provisioner "local-exec" {
    command = "${path.module}/../scripts/deploy_function_scrape.sh"
  }

  provisioner "local-exec" {
    command = "${path.module}/../scripts/deploy_function_create.sh"
  }
}

resource "google_storage_bucket_object" "source_folder" {
  name = "${var.source_pdf_prefix}/"
  content = " "
  bucket = google_storage_bucket.tsa_throughput.name
}

resource "google_storage_notification" "pdf_notification" {
  bucket = google_storage_bucket.tsa_throughput.name
  topic = google_pubsub_topic.pdf_topic.id
  payload_format = "JSON_API_V1"
  event_types = ["OBJECT_FINALIZE"]
  object_name_prefix = "${var.source_pdf_prefix}/"

  depends_on = [ google_pubsub_topic_iam_binding.binding ]
}


# Networking
resource "google_vpc_access_connector" "serverless_connector" {
  name = "serverless-connector"
  region = var.region
  network = "default"
  ip_cidr_range = "10.8.0.0/28"
}


# IAM
resource "google_service_account" "scheduler_sa" {
  account_id = "scheduler-sa"
  display_name = "Scheduler Service Account"
}

resource "google_project_iam_member" "scheduler_invoker" {
  project = var.project_id
  role = "roles/cloudfunctions.invoker"
  member = "serviceAccount:${google_service_account.scheduler_sa.email}"
}

data "google_storage_project_service_account" "gcs_account" {}

resource "google_pubsub_topic_iam_binding" "binding" {
  topic = google_pubsub_topic.pdf_topic.id
  role = "roles/pubsub.publisher"
  members = ["serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"]
}


# Cloud Functions
resource "google_cloudfunctions_function" "scrape_pdf" {
  name = "scrape-pdf"
  region = var.region
  description = "scrape pdf from TSA FOIA"
  runtime = "python39"
  available_memory_mb = 512
  timeout = 180
  source_archive_bucket = google_storage_bucket.tsa_throughput.name
  source_archive_object = "cloud-function/scrape_pdf.zip"
  entry_point = "process_pdf"
  vpc_connector = google_vpc_access_connector.serverless_connector.name
  vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"

  environment_variables = {
    PROJECT = var.project_id
    REGION = var.region
    BUCKET = var.bucket
    PROCESSED_DATES = var.processed_dates
    SOURCE_PDF_PREFIX = var.source_pdf_prefix
  }

  trigger_http = true

  depends_on = [ google_project_iam_member.scheduler_invoker ]
}

resource "google_cloudfunctions_function" "create_pdf" {
  name = "create-pdf"
  region = var.region
  description = "create pdfs by date"
  runtime = "python39"
  available_memory_mb = 512
  timeout = 540
  source_archive_bucket = google_storage_bucket.tsa_throughput.name
  source_archive_object = "cloud-function/create_pdf.zip"
  entry_point = "process_pdf_dates"
  vpc_connector = google_vpc_access_connector.serverless_connector.name
  vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"

  environment_variables = {
    PROJECT = var.project_id
    TOPIC = google_pubsub_topic.create_pdf_topic.name
  }

  event_trigger {
    event_type = "google.pubsub.topic.publish"
    resource = google_pubsub_topic.pdf_topic.name
  }
}


# Cloud Scheduler
resource "google_cloud_scheduler_job" "scrape_pdf_job" {
  name = "scrape-pdf-job"
  region = var.region
  description = "job to scrape pdf from TSA FOIA"

  schedule = "0 0 * * 4"
  time_zone = "Etc/UTC"

  http_target {
    http_method = "POST"
    uri = google_cloudfunctions_function.scrape_pdf.https_trigger_url
    oidc_token {
      service_account_email = google_service_account.scheduler_sa.email
    }
  }
}
