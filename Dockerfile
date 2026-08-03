FROM python:3.12-slim

WORKDIR /app

# Install dependencies via pip (avoids hatchling build issues with uv run)
COPY pyproject.toml .
RUN pip install --no-cache-dir $(python3 -c "import tomllib; print(' '.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))")

# Copy application
COPY . .

EXPOSE 8000

ENV PORT=8000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
