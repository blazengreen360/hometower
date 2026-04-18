FROM python:3.12-slim AS base
WORKDIR /app
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
COPY --chown=appuser:appgroup requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt
COPY --chown=appuser:appgroup . .
RUN mkdir -p /data/attachments && chown -R appuser:appgroup /data
USER appuser
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
