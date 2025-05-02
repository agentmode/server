import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
import multiprocessing
from collections import defaultdict
import asyncio
import signal

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

from agentmode.logs import logger
from agentmode.database import DatabaseConnection
from agentmode.api.api_connection import APIConnection
from agentmode.connector_setup import create_gradio_interface

CONNECTIONS_FILE = "connections.toml"
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
        
        # get the API information from api/connectors/{connection_name}.toml or .json
        api_info = benedict.from_json(os.path.join(os.path.dirname(__file__), f"api/connectors/{connection_name}.json"))
        if not api_info:
            logger.error(f"Failed to load API information for {connection_name}")
            return None
        #logger.info(f"Loaded API information for {connection_name}: {api_info}")
        
        # Create the APIConnection instance
        api_connection = APIConnection.create(
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
            server_url=connection.get("server_url"), # comes from the form
        )

        api_connection.generate_mcp_resources_and_tools(mcp, connection_name_counter)
    except Exception as e:
        logger.error(e, exc_info=True)
        return None

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with type-safe context"""
    connections = None
    if os.path.exists(CONNECTIONS_FILE):
        connections = benedict.from_toml(CONNECTIONS_FILE)
    if connections:
        connections = connections.get("connections", [])

    # Dynamically create tools/resources for each connection
    connection_name_counter = defaultdict(int) # each connection name may be suffixed with a counter to ensure uniqueness, in case of duplicates
    for connection in connections:
        logger.info(f"Creating tool for connection: {connection['connector']}")
        connection_name = connection.pop('connector', None)
        connection_type = connection.pop('connection_type', None)

        if connection_type=='database': # Establish the database connection and store it in the mapping
            await setup_database_connection(connection_name, connection, mcp, connection_name_counter)
        elif connection_type=='api':
            await setup_api_connection(connection_name, connection, mcp, connection_name_counter)

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

# Create an MCP server
mcp = FastMCP("agentmode", lifespan=app_lifespan)

connectors_grid = create_gradio_interface()
app = Starlette(
    routes=[
        Route("/health_check", endpoint=ping, methods=['GET']),
    ],
    debug=True,
)
app = gr.mount_gradio_app(app, connectors_grid, path="/setup")

config = Config("mcp_server:app", host="0.0.0.0", port=PORT, log_config="resources/log_config.json")
server = uvicorn.Server(config)

@click.command()
def cli():
    """
    Command line interface to run the MCP server.
    SSE MCP servers would be nice, but VS Code doesn't support a start command for them yet
    so we use stdio.
    while mcp has a way to expose custom HTTP endpoints via their 'custom_routes', that uvicorn
    server only runs if you're using SSE,
    so we have to run uvicorn ourselves.
    """
    async def start_server():
        click.echo("starting MCP server...")
        await asyncio.gather(
            server.serve(),
            mcp.run_stdio_async()  # Directly call the async function to avoid nested event loops
        )

    def handle_exit(signum, frame):
        click.echo("Shutting down MCP server...")
        loop = asyncio.get_event_loop()
        tasks = asyncio.all_tasks(loop)
        for task in tasks:
            task.cancel()
        loop.stop()

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    # Use asyncio.run only if no event loop is already running
    if not asyncio.get_event_loop().is_running():
        asyncio.run(start_server())
    else:
        asyncio.create_task(start_server())  # Use create_task if an event loop is already running

if __name__ == "__main__":
    cli()
