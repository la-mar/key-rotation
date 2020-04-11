import logging
from enum import Enum
from typing import Dict, Optional, Union

import config as conf
import httpx
import pandas as pd
from key_rotation import RotationManager

logger = logging.getLogger(__name__)


BASE_URL = httpx.URL("https://app.terraform.io/api/v2/")

WORKSPACE_URL = BASE_URL.join(f"organizations/{conf.TF_ORG_NAME}/workspaces")
VARS_URL = BASE_URL.join("vars/")

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
    logger.debug(f"({conf.TF_ORG_NAME}) fetching workspaces: {WORKSPACE_URL}")
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
    logger.debug(f"({conf.TF_ORG_NAME}) found {workspaces.shape[0]} workspaces")
    return workspaces


def get_variables() -> pd.DataFrame:
    logger.debug(f"({conf.TF_ORG_NAME}) fetching variables: {VARS_URL}")
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
    logger.debug(f"({conf.TF_ORG_NAME}) found {variables.shape[0]} variables")
    return variables


class TFVar:
    def __init__(
        self,
        key: str,
        value: str,
        category: Union[VarCategory, str],
        hcl: bool,
        sensitive: bool,
        description: str = "",
        variable_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ):
        self.key = key
        self.value = value
        self.description = description
        self.category = VarCategory(category)
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

    def __repr__(self):
        sensitive = " | sensitive" if self.sensitive else ""
        hcl = " | hcl" if self.hcl else ""
        return f"{self.id}/{self.key}: {self.category.value}{sensitive}{hcl}"

    @property
    def id(self):
        return self.workspace_id or self.variable_id

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

    def send(self):
        try:
            if self.variable_id:
                response = httpx.patch(self.url, json=self.payload(), headers=HEADERS)
            else:
                response = httpx.post(self.url, json=self.payload(), headers=HEADERS)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(
                f"({conf.TF_IAM_USERNAME}) Error rotating credential: {self.id}/{self.key} -- {e}"
            )  # noqa

        return response


def rotate_keys():
    variables = get_variables()
    workspaces = get_workspaces()
    envs = None

    with RotationManager(conf.TF_IAM_USERNAME) as rm:

        credentials = rm.new
        var_levels = rm.descriptions

        workspaces = (
            workspaces.reset_index().set_index("workspace_name").loc[:, "workspace_id"]
        )

        envs = variables.loc[variables.category == VarCategory.ENV.value].drop(
            columns=["created-at"]
        )

        # expanded_index = envs.index.set_levels(levels=list(var_levels.keys()), level="key")
        expanded_index = pd.MultiIndex.from_product(
            [workspaces.index, list(var_levels.keys())], names=["workspace_name", "key"]
        )

        envs = envs.reindex(index=expanded_index)

        creds = (
            pd.DataFrame(data=credentials, index=envs.index.levels[0])
            .reset_index()
            .melt(id_vars="workspace_name", var_name="key")
            .set_index(["workspace_name", "key"])
            .sort_index()
        )

        envs = creds.combine_first(envs)

        df = workspaces.reindex(expanded_index).to_frame().reset_index(level=1)
        df["workspace_id"] = workspaces
        df = df.set_index("key", append=True)
        df

        envs["workspace_id"] = df
        envs = envs.reset_index(level=1, drop=False).set_index(
            "key", append=True, drop=False
        )
        envs.description = envs.key.replace(var_levels)
        envs.value = envs.key.replace(credentials)
        envs = envs.drop(columns=["key"])

        envs["category"] = VarCategory.ENV.value
        envs["hcl"] = False
        envs["sensitive"] = True
        envs.loc[pd.IndexSlice[:, "AWS_IAM_ROLE"], "sensitive"] = False
        envs.loc[pd.IndexSlice[:, "LAST_ROTATED"], "sensitive"] = False
        envs.loc[envs.variable_id.notnull(), "workspace_id"] = None
        envs.loc[envs.variable_id.isna(), "variable_id"] = None

        missing_ids = envs.loc[envs.variable_id.isna() & envs.workspace_id.isna(), :]
        if missing_ids.shape[0] > 0:
            missing_records = (
                missing_ids.head()
                .reset_index()
                .loc[:, ["workspace_name", "key"]]
                .to_dict(orient="records")
            )
            for missing in missing_records:
                workspace_name = missing["workspace_name"]
                key = missing["key"]
                logger.warning(
                    f"({workspace_name}) {key} is missing both variable_id and workspace_id"
                )

        envs = envs.loc[envs.variable_id.notnull() | envs.workspace_id.notnull(), :]

        for workspace_name, df in envs.groupby(level=0):
            records = df.reset_index(level=1).to_dict(orient="records")
            tfvars = [TFVar(**r) for r in records]
            for var in tfvars:
                var.send()
            logger.info(
                f"({conf.TF_IAM_USERNAME}) successfully rotated keys for workspace: {workspace_name}"  # noqa
            )
