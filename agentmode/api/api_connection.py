import httpx
from dataclasses import dataclass

from agentmode.logs import logger

subclasses = {}

@dataclass
class APIConnection:

    def __init__(self):
        self.client = None
        self.mcp_resources = []
        self.mcp_tools = []
        self.auth_type = None
        self.credentials = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        subclasses[cls.name] = cls

    @classmethod
    def create(cls, name, settings, **kwargs):
        if name not in subclasses.keys():
            raise ValueError(f"Unknown APIConnection platform {name}")
        instance = subclasses[name](settings=settings, **kwargs)
        instance.client = httpx.Client()
        return instance
    
    def create_dynamic_tool_or_resource(self, fn_name, parameters={}):
        async def dynamic_tool_or_resource(input_parameters: dict = {}) -> str:
            try:
                # Validate required parameters
                for param_name, param_details in parameters.items():
                    if param_details.get('required') and param_name not in input_parameters:
                        raise ValueError(f"Missing required input parameter: {param_name}")

                # Log the query and parameters
                logger.debug(f"Executing API request for: {fn_name} with parameters: {input_parameters}")

                # Send the request with the provided parameters
                success_flag, result = await self.send_request(parameters.get('method'), parameters.get('url'), **input_parameters)
                if success_flag:
                    logger.debug(f"API result: {result}")
                    return result
                else:
                    logger.error(f"API query failed for {fn_name}")
                    return 'error'
            except Exception as e:
                logger.error(f"Error executing API request: {e}")
                return 'error' + str(e)

        return dynamic_tool_or_resource
    
    def generate_mcp_resources_and_tools(self, mcp):
        """
        Generate MCP resources and tools based on the API connection.
        This method dynamically iterates over types to avoid code repetition.
        """
        types = ['resource', 'tool']
        for type_ in types:
            items = self.mcp_resources if type_ == 'resource' else self.mcp_tools
            for item in items:
                # Create a dynamic function
                fn = self.create_dynamic_tool_or_resource(f"{self.name}-{item.get('operationId')}", item.get('parameters', {}))
                fn.__name__ = item.get('operationId')
                fn.__doc__ = self.generate_docstring_for_function(
                    item.get('operationId'),
                    item.get('description'),
                    item.get('parameters', {}),
                    item.get('responses', {})
                )
                getattr(mcp, type_)()(fn) # equivalent to mcp.resource()(fn) or mcp.tool()(fn)
                logger.debug(f"Generated function for {item.get('operationId')} of type {type_}")

    def generate_docstring_for_function(self, function_name: str, description: str = '', parameters: dict = {}, responses: dict = {}) -> str:
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

        for param_name, param_details in parameters.items():
            if param_details.get('required'):
                required_str = 'required'
            else:
                required_str = 'optional'
            param_type = param_details.get('type')
            param_str = ''
            if param_type:
                param_str = f" ({param_type})"
            param_description = ': ' + param_details.get('description', '')
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
            auth_type (str): The type of authentication (e.g., 'basic', 'bearer', 'api_key').
            credentials (dict): A dictionary containing authentication credentials.

        Returns:
            dict: A dictionary of headers to be used for authentication.
        """
        try:
            if auth_type == 'basic':
                username = credentials.get('username')
                password = credentials.get('password')
                if not username or not password:
                    raise ValueError("Missing username or password for Basic Auth")
                auth_header = httpx.BasicAuth(username, password)
                return {"Authorization": auth_header}

            elif auth_type == 'bearer':
                # typically used for OAuth2, so will be short-lived unless refreshed
                token = credentials.get('token')
                if not token:
                    raise ValueError("Missing token for Bearer Auth")
                return {"Authorization": f"Bearer {token}"}

            elif auth_type == 'api_key':
                api_key = credentials.get('api_key')
                header_name = credentials.get('header_name', 'Authorization')
                if not api_key:
                    raise ValueError("Missing API key for API Key Auth")
                return {header_name: api_key}

            else:
                raise ValueError(f"Unsupported authentication type: {auth_type}")

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise

    async def send_request(self, method: str, url: str, **kwargs):
        """
        Make an asynchronous HTTP request using the httpx client.

        Args:
            method (str): HTTP method (e.g., 'GET', 'POST').
            url (str): The URL for the request.

        Returns:
            tuple: A tuple containing a success flag (bool) and the response data (dict or None).
        """
        try:
            headers = kwargs.pop('headers', {})

            # Add authentication headers if auth_type is provided
            if self.auth_type and self.credentials:
                auth_headers = self.authentication(self.auth_type, self.credentials)
                headers.update(auth_headers)

            async with httpx.AsyncClient() as client:
                response = await client.request(method, url, headers=headers, **kwargs)
                response.raise_for_status()  # Raise an error for non-2xx responses
                return True, response.json()

        except httpx.RequestError as e:
            logger.error(f"An error occurred while making the request: {e}")
            return False, None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False, None
