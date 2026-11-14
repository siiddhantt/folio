"""Pinned tokenizer assets: fetched at build/setup time, loaded offline at runtime."""

import hashlib
import os
from functools import lru_cache
from pathlib import Path

import httpx
from tokenizers import Tokenizer

MODEL_ID = "deepseek/deepseek-v4.1-flash-1017"
TOKENIZER_NAME = "deepseek-v4.1-flash-1017"
REVISION = "08c8657f02291e11b6f6b63e0e16014f8e748518"
SHA256 = "c90dfa01249db1be4245780a052ede752e1361c612ac6d08e2bdada7d599476b"
ASSETS = {
    "tokenizer.json": SHA256,
    "LICENSE": "f2c6c602815669d292889e5be8c802f2ed950653b77999b1584e8e6aed25d040",
}
SOURCE = f"https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/resolve/{REVISION}"


def asset_directory() -> Path:
    return Path(os.environ.get("FOLIO_TOKENIZER_DIRECTORY", ".local/tokenizers")) / TOKENIZER_NAME


@lru_cache(maxsize=2)
def _load(path: Path) -> Tokenizer:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("Tokenizer checksum mismatch")
    return Tokenizer.from_str(data.decode("utf-8"))


def count_tokens(text: str) -> int:
    tokenizer = _load((asset_directory() / "tokenizer.json").resolve())
    return len(tokenizer.encode(text, add_special_tokens=False).ids)


def install() -> None:
    directory = asset_directory()
    directory.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=120, trust_env=False) as client:
        for filename, expected in ASSETS.items():
            response = client.get(f"{SOURCE}/{filename}")
            response.raise_for_status()
            if hashlib.sha256(response.content).hexdigest() != expected:
                raise ValueError(f"Checksum mismatch: {filename}")
            (directory / filename).write_bytes(response.content)


if __name__ == "__main__":
    install()
