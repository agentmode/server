import toml
import asyncio

from agentmode.api.openapi_to_mcp_converter import OpenAPIToMCPConverter
from agentmode.logs import logger

async def process_connectors_toml(file_path):
    # Load the TOML file
    with open(file_path, 'r') as file:
        connectors = toml.load(file)

    # Iterate through each group in the TOML file
    for group_name, items in connectors.items():
        for item in items:
            if item.get('connection_type') == 'api':
                # Call filter_api_calls with the openapi_specification
                openapi_spec_url = item.get('openapi_spec_url')
                filter_to_operator_ids = item.get('filter_to_operator_ids', [])
                filter_to_paths = item.get('filter_to_paths', [])
                if openapi_spec_url:
                    try:
                        # Assuming openapi_spec is a list of API calls
                        # Replace with actual fetching/parsing logic if needed
                        converter = OpenAPIToMCPConverter(item.get('name'), openapi_spec_url=openapi_spec_url, filter_to_relevant_api_methods=False, filter_to_operator_ids=filter_to_operator_ids, filter_to_paths=filter_to_paths)
                        await converter.run_pipeline()
                    except Exception as e:
                        logger.error(f"Error processing API {item.get('name')}: {e}")

if __name__ == "__main__":
    # Path to the connectors.toml file
    toml_file_path = "connectors.toml"
    asyncio.run(process_connectors_toml(toml_file_path))