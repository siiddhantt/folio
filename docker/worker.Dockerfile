ARG DOCLING_IMAGE=folio-docling:2.148.0
FROM scratch AS wheels

FROM ${DOCLING_IMAGE} AS worker
ARG PIP_NO_INDEX=0
ENV PYTHONPATH=/app/src TIKTOKEN_CACHE_DIR=/opt/tokenizers FOLIO_TOKENIZER_DIRECTORY=/opt/tokenizers
WORKDIR /app
COPY requirements.lock ./
RUN --mount=type=bind,from=wheels,target=/wheels \
    pip install --no-cache-dir --find-links=/wheels --require-hashes -r requirements.lock && pip check
RUN python -c "import tiktoken; tiktoken.get_encoding('o200k_base'); tiktoken.get_encoding('cl100k_base')"
COPY src ./src
RUN python -c "from folio.ai.deepseek import install; install()"
ENTRYPOINT []
CMD ["python", "-m", "folio", "worker"]

FROM worker AS verification
COPY requirements-dev.lock ./
RUN --mount=type=bind,from=wheels,target=/wheels \
    pip install --no-cache-dir --find-links=/wheels --require-hashes -r requirements-dev.lock && pip check
COPY pyproject.toml ./
COPY tests ./tests
COPY notebooks/*.py ./notebooks/
CMD ["python", "-m", "pytest", "-q"]
