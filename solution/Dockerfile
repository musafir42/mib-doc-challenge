FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md uv.lock /app/
COPY src /app/src

RUN pip install --no-cache-dir .

COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh

ENTRYPOINT ["/app/run.sh"]
