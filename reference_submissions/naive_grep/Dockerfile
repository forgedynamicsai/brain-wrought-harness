FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY entrypoint.py /app/entrypoint.py

# No pip install — stdlib only; ripgrep is the only external dep and it's
# installed above.  Keeps the image under 150 MB.

ENTRYPOINT ["python", "/app/entrypoint.py"]
