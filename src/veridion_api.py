"""Thin client for the Veridion API, with an on-disk cache to avoid re-spending quota.

Endpoints/payloads to be filled in from the official docs once the account is set up.
"""
import hashlib
import json
import os

import requests
from dotenv import load_dotenv

from src.config import CACHE

load_dotenv()
API_KEY = os.getenv("VERIDION_API_KEY")
BASE_URL = os.getenv("VERIDION_API_BASE_URL")


def _cache_path(endpoint: str, payload: dict):
    key = hashlib.sha256(json.dumps([endpoint, payload], sort_keys=True).encode()).hexdigest()
    return CACHE / f"{key}.json"


def post(endpoint: str, payload: dict) -> dict:
    """POST to the API, returning a cached response if this exact request was made before."""
    path = _cache_path(endpoint, payload)
    if path.exists():
        return json.loads(path.read_text())
    if not (API_KEY and BASE_URL):
        raise RuntimeError("Set VERIDION_API_KEY and VERIDION_API_BASE_URL in .env")
    # TODO: confirm auth header name and endpoint paths in the API docs.
    resp = requests.post(f"{BASE_URL}{endpoint}", json=payload, headers={"x-api-key": API_KEY}, timeout=30)
    resp.raise_for_status()
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(resp.json()))
    return resp.json()
