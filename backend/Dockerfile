FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Optional Kronos forecaster: docker build --build-arg INSTALL_KRONOS=1 .
# Adds CPU PyTorch (~1 GB image); leave off for small free-tier instances.
ARG INSTALL_KRONOS=0
RUN if [ "$INSTALL_KRONOS" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/* && \
      ./scripts/install_kronos.sh --cpu && rm -rf /root/.cache/pip; \
    fi

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
