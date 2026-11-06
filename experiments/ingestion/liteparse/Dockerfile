FROM python:3.12.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata \
    OMP_NUM_THREADS=2

# Native Python/Rust wheel; no Node or hosted service. English OCR assets are
# installed during image creation, outside timed parses. Debian's English
# traineddata is recorded by checksum by the runner (not silently downloaded).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-writer tesseract-ocr tesseract-ocr-eng \
        fonts-dejavu-core fonts-liberation2 fontconfig libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# PyPI python-v2.18.0 / upstream commit 40abdffd435403ec30341b30511dfb8daba5bf5a.
# This wheel targets Linux amd64, matching the comparison host.
RUN python -m pip install --no-cache-dir --only-binary=:all: \
    "liteparse @ https://files.pythonhosted.org/packages/6b/57/c4ca6dfce5a18f5ca5a77c2f7cdb7a96f3c042ff55b5b5998b246cdca3e6/liteparse-2.18.0-cp310-abi3-manylinux_2_28_x86_64.whl#sha256=20c75c090a9266d3214e1e66eda84d8adc636bfb4c4b1907800bd0a149164c2d" \
    && python -c "from liteparse import LiteParse; LiteParse(ocr_language='eng')" \
    && test -s "$TESSDATA_PREFIX/eng.traineddata"

WORKDIR /app
COPY run.py /app/run.py
ENTRYPOINT ["python", "/app/run.py"]
CMD ["--fixtures", "/fixtures", "--results", "/results/liteparse"]
