from typing import Dict, Optional

import pandas as pd
from starlette.config import Config
from starlette.datastructures import Secret
from util.toml import project, version

""" Optional Pandas display settings """
pd.options.display.max_rows = 1000
pd.set_option("display.float_format", lambda x: "%.2f" % x)
pd.set_option("large_repr", "truncate")
pd.set_option("precision", 2)

conf: Config = Config(".env")

ENVIRONMENT_MAP: Dict[str, str] = {
    "production": "prod",
    "staging": "stage",
    "development": "dev",
}

APP_NAME: str = conf("APP_NAME", cast=str)
ENV: str = conf("ENV", cast=str, default="lambda")
HOST_NAME: str = conf("HOST_NAME", cast=str, default="lambda")
TESTING: bool = conf("TESTING", cast=bool, default=False)
DEBUG: bool = conf("DEBUG", cast=bool, default=False)

""" Logging """
LOG_LEVEL: str = conf("LOG_LEVEL", cast=str, default="20")
LOG_FORMAT: str = conf("LOG_FORMAT", cast=str, default="json")
LOG_HANDLER: str = conf("LOG_HANDLER", cast=str, default="colorized")


DATADOG_ENABLED: bool = conf("DATADOG_ENABLED", cast=bool, default=False)

DATADOG_API_KEY: Optional[Secret] = conf(
    "DATADOG_API_KEY",
    cast=Secret,
    default=conf("DD_API_KEY", cast=Secret, default=None),
)

DATADOG_APP_KEY: Optional[Secret] = conf(
    "DATADOG_APP_KEY",
    cast=Optional[Secret],
    default=conf("DD_APP_KEY", cast=Secret, default=None),
)

DATADOG_DEFAULT_TAGS: Dict[str, Optional[str]] = {
    "environment": ENVIRONMENT_MAP.get(ENV, ENV),
    "service_name": project,
    "service_version": version,
}


TF_TOKEN: Optional[Secret] = conf("TF_TOKEN", cast=Secret)
TF_ORG_NAME: str = conf("TF_ORG_NAME", cast=str)
TF_IAM_USERNAME: str = conf("TF_IAM_USERNAME", cast=str)
