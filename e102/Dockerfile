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
