FROM python:3.12-slim

WORKDIR /app

# Offline image: bake dependencies at build time only.
COPY pyproject.toml README.md /app/
COPY src /app/src

RUN pip install --no-cache-dir .

COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh

ENTRYPOINT ["/app/run.sh"]
