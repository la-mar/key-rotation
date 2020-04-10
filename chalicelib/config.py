from typing import Dict, Optional

import pandas as pd
from sqlalchemy.engine.url import URL
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


""" database """
DATABASE_DRIVER: str = conf("DATABASE_DRIVER", cast=str, default="postgresql+asyncpg")
DATABASE_USERNAME: str = conf("DATABASE_USERNAME", cast=str, default=None)
DATABASE_PASSWORD: Secret = conf("DATABASE_PASSWORD", cast=Secret, default=None)
DATABASE_HOST: str = conf("DATABASE_HOST", cast=str, default="localhost")
DATABASE_PORT: int = conf("DATABASE_PORT", cast=int, default=5432)
DATABASE_NAME: str = conf("DATABASE_NAME", cast=str)
DATABASE_POOL_SIZE_MIN: int = conf("DATABASE_POOL_SIZE_MIN", cast=int, default=2)
DATABASE_POOL_SIZE_MAX: int = conf(
    "DATABASE_POOL_SIZE_MIN", cast=int, default=DATABASE_POOL_SIZE_MIN
)


DATABASE_URI = URL(
    drivername=DATABASE_DRIVER,
    username=DATABASE_USERNAME,
    password=DATABASE_PASSWORD,
    host=DATABASE_HOST,
    port=DATABASE_PORT,
    database=DATABASE_NAME,
)

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
