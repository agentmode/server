import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
import json
from collections import defaultdict

import click
from benedict import benedict
import httpx
from mcp.server.fastmcp import FastMCP, Context

from agentmode.logs import logger
from agentmode.database import DatabaseConnection
from agentmode.api.api_connection import APIConnection

CONNECTIONS_FILE = "connections.toml"
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

# Create an MCP server
mcp = FastMCP("agentmode", lifespan=app_lifespan)

@click.command()
def cli():
    """Prints a greeting."""
    click.echo("MCP server is running!")
    mcp.run()

if __name__ == "__main__":
    cli()