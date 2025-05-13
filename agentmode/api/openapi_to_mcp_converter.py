from dataclasses import dataclass
from collections import defaultdict

import json
import httpx
import yaml
import toml
import os

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
    filter_to_operator_ids: list = None
    filter_to_paths: list = None
    read_only: bool = False
    filter_to_relevant_api_methods: bool = True

    def __post_init__(self):
        """
        Initialize the OpenAPIToMCPConverter instance.
        """
        # Dynamically create a subclass of APIConnection with the given name
        self.api_connection = type(f"{self.name}APIConnection", (APIConnection,), {})(name=self.name)
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
        self.operation_ids = defaultdict(int) # sometimes APIs don't use unique operation IDs, so we need to ensure uniqueness

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
            self.api_connection.mcp_resources = await self.api_filter.filter_api_calls(self.api_connection.mcp_resources)
            self.api_connection.mcp_tools = await self.api_filter.filter_api_calls(self.api_connection.mcp_tools)
            logger.info(f"Filtered resources operationIds: {[resource['operationId'] for resource in self.api_connection.mcp_resources]}")
            logger.info(f"Filtered tools operationIds: {[tool['operationId'] for tool in self.api_connection.mcp_tools]}")

        if self.filter_to_operator_ids or self.filter_to_paths:
            logger.info(f"Filtering resources and tools to operator IDs: {self.filter_to_operator_ids}, paths: {self.filter_to_paths}")
            # Filter the resources and tools based on operator IDs and paths
            self.api_connection.mcp_resources = [resource for resource in self.api_connection.mcp_resources if resource['operationId'] in self.filter_to_operator_ids or resource['path'] in self.filter_to_paths]
            self.api_connection.mcp_tools = [tool for tool in self.api_connection.mcp_tools if tool['operationId'] in self.filter_to_operator_ids or tool['path'] in self.filter_to_paths]

        self.save_results({'resources': self.api_connection.mcp_resources, 'tools': self.api_connection.mcp_tools}, self.filter_to_relevant_api_methods)

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
                logger.debug(f"Content-Type: {content_type}")
                if 'yaml' in content_type or 'yml' in content_type or self.openapi_spec_url.endswith(('.yaml', '.yml')):
                    self.openapi_spec = yaml.safe_load(response.text)
                else:
                    self.openapi_spec = response.json()
        elif self.openapi_spec_file_path:
            with open(self.openapi_spec_file_path, 'r') as file:
                if self.openapi_spec_file_path.endswith(('.yaml', '.yml')):
                    self.openapi_spec = yaml.safe_load(file)
                else:
                    self.openapi_spec = json.load(file)
        else:
            raise ValueError("Either 'openapi_spec_url' or 'openapi_spec_file_path' must be provided.")

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
        specs for open source tools may not have a 'servers' section, so it will need to be manually set
        """
        # Initialize the OpenAPI spec if not already done
        if not hasattr(self, 'openapi_spec'):
            raise ValueError("OpenAPI specification not loaded. Call 'get_openapi_spec' first.")

        # Extract servers and paths from the OpenAPI spec
        servers = self.openapi_spec.get('servers', [])
        paths = self.openapi_spec.get('paths', {})
        self.api_connection.security = self.openapi_spec.get('security', [])
        server_url = ''

        # Flatten the OpenAPI spec into a list of unique paths/methods
        for server in servers:
            server_url = server.get('url')
            if server_url:
                break
        for path, methods in paths.items():
            for method, details in methods.items():
                if not isinstance(details, dict):
                    # sometimes the method is 'parameters' and the details are a list of reference schemas
                    logger.warning(f"Details for method '{method}' at path '{path}' is not a dictionary. Skipping.")
                    continue
                operation_id = details.get('operationId')
                parameters = details.get('parameters', [])
                responses = details.get('responses', {})
                request_body_parameters = details.get('requestBody', {})
                description = details.get('description', '')
                tags = details.get('tags', [])

                # Denormalize any reference schemas in parameters
                for param in parameters:
                    if 'schema' in param and '$ref' in param['schema']:
                        ref = param['schema']['$ref']
                        param['schema'] = self.resolve_ref(ref)
                    elif '$ref' in param.keys():
                        ref = param['$ref']
                        param['schema'] = self.resolve_ref(ref)

                # Denormalize any reference schemas in responses
                for response_code, response_details in responses.items():
                    if 'content' in response_details:
                        for content_type, content_details in response_details['content'].items():
                            if 'schema' in content_details and '$ref' in content_details['schema']:
                                ref = content_details['schema']['$ref']
                                content_details['schema'] = self.resolve_ref(ref)

                # Denormalize any reference schemas in requestBody
                if 'content' in request_body_parameters:
                    for content_type, content_details in request_body_parameters['content'].items():
                        if content_type in ['application/json', 'application/x-www-form-urlencoded']:
                            if 'schema' in content_details and '$ref' in content_details['schema']:
                                ref = content_details['schema']['$ref']
                                content_details['schema'] = self.resolve_ref(ref)

                # If operationId is not present, generate a unique one
                if not operation_id:
                    operation_id = f"{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}"
                self.operation_ids[operation_id] += 1
                if self.operation_ids[operation_id] > 1:
                    operation_id = f"{operation_id}_{self.operation_ids[operation_id]}" # will append _1, _2, etc. to the operationId

                # Create a dictionary for the operation
                operation_info = {
                    'server_url': server_url,
                    'path': path,
                    'method': method,
                    'parameters': parameters,
                    'responses': responses,
                    'request_body_parameters': request_body_parameters,
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
    
    def save_results(self, results, filtered):
        """
        Save the results to a JSON file
        """
        path = os.path.join('api', 'connectors', f'{self.name}.json')
        logger.debug(f"Saving results to {path}")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as json_file:
            json.dump(results, json_file, indent=4)