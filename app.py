# isort:skip_file
import logging


import ssm  # noqa
from chalice import Chalice, Rate
import terraform
import loggers

loggers.config()

app_name = "key-rotation"


logger = logging.getLogger()


app = Chalice(app_name=app_name)


@app.schedule(Rate(24, unit=Rate.HOURS), name="terraform-cloud")
def rotate_terraform_keys(event):
    terraform.rotate_keys()
