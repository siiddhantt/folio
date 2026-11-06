# This experiment targets the same Linux amd64 CPU environment for both parsers.
FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    TOKENIZERS_PARALLELISM=false \
    DOCLING_DEVICE=cpu \
    DOCLING_NUM_THREADS=1 \
    DOCLING_ARTIFACTS_PATH=/models \
    DOCLING_DEBUG_PROFILE_PIPELINE_TIMINGS=true \
    HF_HUB_DISABLE_TELEMETRY=1

# Use the base image's Debian mirrors; record resolved system packages below.
# The dated snapshot mirror repeatedly stalled during the initial build.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng libglib2.0-0 libgl1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/experiment
COPY constraints.txt run.py test_normalization.py ./

# Direct, hash-pinned CPU wheels prevent the resolver from pulling CUDA packages.
RUN python -m pip install --no-cache-dir -c constraints.txt \
      'torch @ https://download.pytorch.org/whl/cpu/torch-2.11.0%2Bcpu-cp312-cp312-manylinux_2_28_x86_64.whl#sha256=f82e2ae20c1545bb03997d1cc3143d94e14b800038669ee1aca45808a9acc338' \
      'torchvision @ https://download.pytorch.org/whl/cpu/torchvision-0.26.0%2Bcpu-cp312-cp312-manylinux_2_28_x86_64.whl#sha256=cf547dc0975eb40bc3249be4ccbeb736597d2c3ece305b1c4e5b7a5dd7363567' \
      'docling==2.148.0' 'transformers==5.20.2' \
    && python -m pip check \
    && python -c "import importlib.metadata as m, torch; assert torch.version.cuda is None; assert not any(d.metadata['Name'].lower().startswith('nvidia-') for d in m.distributions())" \
    && python -m pip freeze --all > pip-freeze.txt \
    && dpkg-query -W > dpkg-versions.txt \
    && python -m unittest test_normalization

# Model transfer is a separate build step and never included in parse timings.
RUN python run.py --prefetch --models /models

ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
ENTRYPOINT ["python", "/opt/experiment/run.py"]
