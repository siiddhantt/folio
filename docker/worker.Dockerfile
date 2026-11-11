FROM folio-docling:2.148.0 AS worker
ENV PYTHONPATH=/app/src TIKTOKEN_CACHE_DIR=/opt/tokenizers
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock && pip check
RUN python -c "import tiktoken; tiktoken.get_encoding('o200k_base')"
COPY src ./src
ENTRYPOINT []
CMD ["python", "-m", "folio", "worker"]

FROM worker AS verification
COPY requirements-dev.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements-dev.lock && pip check
COPY pyproject.toml ./
COPY tests ./tests
CMD ["python", "-m", "pytest", "-q"]
