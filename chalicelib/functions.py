from db import db
from util.deco import log_execution_time


@log_execution_time
async def call_procedure(text: str):
    async with db.with_bind():
        await db.scalar(text)
