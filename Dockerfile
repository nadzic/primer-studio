FROM ghcr.io/astral-sh/uv:python3.11-bookworm

# Base image for building Python 3.11 apps with uv (faster Python package installer and manager)
WORKDIR /app

# Install Python deps first for better cache
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

# Copy source
COPY . .

ENV PYTHONPATH=/app
ENV PORT=8000

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]