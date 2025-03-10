import logging

import sd

# Create a logger.
logger = logging.getLogger("MIPmapsExporter")


# Add a handler to redirect logging to Designer's console panel.
ctx = sd.getContext()
logger.addHandler(ctx.createRuntimeLogHandler())


# Do not propagate log messages to Python's root logger.
logger.propagate = False


# Set the default log level if needed.
logger.setLevel(logging.DEBUG)
