import logging
import sys

# Local MCP servers should not log messages to stdout (standard out), as this will interfere with protocol operation.
# https://modelcontextprotocol.io/docs/tools/debugging

# Create a logger
logger = logging.getLogger('logger')
logger.setLevel(logging.DEBUG)  # Set the logging level

# Create a handler that outputs to stdout
#handler = logging.StreamHandler(sys.stderr) # don't send to stdout as we use that for stdio in MCP
#handler.setLevel(logging.DEBUG)  # Set the logging level for the handler

# Create a formatter and set it for the handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#handler.setFormatter(formatter)

# Add the handler to the logger
#logger.addHandler(handler)

# Create a handler that outputs to a file
file_handler = logging.FileHandler('application.log')
file_handler.setLevel(logging.DEBUG)  # Set the logging level for the file handler

# Set the same formatter for the file handler
file_handler.setFormatter(formatter)

# Add the file handler to the logger
logger.addHandler(file_handler)

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)  # Set the root logger level
root_logger.handlers = []  # Clear existing handlers
root_logger.addHandler(file_handler)

# Configure logging for SQLAlchemy and other imported modules
sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
sqlalchemy_logger.setLevel(logging.WARNING)  # Set to WARNING to suppress DEBUG/INFO logs
sqlalchemy_logger.addHandler(file_handler)  # Redirect logs to the file handler