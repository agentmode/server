import json
from dataclasses import dataclass, field

import httpx

from agentmode.logs import logger
from agentmode.api.connectors.api_connector import APIConnector

@dataclass
class APIConnection:
    """
    an APIConnection actively sends requests to an API and returns the results.
    an APIConnector defines the API schema that we're interested in, and how to filter the results.
    """
    name: str
    mcp_resources: list = field(default_factory=list)
    mcp_tools: list = field(default_factory=list)
    auth_type: str = None
    credentials: dict = None
    server_url: str = None
    connector: APIConnector = None
    filter_responses: dict = field(default_factory=dict)
    decode_responses: dict = field(default_factory=dict)

    def __post_init__(self):
        self.client = httpx.Client()
        self.mcp_resources_functions = {} # for testing purposes
        self.mcp_tools_functions = {} # for testing purposes

    def create_dynamic_tool_or_resource(self, fn_name, server_url, path, method, parameters, request_body_parameters, operation_id):

        async def dynamic_tool_or_resource(input_parameters: dict = {}) -> str:
            try:
                # Use a local variable to avoid UnboundLocalError
                local_server_url = server_url or self.server_url
                if not local_server_url:
                    raise ValueError("Missing server_url in parameters and/or class")

                # Validate required parameters
                for parameter in parameters:
                    param_name = parameter.get('name')
                    if parameter.get('required') and param_name not in input_parameters:
                        raise ValueError(f"Missing required input parameter: {param_name}")
                    # TODO: validate enum values for parameters https://swagger.io/docs/specification/v3_0/describing-parameters/#enum-parameters

                # Log the query and parameters
                logger.debug(f"Executing API request for: {fn_name} with parameters: {input_parameters}")

                # for each parameter in input_parameters, check how it needs to be sent by checking the parameters dict
                # https://swagger.io/docs/specification/v3_0/describing-parameters/
                url_params = {}
                headers = {}
                body_data = {}
                form_data = {}
                for parameter in parameters:
                    param_name = parameter.get('name')
                    if param_name in input_parameters:
                        # Check if the parameter is a query parameter
                        if parameter.get('in') == 'query':
                            url_params[param_name] = input_parameters[param_name]
                        # Check if the parameter is a URL path parameter
                        elif parameter.get('in') == 'path':
                            # Replace the parameter in the path with its value
                            if parameters.get('path'):
                                parameters['path'] = parameters['path'].replace(f"{{{param_name}}}", str(input_parameters[param_name]))
                            else:
                                raise ValueError(f"Missing path for path parameter: {param_name}")
                        # Check if the parameter is a header parameter
                        elif parameter.get('in') == 'header':
                            headers[param_name] = input_parameters[param_name]


                # In OpenAPI v3, Body and form parameters are replaced with requestBody, but we convert all v2 specs to v3 before parsing
                # check if the parameter is a body parameter
                if request_body_parameters:
                    content = request_body_parameters.get('content')
                    for content_type, content_details in content.items():
                        if content_type in ['application/json', 'application/x-www-form-urlencoded']:
                            properties = content.get(content_type, {}).get('schema', {}).get('properties', {})
                            for param_name, param_details in properties.items():
                                if param_name in input_parameters:
                                    if content_type == 'application/json':
                                        body_data[param_name] = input_parameters[param_name]
                                    elif content_type == 'application/x-www-form-urlencoded':
                                        form_data[param_name] = input_parameters[param_name]


                full_url = local_server_url + path

                # Send the request with the provided parameters
                success_flag, result = await self.send_request(method, full_url, url_params, headers, body_data, form_data, operation_id)
                if success_flag:
                    logger.debug(f"API result: {result}")
                    return result
                else:
                    logger.error(f"API query failed for {fn_name}")
                    return 'error'
            except Exception as e:
                logger.error(f"Error executing API request", exc_info=True)
                return 'error'

        return dynamic_tool_or_resource
    
    def generate_mcp_resources_and_tools(self, mcp, connection_name_counter):
        """
        Generate MCP resources and tools based on the API connection.
        This method dynamically iterates over types to avoid code repetition.
        """
        types = ['resource', 'tool']
        for type_ in types:
            items = self.mcp_resources if type_ == 'resource' else self.mcp_tools
            for item in items:
                # Check if the name already exists in the mapping (ie we may have multiple connections to the same API, ie one for prod & one for staging)
                name = f"{self.name}/{item.get('operationId')}"
                # Increment the counter for the connection name (TODO: ask the user to provide a unique name)
                suffix = ""
                connection_name_counter[name] += 1
                if connection_name_counter[name] > 1:
                    suffix = f"_{connection_name_counter[name]}"
                    name = f"{name}{suffix}"

                # Create a dynamic function
                fn = self.create_dynamic_tool_or_resource(name, item.get('server_url', ''), item.get('path', ''), item.get('method', ''), item.get('parameters', []), item.get('request_body_parameters', {}), item.get('operationId'))
                fn.__name__ = item.get('operationId')
                fn.__doc__ = self.generate_docstring_for_function(
                    item.get('operationId'),
                    item.get('description'),
                    item.get('parameters', []),
                    item.get('responses', {})
                )
                # resources need a URI parameter, whereas tools don't
                if type_ == 'resource':
                    uri = f"{self.name}{suffix}//{item.get('operationId')}/{{input_parameters}}" # input_parameters is required to be in the URI
                    # otherwise you get an error: ValueError: Mismatch between URI parameters set() and function parameters {'input_parameters'}
                    mcp.resource(uri)(fn)
                    self.mcp_resources_functions[name] = fn
                else:
                    mcp.tool()(fn) # getattr(mcp, type_)()(fn)
                    self.mcp_tools_functions[name] = fn
                logger.debug(f"Generated function for {item.get('operationId')} of type {type_}")

    def generate_docstring_for_function(self, function_name: str, description: str = '', parameters: list = [], responses: dict = {}) -> str:
        """
        Generate a description using the path, method, and parameters
        following the Google-style docstring format
        """
        docstring = f"""
        {function_name}
        
        """
        if parameters:
            docstring += """
Args:
    input_parameters (dict): All the input parameters for the function, with possible key/value items:
            """

        for parameter in parameters:
            param_name = parameter.get('name')
            if parameter.get('required'):
                required_str = 'required'
            else:
                required_str = 'optional'
            param_type = parameter.get('type')
            param_str = ''
            if param_type:
                param_str = f" ({param_type})"
            param_description = ': ' + parameter.get('description', '')
            docstring += f"    {param_name}{param_str} {required_str}{param_description}\n"

        if responses:
            docstring += "\n        Returns:\n"
            for response_code, response_details in responses.items():
                docstring += f"            {response_code}: {response_details.get('description', '')}\n"
        return docstring

    def authentication(self, auth_type: str, credentials: dict):
        """
        Perform authentication using the provided settings.

        Args:
            auth_type (str): The type of authentication (e.g., 'basic', 'bearer', 'api_key', 'digest').
            credentials (dict): A dictionary containing authentication credentials.

        Returns:
            dict: A dictionary of headers to be used for authentication.
        """
        try:
            if auth_type == 'Basic Auth':
                username = credentials.get('username')
                password = credentials.get('password')
                if not username or not password:
                    raise ValueError("Missing username or password for Basic Auth")
                auth_header = httpx.BasicAuth(username, password)
                return {"Authorization": auth_header}

            elif auth_type == 'Bearer Token':
                # typically used for OAuth2, so will be short-lived unless refreshed
                token = credentials.get('token')
                if not token:
                    raise ValueError("Missing token for Bearer Auth")
                return {"Authorization": f"Bearer {token}"}

            elif auth_type == 'API key in headers':
                return json.loads(credentials.get('headers'))

            elif auth_type == 'Digest Auth':
                username = credentials.get('username')
                password = credentials.get('password')
                if not username or not password:
                    raise ValueError("Missing username or password for Digest Auth")
                auth_header = httpx.DigestAuth(username, password)
                return {"Authorization": auth_header}

            else:
                raise ValueError(f"Unsupported authentication type: {auth_type}")

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise

    async def send_request(self, method: str, url: str, url_params: dict = {}, headers: dict = {}, body_data: dict = {}, form_data: dict = {}, operation_id: str = None):
        """
        Make an asynchronous HTTP request using the httpx client.

        Args:
            method (str): HTTP method (e.g., 'GET', 'POST').
            url (str): The URL for the request.
            url_params (dict): URL parameters to be included in the request.
            headers (dict): Headers to be included in the request.
            body_data (dict): Body data to be included in the request.
            form_data (dict): Form data to be included in the request.
            operator_id (str): The ID of the operator for the request.
            **kwargs: Additional keyword arguments for the request.

        Returns:
            tuple: A tuple containing a success flag (bool) and the response data (dict or None).
        """
        try:
            # Add authentication headers if auth_type is provided
            if self.auth_type and self.credentials:
                auth_headers = self.authentication(self.auth_type, self.credentials)
                headers.update(auth_headers)

            async with httpx.AsyncClient() as client:
                # form-encoded data is sent as data=data parameter, where data is a dict
                # json data is sent as json=data parameter, where data is a dict
                # query parameters are sent as params=params parameter, where params is a dict
                # if there are parameters in the URL itself that need to be replaced, we need to do that ourselves
                kwargs = {}
                if form_data:
                    kwargs['data'] = form_data
                if body_data:
                    kwargs['json'] = body_data
                if headers:
                    kwargs['headers'] = headers
                if url_params:
                    kwargs['params'] = url_params
                
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()  # Raise an error for non-2xx responses
                result = response.text
                is_json = False
                # if the response is JSON, decode it
                if response.headers.get('Content-Type') == 'application/json':
                    result = response.json()
                    is_json = True
                if self.connector and self.filter_responses and is_json and self.filter_responses and self.filter_responses.get(operation_id): # only support JSON responses for now
                    result = json.dumps(self.connector.post_process_response(result, self.filter_responses.get(operation_id)))
                if self.connector and self.decode_responses and self.decode_responses.get(operation_id):
                    result = json.dumps(self.connector.base64_decode(result, self.decode_responses.get(operation_id)))
                return True, result

        except httpx.RequestError as e:
            logger.error(f"An error occurred while making the request: {e}")
            return False, None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False, None
