terraform {
  required_version = ">= 1.3.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "google" {
  region = var.region
}

# Generate a pinned pet name for the project
resource "random_pet" "project_name" {
  prefix = "clinic-ep2"
  length = 2
  keepers = {
    session_id = var.session_id
  }
}

# Create the GCP Project
resource "google_project" "project" {
  name            = random_pet.project_name.id
  project_id      = random_pet.project_name.id
  billing_account = var.billing_account
  folder_id       = var.folder_id != "" ? var.folder_id : null
  org_id          = var.folder_id == "" && var.org_id != "" ? var.org_id : null
}

# Enable specified APIs for the project
resource "google_project_service" "services" {
  for_each           = toset(var.enabled_apis)
  project            = google_project.project.project_id
  service            = each.value
  disable_on_destroy = false
}

# Create the Google Cloud Monitoring Dashboard for Playback IQ
resource "google_monitoring_dashboard" "playback_iq_dashboard" {
  project = google_project.project.project_id
  dashboard_json = jsonencode({
    displayName = "Playback IQ Token Analytics"
    gridLayout = {
      columns = "2"
      widgets = [
        {
          title = "LLM Token Consumption by Operation"
          xyChart = {
            dataSets = [
              {
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"workload.googleapis.com/gen_ai.client.token.usage\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_DELTA"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["metric.label.operation"]
                    }
                  }
                }
                plotType = "STACKED_BAR"
              }
            ]
          }
        },
        {
          title = "LLM Token Consumption by Type (Input/Output)"
          xyChart = {
            dataSets = [
              {
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"workload.googleapis.com/gen_ai.client.token.usage\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_DELTA"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["metric.label.token_type"]
                    }
                  }
                }
                plotType = "LINE"
              }
            ]
          }
        },
        {
          title = "Total Tokens Consumed (Selected Period)"
          scorecard = {
            timeSeriesQuery = {
              timeSeriesFilter = {
                filter = "metric.type=\"workload.googleapis.com/gen_ai.client.token.usage\""
                aggregation = {
                  alignmentPeriod    = "3600s"
                  perSeriesAligner   = "ALIGN_DELTA"
                  crossSeriesReducer = "REDUCE_SUM"
                  groupByFields      = ["metric.label.token_type"]
                }
              }
            }
            sparkChartView = {
              sparkChartType = "SPARK_LINE"
            }
          }
        }
      ]
    }
  })

  depends_on = [google_project_service.services]
}


# ─── Artifact Registry ─────────────────────────────────────────────────────────
resource "google_artifact_registry_repository" "repo" {
  project       = google_project.project.project_id
  location      = var.region
  repository_id = "playback-iq-repo"
  description   = "Docker repository for Playback IQ"
  format        = "DOCKER"
  depends_on    = [google_project_service.services]
}

# ─── Service Account & IAM Role Bindings ──────────────────────────────────────
resource "google_service_account" "sa" {
  project      = google_project.project.project_id
  account_id   = "playback-iq-runner"
  display_name = "Playback IQ Runner"
}

resource "google_project_iam_member" "vertex_user" {
  project = google_project.project.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.sa.email}"
}

resource "google_project_iam_member" "trace_agent" {
  project = google_project.project.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.sa.email}"
}

resource "google_project_iam_member" "metric_writer" {
  project = google_project.project.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.sa.email}"
}

resource "google_project_iam_member" "user_owner" {
  project = google_project.project.project_id
  role    = "roles/owner"
  member  = "user:luis@luissala.altostrat.com"
}

resource "google_project_iam_member" "compute_storage_admin" {
  project = google_project.project.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_project.project.number}-compute@developer.gserviceaccount.com"
}

resource "google_project_iam_member" "compute_registry_writer" {
  project = google_project.project.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_project.project.number}-compute@developer.gserviceaccount.com"
}

resource "google_project_iam_member" "cloudbuild_registry_writer_legacy" {
  project = google_project.project.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_project.project.number}@cloudbuild.gserviceaccount.com"
}

resource "google_project_iam_member" "cloudbuild_registry_writer_service" {
  project = google_project.project.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:service-${google_project.project.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com"
}

# ─── Google Cloud Run Service ──────────────────────────────────────────────────
resource "google_cloud_run_v2_service" "cloud_run" {
  name     = "playback-iq"
  project  = google_project.project.project_id
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.sa.email
    containers {
      image = "${var.region}-docker.pkg.dev/${google_project.project.project_id}/${google_artifact_registry_repository.repo.repository_id}/playback-iq:latest"

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "true"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = google_project.project.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = "global"
      }
      env {
        name  = "OTEL_ENABLED"
        value = "true"
      }
      env {
        name  = "TRACE_EXPORTER"
        value = "gcp"
      }
      env {
        name  = "AUDIO_CACHE"
        value = "false"
      }

      ports {
        container_port = 8080
      }
    }
  }

  depends_on = [
    google_project_service.services,
    google_artifact_registry_repository.repo,
    google_project_iam_member.vertex_user,
    google_project_iam_member.trace_agent,
    google_project_iam_member.metric_writer
  ]
}

# Override the Domain Restricted Sharing organization policy at the project level to allow public internet sharing
resource "google_project_organization_policy" "override_drs" {
  project    = google_project.project.project_id
  constraint = "constraints/iam.allowedPolicyMemberDomains"

  list_policy {
    allow {
      all = true
    }
  }
}

# Allow public unauthenticated invocation access to the service
resource "google_cloud_run_v2_service_iam_member" "noauth" {
  project  = google_project.project.project_id
  location = google_cloud_run_v2_service.cloud_run.location
  name     = google_cloud_run_v2_service.cloud_run.name
  role     = "roles/run.invoker"
  member   = "allUsers"

  depends_on = [
    google_cloud_run_v2_service.cloud_run,
    google_project_organization_policy.override_drs
  ]
}


# Outputs
output "project_id" {
  value       = google_project.project.project_id
  description = "The dynamically generated GCP Project ID."
}

output "cloud_run_url" {
  value       = google_cloud_run_v2_service.cloud_run.uri
  description = "The public URL of the deployed Cloud Run service."
}
