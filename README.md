# key-rotation

requirements.txt -> used in Chalice packaging
vendor-requirements.txt -> used by scripts/vendor-c-libs.sh

# TODO

1. post datadog event when executed

Example .chalice/config.json

```json
{
  "version": "2.0",
  "app_name": "key-rotation",
  "lambda_memory_size": 128,
  "lambda_timeout": 900,
  "reserved_concurrency": 1,
  "api_gateway_stage": "api",
  "manage_iam_role": false,
  "iam_role_arn": "arn:aws:iam::AWS_ACCOUNT_ID_HERE:role/key-rotation-role",
  "environment_variables": {
    "PYTHONPATH": "./chalicelib:./:$PYTHONPATH",
    "APP_NAME": "key-rotation"
  },
  "subnet_ids": [
    "subnet-example-1",
    "subnet-example-2",
    "subnet-example-3",
    "subnet-example-4"
  ],
  "security_group_ids": ["sg-example-1"],
  "tags": {
    "domain": "technology",
    "service_name": "key-rotation",
    "terraform": "false",
    "environment": "prod"
  }
}
```
