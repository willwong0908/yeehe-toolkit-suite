FROM alpine:3.22
RUN apk add --no-cache python3 py3-fastapi py3-httpx py3-pip ca-certificates && python3 -m venv --system-site-packages /opt/venv && /opt/venv/bin/pip install --no-cache-dir uvicorn==0.35.0
RUN apk add --no-cache py3-cryptography
WORKDIR /srv
COPY server.py direct_auth.py ./
CMD ["/opt/venv/bin/python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
