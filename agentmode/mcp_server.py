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

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with type-safe context"""
    connections = None
    if os.path.exists(CONNECTIONS_FILE):
        connections = benedict.from_toml(CONNECTIONS_FILE)
    if connections:
        connections = connections.get("connections")

    # Dynamically create a tool for each connection
    if connections:
        connection_name_counter = defaultdict(int) # each connection name may be suffixed with a counter to ensure uniqueness, in case of duplicates
        for connection in connections:
            logger.info(f"Creating tool for connection: {connection['connector']}")
            connection_name = connection.pop('connector', None)

            # Establish the database connection and store it in the mapping
            db = DatabaseConnection.create(connection_name, connection)
            if not await db.connect():
                logger.error(f"Failed to connect to {connection_name}")
                continue
            else:
                logger.info(f"Connected to {connection_name}")
            # Check if the connection name already exists in the mapping
            tool_name = f"database_query_{connection_name}"
            # Increment the counter for the connection name
            connection_name_counter[tool_name] += 1
            if connection_name_counter[tool_name] > 1:
                tool_name = f"{tool_name}_{connection_name_counter[tool_name]}"
            
            connection_mapping[tool_name] = db

            # Define a function dynamically using a closure
            def create_dynamic_tool(fn_name):
                async def dynamic_tool(query: str) -> str:
                    """Run a database query on the connection."""
                    db = connection_mapping.get(fn_name)
                    if not db:
                        logger.error(f"No database connection found for tool: {fn_name}")
                        return None
                    try:
                        logger.debug(f"Executing query: {query} in dynamic tool")
                        success_flag, result = await db.query(query)
                        if success_flag:
                            # convert the result pandas dataframe to a list of dictionaries
                            result = result.to_dict('records')
                            logger.debug(f"Query result: {result}")
                            # we don't need to convert to JSON string here, as the mcp server will handle it for us
                            return result
                        else:
                            logger.error(f"Query execution failed for {fn_name}")
                            return 'error'
                    except Exception as e:
                        logger.error(f"Error executing query: {e}")
                        return 'error' + str(e)
                return dynamic_tool

            # Create the dynamic tool function with the tool name
            tool_function = create_dynamic_tool(tool_name)

            # Register the function as an MCP tool
            tool_function.__name__ = tool_name
            tool_function.__doc__ = f"Run a query on the {connection_name} database."
            mcp.tool()(tool_function)

    try:
        yield AppContext(db=None)
    finally:
        # Cleanup on shutdown
        for db in connection_mapping.values():
            await db.disconnect()
        connection_mapping.clear()

# Create an MCP server
mcp = FastMCP("agentmode", lifespan=app_lifespan)

# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    logger.debug(f"Adding {a} and {b}")
    return a + b

@mcp.tool()
async def fetch_weather(city: str) -> str:
    """Fetch current weather for a city"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.weather.com/{city}")
        return response.text

# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"

@click.command()
def cli():
    """Prints a greeting."""
    click.echo("MCP server is running!")
    mcp.run()

if __name__ == "__main__":
    cli()