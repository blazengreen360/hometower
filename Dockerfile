FROM python:3.12-slim AS base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
RUN mkdir -p /data/attachments && chown -R appuser:appgroup /app /data
COPY . .
USER appuser
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
