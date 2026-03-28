# Static site generator for benchmark results (stdlib only).
FROM python:3.12-slim

WORKDIR /app
COPY generate_site.py .

ENTRYPOINT ["python", "/app/generate_site.py"]
