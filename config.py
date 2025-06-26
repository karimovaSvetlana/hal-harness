from typing import Optional
from pydantic import BaseModel, Field, conint, confloat
import yaml


# --- Pydantic models ---

class APISettings(BaseModel):
    token: str
    url: str


class ModelParameters(BaseModel):
    max_tokens: conint(ge=1)
    temperature: confloat(ge=0.0, le=1.0)
    top_p: confloat(ge=0.0, le=1.0)
    max_retries: conint(ge=0)
    time_sleep: conint(ge=0)
    timeout: conint(ge=200)
    scope: str
    profanity_check: bool = False


class ModelSettings(BaseModel):
    api: APISettings
    name: str
    parameters: ModelParameters


class Config(BaseModel):
    model: ModelSettings


# --- Load function ---

def load_config(path: str = "config.yaml") -> Config:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return Config(**raw)
