/**
 * Copyright 2020 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

variable "project_id" {
  description = "The ID of the project in which the dashboard will be created."
  type        = string
}

variable "region" {
  description = "The region of the functions will be created."
  type        = string
  default     = "us-central1"
}

variable "local_output_path" {
  description = "The local output directory."
  type        = string
  default     = "build"
}

provider "google" {
  project = var.project_id
  version = ">= 3.5.0"
}

resource "random_pet" "suffix" {
  length = 2
}

provider "archive" {}

resource "google_storage_bucket" "bucket_source_archives" {
    name          = "gcf_source_archives_${random_pet.suffix.id}"
    storage_class = "REGIONAL"
    location      = var.region
    force_destroy = "true"
}

resource "google_pubsub_topic" "gcs_log_pubsub_topic" {
  name = "gcs_log_pubsub_topic_${random_pet.suffix.id}"
}

resource "google_logging_project_sink" "gcs_logsink" {
  name = "gcs_pubsub_logsink"

  # Can export to pubsub, cloud storage, or bigquery
  destination = "pubsub.googleapis.com/projects/${var.project_id}/topics/${google_pubsub_topic.gcs_log_pubsub_topic.name}"

  # Log all WARN or higher severity messages relating to instances
  filter = "resource.type=\"gcs_bucket\""

  # Use a unique writer (creates a unique service account used for writing)
  unique_writer_identity = true
}

# Because our sink uses a unique_writer, we must grant that writer access to the topic.
resource "google_project_iam_binding" "topic-writer" {
  role = "roles/pubsub.publisher"

  members = [
    google_logging_project_sink.gcs_logsink.writer_identity,
  ]
}

/**
 * Cloud Functions.
 * For each function, zip up the source and upload to GCS.
 * Uploaded source is referenced in the Function deploy.
 */

// [START function-gcs-demo-block]
data "archive_file" "gcs_demo_source" {
  type        = "zip"
  source_dir  = "../gcs-demo/function_src"
  output_path = "${var.local_output_path}/gcs_demo.zip"
}

resource "google_storage_bucket_object" "gcs_demo_source" {
  name   = "gcs_demo.zip"
  bucket = google_storage_bucket.bucket_source_archives.name
  source = data.archive_file.gcs_demo_source.output_path
}

resource "google_cloudfunctions_function" "gcs_logging_function" {
  name                  = "gcs_logging_${random_pet.suffix.id}"
  project               = var.project_id
  region                = var.region
  available_memory_mb   = "256"
  entry_point           = "process_bucket_audit_log"
  runtime               = "python37"
  event_trigger {
    event_type = "google.pubsub.topic.publish"
    resource   = google_pubsub_topic.gcs_log_pubsub_topic.name
  }
  source_archive_bucket = google_storage_bucket.bucket_source_archives.name
  source_archive_object = google_storage_bucket_object.gcs_demo_source.name
  environment_variables = {
    PROJECT_ID = var.project_id
  }
}
// [END function-gcs-demo-block]


// define output variables for use downstream
output "project" {
  value = var.project_id
}
output "region" {
  value = var.region
}
output "gcs_logsink" {
  value = google_logging_project_sink.gcs_logsink.name
}
output "function_gcs_demo" {
  value = google_cloudfunctions_function.gcs_logging_function.name
}
