import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from collections import defaultdict
import asyncio
import signal
import importlib.resources

import uvicorn
from uvicorn import Config, Server
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import (
	PlainTextResponse,
)
import click
from benedict import benedict
from mcp.server.fastmcp import FastMCP, Context
import gradio as gr
import platformdirs

from agentmode.logs import logger
from agentmode.database import DatabaseConnection
from agentmode.api.api_connection import APIConnection
from agentmode.api.connectors.api_connector import APIConnector

HOME_DIRECTORY = platformdirs.user_data_dir('agentmode', ensure_exists=True)
PORT = os.getenv("PORT", 13000)
# to debug: uv run mcp dev mcp_server.py

"""
Resources (think of these sort of like GET endpoints; they are used to load information into the LLM's context)
Provide functionality through Tools (sort of like POST endpoints; they are used to execute code or otherwise produce a side effect)
https://github.com/modelcontextprotocol/python-sdk
"""

@dataclass
class AppContext:
    db: Any

# Maintain a mapping of function names to their database connections
connection_mapping = {}
connections_created = []
kwargs = {}

async def setup_database_connection(connection_name: str, connection: dict, mcp: FastMCP, connection_name_counter: defaultdict) -> None:
    """
    Establish a database connection and store it in the connection mapping.
    """
    try:
        db = DatabaseConnection.create(connection_name, connection)
        if not await db.connect():
            logger.error(f"Failed to connect to {connection_name}")
            return None
        else:
            logger.info(f"Connected to {connection_name}")

        await db.generate_mcp_resources_and_tools(connection_name, mcp, connection_name_counter, connection_mapping)
    except Exception as e:
        logger.error(f"Error setting up database connection: {e}")
        return None
    
async def setup_api_connection(connection_name: str, connection: dict, mcp: FastMCP, connection_name_counter: defaultdict) -> None:
    """
    Establish an API connection and store it in the connection mapping.
    """
    try:
        api_connection = type(f"{connection_name}APIConnection", (APIConnection,), {'name': connection_name})() # define the APIConnection class dynamically
        
        # get the API schema from api/connectors/{connection_name}.json
        connectors_path = importlib.resources.files('agentmode.api.connectors').joinpath(f"{connection_name}.json")
        api_info = benedict.from_json(str(connectors_path))
        if not api_info:
            logger.error(f"Failed to load API information for {connection_name}")
            return None
        
        # get the APIConnector for that API name
        api_connector = APIConnector.create(connection_name) # may be a subclass of APIConnector if custom logic is needed
        # Create the APIConnection instance
        api_connection = APIConnection(
            connection_name, 
            mcp_resources=api_info.get("resources", []),
            mcp_tools=api_info.get("tools", []),
            auth_type=connection.get("authentication_type"), # comes from the form
            credentials={
                "username": connection.get("username"),
                "password": connection.get("password"),
                "token": connection.get("token"),
                "headers": connection.get("headers"),
            }, 
            server_url=connection.get("server_url"), # comes from the form,
            connector=api_connector,
            response_filters=api_info.get("filter_responses", {}),
            decode_responses=api_info.get("decode_responses", {}),
        )

        api_connection.generate_mcp_resources_and_tools(mcp, connection_name_counter)
    except Exception as e:
        logger.error(e, exc_info=True)
        return None
    
async def setup_connections():
    """
    Setup connections for the application.
    This function is called during application startup, as well as whenever a new connection is added.
    """
    logger.info("Setting up connections...")
    global mcp, connections_created, kwargs
    
    """
    read the connections from the kwargs dictionary, which is populated by the CLI arguments
    The expected format is:
    mysql_1+host: value
    mysql_1+port: value
    mysql_1+username: value
    mysql_1+password: value
    mysql_1+database_name: value
    mysql_1+read_only: value
    """

    parameters_per_connection = defaultdict(dict) # stores all parameters for each connection like 'mysql_1'
    if kwargs:
        for key, value in kwargs.items():
            # split the key on the first '+' to get the connection name and the property
            if '+' in key:
                connection_name, property_name = key.split('+', 1)
                parameters_per_connection[connection_name][property_name] = value
    # for each connection, get the connection_type from connectors.toml
    connectors_path = importlib.resources.files('agentmode').joinpath("connectors.toml")
    connectors = benedict.from_toml(str(connectors_path))
    # flatten the connectors data so we can look up connectors by label or name
    list_connectors = {}
    for group_name, group_connectors in connectors.items():
        for connector_info in group_connectors:
            list_connectors[connector_info.get("label", connector_info.get("name")).lower()] = connector_info
    for connection_name, parameters in parameters_per_connection.items():
        connection_type = list_connectors.get(connection_name, {}).get('connection_type')
        if not connection_type:
            logger.error(f"Connection type for {connection_name} not found in connectors.toml")
            break
        parameters_per_connection[connection_name]['connection_type'] = connection_type
        
    # Dynamically create tools/resources for each connection
    connection_name_counter = defaultdict(int) # each connection name may be suffixed with a counter to ensure uniqueness, in case of duplicates
    for connection, params in parameters_per_connection.items():
        logger.info(f"Creating tool for connection: {connection}")
        connection_name = connection
        connection_type = params.pop('connection_type')

        if connection_type=='database': # Establish the database connection and store it in the mapping
            await setup_database_connection(connection_name, params, mcp, connection_name_counter)
        elif connection_type=='api':
            await setup_api_connection(connection_name, params, mcp, connection_name_counter)

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with type-safe context"""
    await setup_connections()
    try:
        yield AppContext(db=None)
    finally:
        # Cleanup on shutdown
        for db in connection_mapping.values():
            await db.disconnect()
        connection_mapping.clear()

async def ping(request):
	"""
	return 200 OK
	"""
	return PlainTextResponse("OK", status_code=200)

def process_args(ctx):
    """Accept key-value pairs in '--key value' format and convert them to a dictionary."""
    # Extract the raw arguments passed after the command
    raw_args = ctx.args

    # Ensure the arguments are in key-value pairs
    if len(raw_args) % 2 != 0:
        raise click.UsageError("Arguments must be provided in '--key value' pairs.")

    # Convert the arguments into a dictionary
    args_dict = {raw_args[i].lstrip('-'): raw_args[i + 1] for i in range(0, len(raw_args), 2)}
    # if any value is 'true' or 'false', convert it to a boolean
    for key, value in args_dict.items():
        if value.lower() == 'true':
            args_dict[key] = True
        elif value.lower() == 'false':
            args_dict[key] = False
        elif value.isdigit():
            args_dict[key] = int(value)
    logger.info(f"Parsed arguments: {args_dict}")
    return args_dict

# Create an MCP server
mcp = FastMCP("agentmode", lifespan=app_lifespan)

@click.command(context_settings={
    "ignore_unknown_options": True,
    "allow_extra_args": True,
})
@click.pass_context
def cli(ctx):
    """
    Command line interface to run the MCP server.
    SSE MCP servers would be nice, but VS Code doesn't support a start command for them yet
    so we use stdio.
    while mcp has a way to expose custom HTTP endpoints via their 'custom_routes', that uvicorn
    server only runs if you're using SSE,
    so we have to run uvicorn ourselves.
    """
    global kwargs
    kwargs = process_args(ctx)

    # Use asyncio.run only if no event loop is already running
    if not asyncio.get_event_loop().is_running():
        asyncio.run(mcp.run_stdio_async())
    else:
        asyncio.create_task(mcp.run_stdio_async())

if __name__ == "__main__":
    cli()
