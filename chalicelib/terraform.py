import logging
from enum import Enum
from typing import Dict, Optional, Union

import boto3
import config as conf
import httpx
import pandas as pd

logger = logging.getLogger(__name__)

TF_ORG_NAME: str = "deo"
IAM_TF_USERNAME: str = "terraform-cloud"

BASE_URL = httpx.URL("https://app.terraform.io/api/v2/")

WORKSPACE_URL = BASE_URL.join(f"organizations/{TF_ORG_NAME}/workspaces")
VARS_URL = BASE_URL.join("vars")

HEADERS = {
    "Authorization": f"Bearer {conf.TF_TOKEN}",
    "Content-Type": "application/vnd.api+json",
}


class VarCategory(str, Enum):
    TF = "terraform"
    ENV = "env"


class EntityType(str, Enum):
    VAR = "vars"
    WS = "workspaces"


def get_workspaces() -> pd.DataFrame:
    logger.debug(f"({TF_ORG_NAME}) fetching workspaces: {WORKSPACE_URL}")
    response = httpx.get(WORKSPACE_URL, headers=HEADERS)
    workspaces = pd.DataFrame(response.json()["data"])  # type: ignore
    attrs = pd.DataFrame(workspaces.attributes.values.tolist())
    workspaces = (
        workspaces.loc[:, ["id"]]
        .join(
            attrs.loc[
                :,
                [
                    "name",
                    "auto-apply",
                    "vcs-repo-identifier",
                    "working-directory",
                    "allow-destroy-plan",
                    "terraform-version",
                    "locked",
                    "latest-change-at",
                    "created-at",
                ],
            ]
        )
        .rename(columns={"id": "workspace_id", "name": "workspace_name"})
        .set_index("workspace_id")
    )
    logger.debug(f"({TF_ORG_NAME}) found {workspaces.shape[0]} workspaces")
    return workspaces


def get_variables() -> pd.DataFrame:
    logger.debug(f"({TF_ORG_NAME}) fetching variables: {VARS_URL}")
    response = httpx.get(VARS_URL, headers=HEADERS)
    variables = pd.DataFrame(response.json()["data"])  # type: ignore
    attrs = pd.DataFrame(variables.attributes.values.tolist())
    relationships = pd.DataFrame(
        [x["configurable"]["data"] for x in variables.relationships.values.tolist()]
    )

    variables = (
        variables.loc[:, ["id"]]
        .join(relationships.id.rename("workspace_id"))
        .join(attrs)
    )

    variables = (
        variables.set_index("workspace_id")
        .join(get_workspaces().loc[:, ["workspace_name"]])
        .rename(columns={"id": "variable_id"})
        .reset_index()
        .set_index(["workspace_name", "key"])
        .loc[
            :,
            [
                "value",
                "sensitive",
                "category",
                "hcl",
                "workspace_id",
                "variable_id",
                "created-at",
                "description",
            ],
        ]
    )
    logger.debug(f"({TF_ORG_NAME}) found {variables.shape[0]} variables")
    return variables


iam = boto3.client("iam")
sts = boto3.client("sts")

# get current access key
current_access_key_id = iam.list_access_keys(UserName=IAM_TF_USERNAME)[
    "AccessKeyMetadata"
][0]["AccessKeyId"]

# make new access key
new_credentials = iam.create_access_key(UserName=IAM_TF_USERNAME)

response_code = new_credentials["ResponseMetadata"]["HTTPStatusCode"]

if response_code == 200:
    logger.info(f"({IAM_TF_USERNAME}) created new access key")
else:
    logger.error(f"({IAM_TF_USERNAME}) failed to create new access key")

access_key = new_credentials["AccessKey"]

sts_response = sts.get_access_key_info(AccessKeyId=access_key["AccessKeyId"])
sts_response = new_credentials["ResponseMetadata"]["HTTPStatusCode"]
if sts_response != 200:
    logger.error(f"({IAM_TF_USERNAME}) failed to fetch account id")

credentials = {
    "AWS_ACCOUNT_ID": sts_response["Account"],
    "AWS_ACCESS_KEY_ID": access_key["AccessKeyId"],
    "AWS_SECRET_ACCESS_KEY": access_key["SecretAccessKey"],
    "AWS_IAM_ROLE": access_key["UserName"],
    "LAST_ROTATED": pd.Timestamp.now().date(),
}


