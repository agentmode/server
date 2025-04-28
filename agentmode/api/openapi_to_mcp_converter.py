from dataclasses import dataclass

import json
import httpx
import yaml
import toml

from agentmode.logs import logger
from agentmode.api.filter_openapi_specs import FilterOpenAPISpecs
from agentmode.api.api_connection import APIConnection

@dataclass
class OpenAPIToMCPConverter:
    """
    This class is responsible for converting OpenAPI specifications to MCP format.
    It provides methods to parse OpenAPI documents and generate corresponding MCP resources and tools.
    It runs on-the-fly, and is not designed to output persistent files.
    """
    name: str
    openapi_spec_url: str = None
    openapi_spec_file_path: str = None
    read_only: bool = False
    filter_to_relevant_api_methods: bool = True

    def __post_init__(self):
        """
        Initialize the OpenAPIToMCPConverter instance.
        """
        # Dynamically create a subclass of APIConnection with the given name
        self.api_connection = type(f"{self.name}APIConnection", (APIConnection,), {})()
        setattr(self.api_connection, 'name', self.name)
        self.mapping_operations_to_mcp = {
            'GET': 'resource',
            'POST': 'tool',
            'PUT': 'tool',
            'DELETE': 'tool',
            'PATCH': 'tool',
            'OPTIONS': 'resource',
            'HEAD': 'resource',
            'TRACE': 'tool',
        }
        self.api_filter = FilterOpenAPISpecs(self.name)

    async def run_pipeline(self):
        """
        Run the pipeline to convert OpenAPI specifications to MCP format.
        This method orchestrates the loading, parsing, and filtering of OpenAPI specs.
        """
        # Load the OpenAPI spec
        await self.get_openapi_spec()

        # Parse the OpenAPI spec
        self.parse_openapi_spec()

        # Filter the OpenAPI spec if required
        if self.filter_to_relevant_api_methods:
            filtered_resources = await self.api_filter.filter_api_calls(self.api_connection.mcp_resources)
            filtered_tools = await self.api_filter.filter_api_calls(self.api_connection.mcp_tools)
            logger.info(f"Filtered resources: {filtered_resources}")
            logger.info(f"Filtered tools: {filtered_tools}")
            self.save_filtered_results({'resources': filtered_resources, 'tools': filtered_tools})

    async def get_openapi_spec(self):
        """
        Load the OpenAPI specification from a URL or file.
        """
        # Load the OpenAPI spec from URL or file
        if self.openapi_spec_url:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.openapi_spec_url)
                response.raise_for_status()
                content_type = response.headers.get('Content-Type', '')
                if 'yaml' in content_type or 'yml' in content_type:
                    self.openapi_spec = yaml.safe_load(response.text)
                else:
                    self.openapi_spec = response.json()
        elif self.openapi_spec_path:
            with open(self.openapi_spec_path, 'r') as file:
                if self.openapi_spec_path.endswith(('.yaml', '.yml')):
                    self.openapi_spec = yaml.safe_load(file)
                else:
                    self.openapi_spec = json.load(file)
        else:
            raise ValueError("Either 'openapi_spec_url' or 'openapi_spec_path' must be provided.")

    def parse_openapi_spec(self):
        """
        Parse the OpenAPI specification and extract relevant information.

        we flatten the specification into a list of unique paths/methods (one per operationId, if present)
        the operationId is typically used to name the function in the generated code, or to refer to it in the documentation.
        We denormalize any references schemas so we don't have to do lookups later.
        Each list item will be a dictionary with the following keys:
        - url: server URL suffixed with the API path
        - method: the HTTP method (GET, POST, etc.)
        - parameters: list of input parameters (with keys such as name, required, schema, etc.)
        - responses: list of response codes (with keys such as data type, code, description, schema, etc.)
        - description: a short description of the endpoint (optional)
        - tags: list of tags associated with the endpoint (optional)

        we also store the authentication information (if any) in the APIConnection instance
        """
        # Initialize the OpenAPI spec if not already done
        if not hasattr(self, 'openapi_spec'):
            raise ValueError("OpenAPI specification not loaded. Call 'get_openapi_spec' first.")

        # Extract servers and paths from the OpenAPI spec
        servers = self.openapi_spec.get('servers', [])
        paths = self.openapi_spec.get('paths', {})
        self.api_connection.security = self.openapi_spec.get('security', [])

        # Flatten the OpenAPI spec into a list of unique paths/methods
        for server in servers:
            server_url = server.get('url')
            for path, methods in paths.items():
                for method, details in methods.items():
                    operation_id = details.get('operationId')
                    parameters = details.get('parameters', [])
                    responses = details.get('responses', {})
                    description = details.get('description', '')
                    tags = details.get('tags', [])
                    # Denormalize any references schemas
                    for param in parameters:
                        if '$ref' in param['schema']:
                            ref = param['schema']['$ref']
                            param['schema'] = self.resolve_ref(ref)
                    for response_code, response_details in responses.items():
                        if 'content' in response_details and \
                           'application/json' in response_details['content'] and \
                           'schema' in response_details['content']['application/json'] and \
                           '$ref' in response_details['content']['application/json']['schema']:
                            ref = response_details['content']['application/json']['schema']['$ref']
                            response_details['content']['application/json']['schema'] = self.resolve_ref(ref)
                    # If operationId is not present, generate a unique one
                    if not operation_id:
                        operation_id = f"{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}"
                    # Create a dictionary for the operation
                    operation_info = {
                        'url': f"{server_url}{path}",
                        'method': method,
                        'parameters': parameters,
                        'responses': responses,
                        'description': description,
                        'tags': tags,
                        'operationId': operation_id,
                    }
                    method = method.upper()
                    if method in self.mapping_operations_to_mcp:
                        # Map the operation to MCP resources or tools
                        mcp_type = self.mapping_operations_to_mcp.get(method)
                        if mcp_type == 'resource':
                            self.api_connection.mcp_resources.append(operation_info)
                        elif mcp_type == 'tool':
                            if self.read_only:
                                logger.warning(f"Tool '{operation_id}' is read-only and will not be added to MCP tools.")
                            else:
                                self.api_connection.mcp_tools.append(operation_info)
                    else:
                        logger.debug(f"Unknown HTTP method '{method}' for operation '{operation_id}'. Skipping.")

                logger.info(f"Parsed operation '{operation_id}' with method '{method}'.")

        logger.info(f"Total resources parsed: {len(self.api_connection.mcp_resources)}")
        logger.info(f"Total tools parsed: {len(self.api_connection.mcp_tools)}")

    def resolve_ref(self, ref):
        """
        Resolve a $ref (reference) in the OpenAPI specification.

        Args:
            ref (str): The reference string (e.g., '#/components/schemas/ExampleSchema').

        Returns:
            dict: The resolved schema or object.
        """
        if not ref.startswith('#/'):
            raise ValueError(f"Unsupported reference format: {ref}")

        # Remove the initial '#/' and split the reference path
        ref_path = ref[2:].split('/')

        # Navigate through the OpenAPI spec to resolve the reference
        resolved = self.openapi_spec
        for part in ref_path:
            if part not in resolved:
                raise KeyError(f"Reference path '{'/'.join(ref_path)}' not found in the OpenAPI spec.")
            resolved = resolved[part]

        return resolved
    
    def save_filtered_results(self, filtered_results):
        """
        Save the filtered results to a TOML file.
        """
        with open(f'api/connectors/{self.name}.toml', 'w') as toml_file:
            toml.dump(filtered_results, toml_file)