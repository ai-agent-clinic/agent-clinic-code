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

"""OpenTelemetry bootstrap — call setup_telemetry(app) once at startup."""

import os

from opentelemetry import trace, metrics
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

# Define a global meter
_meter = metrics.get_meter("playback-iq")

# Counter for token consumption (OTel Semantic GenAI Convention)
_token_usage_counter = _meter.create_counter(
    name="gen_ai.client.token.usage",
    description="Number of input and output tokens consumed by GenAI models",
    unit="1",
)


def record_tokens(count: int, token_type: str, model: str, operation: str) -> None:
    """Record GenAI token usage metrics."""
    if count > 0:
        _token_usage_counter.add(
            count,
            {
                "token_type": token_type,
                "gen_ai.response.model": model,
                "operation": operation,
            }
        )


def setup_telemetry(app) -> None:
    """Wire up telemetry (tracing & metrics) and auto-instrument the FastAPI app.

    Supports multiple exporters based on TRACE_EXPORTER env var:
    - 'otlp' / 'jaeger': OTLP/HTTP to Jaeger (default)
    - 'gcp' / 'gcp-trace': Google Cloud Trace & Cloud Monitoring
    - 'console': ConsoleExporter for both Tracing & Metrics (local diagnostics)
    """
    exporter_type = os.getenv("TRACE_EXPORTER", "otlp").lower()
    service_name = os.getenv("OTEL_SERVICE_NAME", "playback-iq")

    resource = Resource(attributes={"service.name": service_name})

    # ─── Tracing Provider Setup ────────────────────────────────────────────────
    trace_provider = TracerProvider(resource=resource)

    if exporter_type in ("gcp", "gcp-trace"):
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
        gcp_project = os.getenv("GOOGLE_CLOUD_PROJECT")
        trace_exporter = CloudTraceSpanExporter(project_id=gcp_project)
        trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    elif exporter_type == "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        trace_exporter = ConsoleSpanExporter()
        trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    else:
        # Default to OTLP/HTTP (Jaeger)
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        base = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
        trace_exporter = OTLPSpanExporter(endpoint=f"{base}/v1/traces")
        trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))

    trace.set_tracer_provider(trace_provider)

    # ─── Metrics Provider Setup ───────────────────────────────────────────────
    metric_readers = []

    if exporter_type in ("gcp", "gcp-trace"):
        from opentelemetry.exporter.cloud_monitoring import CloudMonitoringMetricsExporter
        metrics_exporter = CloudMonitoringMetricsExporter()
        metric_readers.append(
            PeriodicExportingMetricReader(metrics_exporter, export_interval_millis=60000)
        )
    elif exporter_type == "console":
        from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
        metrics_exporter = ConsoleMetricExporter()
        # Fast 10s reporting for local debugging
        metric_readers.append(
            PeriodicExportingMetricReader(metrics_exporter, export_interval_millis=10000)
        )

    meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
    metrics.set_meter_provider(meter_provider)

    FastAPIInstrumentor.instrument_app(app)


