# Copyright 2026 Sami Maghnaoui
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

variable "billing_account" {
  type        = string
  description = "The Google Cloud Billing Account ID to bind to the disposable project."
}

variable "folder_id" {
  type        = string
  default     = ""
  description = "Optional GCP Folder ID to create the disposable project inside."
}

variable "org_id" {
  type        = string
  default     = ""
  description = "Optional GCP Org ID to create the disposable project inside if folder_id is not provided."
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "The default GCP region for resource provisioning."
}

variable "session_id" {
  type        = string
  default     = "default-session"
  description = "Unique ID for the active session. Changing this triggers a project recreation."
}

variable "enabled_apis" {
  type = list(string)
  default = [
    "cloudtrace.googleapis.com",
    "monitoring.googleapis.com",
    "aiplatform.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "cloudbuild.googleapis.com"
  ]
  description = "List of GCP APIs to enable on the generated project."
}


