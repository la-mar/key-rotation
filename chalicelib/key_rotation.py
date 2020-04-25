import logging
from datetime import date
from typing import Dict, Optional

import boto3
from util.iterables import query

logger = logging.getLogger(__name__)


iam = boto3.client("iam")
sts = boto3.client("sts")

CREDENTIAL_DESCRIPTIONS: Dict[str, str] = {
    "AWS_ACCOUNT_ID": "AWS account in which resources will be created",
    "AWS_ACCESS_KEY_ID": "AWS access key identifier used for Terraform executions",
    "AWS_SECRET_ACCESS_KEY": "AWS secret key used for Terraform executions",
    "AWS_IAM_ROLE": "AWS IAM role used for Terraform executions",
    "LAST_ROTATED": "Date of last AWS key rotation",
}


class RotationManager:
    _account_id: Optional[str] = None
    _previous_key_id: Optional[str] = None
    _next_key_id: Optional[str] = None

    def __init__(self, iam_username: str):
        self.iam_username = iam_username
        self.new: Dict[str, str] = {}

    def __enter__(self):
        self.create_new_credentials()
        return self

    def __exit__(self, *exc):
        if not exc:
            self.delete_previous_key()
        logger.info(f"({self.iam_username}) rotated access keys")

    @property
    def descriptions(self) -> Dict[str, str]:
        return {**CREDENTIAL_DESCRIPTIONS}

    @property
    def previous_key_id(self) -> Optional[str]:
        if self._previous_key_id is None:
            self._previous_key_id = self._fetch_access_key()
        return self._previous_key_id

    @property
    def next_key_id(self) -> Optional[str]:
        return self._next_key_id

    @property
    def account_id(self) -> str:
        if self._account_id is None:
            payload = sts.get_caller_identity()
            sts_response_code = query("ResponseMetadata.HTTPStatusCode", data=payload)

            if sts_response_code != 200:
                raise ValueError(f"({self.iam_username}) failed to fetch account id")

            self._account_id = payload["Account"]

        return self._account_id

    @property
    def oldest_key(self) -> Optional[str]:
        return self._fetch_access_key(oldest=True)

    def _fetch_access_key(self, oldest: bool = False):
        payload = iam.list_access_keys(UserName=self.iam_username)
        index = -1 if oldest else 0
        return query(f"AccessKeyMetadata.{index}.AccessKeyId", data=payload)

    def create_new_credentials(self, is_retry: bool = False) -> Dict[str, str]:
        if not self.new:
            try:
                payload = iam.create_access_key(UserName=self.iam_username)
            except iam.exceptions.LimitExceededException as e:
                logger.warning(f"({self.iam_username}) -- {e}")
                oldest = self.oldest_key
                if oldest:
                    self.delete_key(oldest)
                    logger.warning(
                        f"({self.iam_username}) retrying creating new credentials"
                    )
                    if not is_retry:  # only retry once
                        return self.create_new_credentials(is_retry=True)

            response_code = query("ResponseMetadata.HTTPStatusCode", data=payload)

            if response_code == 200:
                logger.info(f"({self.iam_username}) created new access key")
            else:
                raise ValueError(
                    f"({self.iam_username}) failed to create new access key"
                )

            access_key = payload["AccessKey"]
            self._next_key_id = access_key["AccessKeyId"]

            self.new = {
                "AWS_ACCOUNT_ID": self.account_id,
                "AWS_ACCESS_KEY_ID": access_key["AccessKeyId"],
                "AWS_SECRET_ACCESS_KEY": access_key["SecretAccessKey"],
                "AWS_IAM_ROLE": access_key["UserName"],
                "LAST_ROTATED": str(date.today()),
            }

            return self.new
        else:
            raise ValueError(f"credentials have already been generated")

    def delete_key(self, access_key_id: str):
        payload = iam.delete_access_key(
            UserName=self.iam_username, AccessKeyId=access_key_id
        )

        response_code = query("ResponseMetadata.HTTPStatusCode", data=payload)

        if response_code == 200:
            logger.info(f"({self.iam_username}) deleted old access key")
        else:
            raise ValueError(f"({self.iam_username}) failed to delete old access key")

    def delete_previous_key(self):
        if self.previous_key_id:
            result = self.delete_key(access_key_id=self.previous_key_id)
            self._previous_key_id = None
            return result
        else:
            logger.info(f"({self.iam_username}) no previous key to delete")


if __name__ == "__main__":
    import loggers
    import config as conf

    loggers.config(10)
    self = RotationManager(conf.TF_IAM_USERNAME)
    self.create_new_credentials()

    # use as context manager
    with RotationManager(conf.TF_IAM_USERNAME) as rm:
        print(rm.new)
