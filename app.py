# isort:skip_file
import logging

import ssm  # noqa
import loggers
from chalice import Chalice

app_name = "key-rotation"

loggers.config()

logger = logging.getLogger()


app = Chalice(app_name=app_name)


# @app.schedule(Rate(24, unit=Rate.HOURS), name="capture-table-metrics")
# def capture_table_metrics(event):
#     query = "call _internal.capture_table_metrics();"
#     name = "capture-table-metrics"
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(functions.call_procedure(query, name=name))


# @app.schedule(Rate(1, unit=Rate.HOURS), name="refresh-1h")  # every 1 hour
# def refresh_1h(event):
#     refresh_views(VIEWS_1H)


# @app.schedule(Rate(3, unit=Rate.HOURS), name="refresh-3h")  # every 3 hour
# def refresh_3h(event):
#     refresh_views(VIEWS_3H)


# if __name__ == "__main__":

#     # functions = [x.function for x in inspect.stack()][-3:]
#     # chain = ".".join(list(reversed(functions)))
#     # print(chain)

#     # async def test():
#     #     import inspect

#     #     print(inspect.currentframe().f_code.co_name)

#     # await test()

#     loop.run_until_complete(capture_table_metrics.func({}))

# [x.function for x in inspect.stack()]
# dir(inspect)
# [x.frame.f_code.co_name for x in inspect.stack()]