var_levels = {
    "AWS_ACCOUNT_ID": "AWS account in which resources will be created",
    "AWS_ACCESS_KEY_ID": "AWS access key identifier used for Terraform executions",
    "AWS_SECRET_ACCESS_KEY": "AWS secret key used for Terraform executions",
    "AWS_IAM_ROLE": "AWS IAM role used for Terraform executions",
    "LAST_ROTATED": "Date of last AWS key rotation",
}

variables = get_variables()

envs = variables.loc[variables.category == "env"].drop(columns=["created-at"])

expanded_index = envs.index.set_levels(levels=list(var_levels.keys()), level="key")
envs = envs.reindex(index=expanded_index)

creds = (
    pd.DataFrame(data=credentials, index=envs.index.levels[0])
    .reset_index()
    .melt(id_vars="workspace_name", var_name="key")
    .set_index(["workspace_name", "key"])
    .sort_index()
)

envs = creds.combine_first(envs)
envs.head(50)

envs.workspace_id = (
    envs.sort_values("workspace_id")
    .workspace_id.groupby(level=0)
    .fillna(method="ffill")
)


envs = envs.reset_index(level=1, drop=False).set_index("key", append=True, drop=False)
envs.description = envs.key.replace(var_levels)
envs.value = envs.key.replace(credentials)

envs = envs.drop(columns=["key", "description"])
envs["category"] = VarCategory.ENV.value
envs["hcl"] = False
envs["sensitive"] = True
envs.loc[pd.IndexSlice[:, "AWS_IAM_ROLE"], "sensitive"] = False
envs.loc[pd.IndexSlice[:, "LAST_ROTATED"], "sensitive"] = False


class TFVar:
    def __init__(
        self,
        key: str,
        value: str,
        description: str,
        category: VarCategory,
        hcl: bool,
        sensitive: bool,
        variable_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ):
        self.key = key
        self.value = value
        self.description = description
        self.category = category
        self.hcl = hcl
        self.sensitive = sensitive

        id_count = sum([variable_id is not None, workspace_id is not None])

        if id_count > 1:
            raise ValueError(f"Cant specify both variable_id and workspace_id")
        elif id_count < 1:
            raise ValueError(f"Must specify one of [variable_id, workspace_id]")

        self._workspace_id: Optional[str] = self.validate_id(
            workspace_id, type=EntityType.WS
        )
        self._variable_id: Optional[str] = self.validate_id(
            variable_id, type=EntityType.VAR
        )

    @property
    def workspace_id(self):
        return self._workspace_id

    @property
    def variable_id(self):
        return self._variable_id

    @staticmethod
    def validate_id(value: Optional[str], type: EntityType) -> Optional[str]:
        if value:
            if type == EntityType.WS:
                assert value.startswith("ws-")
            elif type == EntityType.VAR:
                assert value.startswith("var-")
        return value

    def payload(self) -> Dict[str, Union[Dict, str]]:
        attributes: Dict = {
            "key": self.key,
            "value": self.value,
            "description": self.description,
            "category": self.category.value,
            "hcl": self.hcl,
            "sensitive": self.sensitive,
        }

        if self.variable_id:
            return {
                "data": {
                    "id": self.variable_id,
                    "attributes": attributes,
                    "type": EntityType.VAR.value,
                }
            }

        else:
            return {
                "data": {
                    "type": EntityType.VAR.value,
                    "attributes": attributes,
                    "relationships": {
                        "workspace": {
                            "data": {
                                "id": self.workspace_id,
                                "type": EntityType.WS.value,
                            }
                        }
                    },
                }
            }

    @property
    def url(self) -> httpx.URL:
        if self.variable_id:
            return VARS_URL.join(self.variable_id)
        else:
            return VARS_URL

    def post(self):
        return httpx.post(self.url, json=self.payload(), headers=HEADERS)


var = TFVar(
    key="TEST",
    value="test",
    description="test post",
    category=VarCategory.ENV,
    hcl=False,
    sensitive=False,
    workspace_id="ws-vBFHu5ziZP3HbSKc",
)

var.payload()
var.url
response = var.post()
response.json()


# delete old access key
response = iam.delete_access_key(
    UserName=IAM_TF_USERNAME, AccessKeyId=current_access_key_id
)
response_code = response["ResponseMetadata"]["HTTPStatusCode"]

if response_code == 200:
    logger.info(f"({IAM_TF_USERNAME}) deleted old access key")
else:
    logger.error(f"({IAM_TF_USERNAME}) failed to delete old access key")
