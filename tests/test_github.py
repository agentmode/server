import logging
import os
from collections import defaultdict
import uuid

import pytest
import pytest_asyncio
from benedict import benedict
import importlib

from agentmode.api.api_connection import APIConnection
from agentmode.api.openapi_to_mcp_converter import OpenAPIToMCPConverter

# setup a logger to log to the console
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

CREDENTIALS = {
    "token": os.environ.get("GITHUB_ACCESS_TOKEN")
}

# Load connectors from a TOML file
test_connector = None
connectors_path = importlib.resources.files('agentmode').joinpath('connectors.toml')
CONNECTORS_FILE = str(connectors_path)
logger.debug("CONNECTORS_FILE: %s", CONNECTORS_FILE)
connectors = benedict.from_toml(CONNECTORS_FILE)
for group, connectors_list in connectors.items():
    for connector in connectors_list:
        logger.debug("Connector name: %s", connector.get("name"))
        if connector.get("name") == "GitHub":
            test_connector = connector
            break
if test_connector is None:
    raise ValueError("GitHub connector not found in connectors.toml")

# create a Dummy MCP object which can have 'tool' and 'resource' methods which take arbitrary parameters
class DummyMCP:
    def __init__(self):
        self.mcp_resources_functions = {}
        self.mcp_tools_functions = {}

    def tool(self, **kwargs):
        def decorator(func):
            self.mcp_tools_functions[uuid.uuid4()] = func
            return func
        return decorator

    def resource(self, uri, **kwargs):
        def decorator(func):
            self.mcp_resources_functions[uri] = func
            return func
        return decorator

@pytest_asyncio.fixture
async def github_converter():
    converter = OpenAPIToMCPConverter(
        name=test_connector.get("name"),
        openapi_spec_url=test_connector.get("openapi_spec_url"),
        filter_to_relevant_api_methods=False,
        filter_to_operator_ids=test_connector.get("filter_to_operator_ids")
    )
    await converter.run_pipeline()
    return converter

@pytest.mark.asyncio
async def test_openapi_parsing(github_converter):
    logger.info("Starting test_openapi_parsing")
    assert github_converter.api_connection.mcp_resources, "MCP resources are empty"

@pytest.mark.asyncio
async def test_api_request(github_converter):
    logger.info("Starting test_api_request")
    api = github_converter.api_connection
    api.auth_type = test_connector.get("default_authentication_method")
    api.credentials = CREDENTIALS
    api.filter_responses = test_connector.get("filter_responses", {})
    api.decode_responses = test_connector.get("decode_responses", {})
    mcp = DummyMCP()
    api.generate_mcp_resources_and_tools(mcp, defaultdict(int))
    logger.info("resources: %s", api.mcp_resources_functions.keys())
    logger.info("tools: %s", api.mcp_tools_functions.keys())
    fn = api.mcp_resources_functions.get('GitHub/search/code')
    assert fn, "Function not found in mcp_resources_functions"
    response = await fn(input_parameters={"q": "test", "page": 1})
    logger.info("API Response: %s", response)
    assert response, "Request did not return any data"

if __name__ == "__main__":
    pytest.main(["-v", "--log-cli-level=INFO", "test_github.py"])