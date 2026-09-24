"""Token counting for the OpenAI-compatible chat context budget."""

import os
from functools import lru_cache
from pathlib import Path

# Keep the encoding tables available in offline deployments.
os.environ.setdefault(
    "TIKTOKEN_CACHE_DIR", str(Path(__file__).resolve().parent / "tokenizer_cache")
)
import tiktoken


@lru_cache(maxsize=64)
def _encoding(model: str):
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        # Third-party OpenAI-compatible model names have no registered encoding.
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(content: str, model: str = "") -> int:
    return len(_encoding(model).encode(content))


def newest_tokens(content: str, budget: int, model: str = "") -> str:
    if budget <= 0:
        return ""
    encoding = _encoding(model)
    tokens = encoding.encode(content)
    if len(tokens) <= budget:
        return content
    return encoding.decode(tokens[-budget:])
