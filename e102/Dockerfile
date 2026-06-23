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

# Stage 1: Build the React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# Install dependencies
COPY frontend/package*.json ./
RUN npm ci

# Copy source and build
COPY frontend/ ./
RUN npm run build

# Stage 2: Run the FastAPI backend
FROM python:3.12-slim
WORKDIR /app

# Copy python dependency files and install via standard PyPI using uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv pip install --system --no-cache-dir -r pyproject.toml --index-url https://pypi.org/simple

# Copy backend source and data directories
COPY src/ ./src
COPY data/ ./data

# Copy built frontend assets from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Configure environment variables
EXPOSE 8080
ENV PORT=8080

# Command to boot the server
CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8080"]
