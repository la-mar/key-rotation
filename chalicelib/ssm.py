import logging
import os

import boto3

ssm = boto3.client("ssm")

logger = logging.getLogger("ssm")
logger.setLevel(20)


def ssm_load_config(ssm_parameter_path: str):
    """ Load variables at the specified path from the SSM Parameter Store """

    try:
        # Get all parameters for this app
        param_details = ssm.get_parameters_by_path(
            Path=ssm_parameter_path, Recursive=False, WithDecryption=True
        )

        # Loop through the returned parameters and populate the ConfigParser
        if "Parameters" in param_details and len(param_details.get("Parameters")) > 0:
            for param in param_details.get("Parameters"):
                name = (
                    param["Name"]
                    .replace(ssm_parameter_path, "")
                    .replace("/", "")
                    .upper()
                )
                value = param["Value"]
                os.environ[name] = value
                logger.debug(f"SSM: Overwriting variable {name}")

    except Exception as e:
        logger.exception(f"Encountered an error loading config from SSM -- {e}")


try:
    app_name = os.environ["APP_NAME"]
except KeyError as ke:
    logger.error("APP_NAME not found in environment")
    raise ke


ssm_load_config("/" + app_name)
