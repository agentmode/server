import logging

import pytest

from agentmode.api.api_connection import APIConnection
from agentmode.api.openapi_to_mcp_converter import OpenAPIToMCPConverter

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

CREDENTIALS = {
    "headers": '{"User-Agent": "agentmode, admin@agentmode.app"}'
}

@pytest.mark.asyncio
async def test_openapi_parsing():
    logger.info("Starting test_openapi_parsing")
    converter = OpenAPIToMCPConverter(name="weather", openapi_spec_url="https://api.weather.gov/openapi.json", filter_to_relevant_api_methods=False)
    await converter.run_pipeline()
    assert converter.api_connection.mcp_resources, "MCP resources are empty"

@pytest.mark.asyncio
async def test_api_request():
    logger.info("Starting test_api_request")
    converter = OpenAPIToMCPConverter(name="weather", openapi_spec_url="https://api.weather.gov/openapi.json", filter_to_relevant_api_methods=False)
    await converter.run_pipeline()
    api = APIConnection.create(
        name="weather",
        mcp_resources=converter.api_connection.mcp_resources,
        mcp_tools=converter.api_connection.mcp_tools,
        auth_type="API key in headers",
        credentials=CREDENTIALS,
        server_url="https://api.weather.gov",
    )
    success_flag, response = await api.send_request(
        method="GET",
        url="https://api.weather.gov/gridpoints/TOP/31,80/forecast"
    )
    assert success_flag is not False, "Request failed"
    assert response, "Request did not return any data"

if __name__ == "__main__":
    pytest.main()