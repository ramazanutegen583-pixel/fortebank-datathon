FROM python:3.12-slim

WORKDIR /app
COPY server/requirements.txt /app/server/requirements.txt
RUN python -m pip install --no-cache-dir -r server/requirements.txt
COPY . /app
RUN if [ -f vision/requirements.txt ]; then python -m pip install --no-cache-dir -r vision/requirements.txt; fi \
    && useradd --uid 10001 --create-home review \
    && mkdir -p /app/runtime \
    && chown -R review:review /app/runtime

USER review
ENV APP_HOST=0.0.0.0 APP_PORT=8000 APP_RUNTIME_DIR=/app/runtime APP_TEST_MODE=0
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["python", "-m", "server"]
