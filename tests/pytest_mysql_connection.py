import asyncio
import subprocess
import time
import logging
import os, sys

import pytest
path_to_append = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(path_to_append)
path = os.environ.get("PATH") + ":" + path_to_append

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# setup a logger to log to the console
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

CREDENTIALS = {
	"username": "test_user",
	"password": "password",
	"host": "127.0.0.1",
	"port": 3306,
	"database_name": "test_database",
	"read_only": False
}

# Create server parameters for stdio connection
server_params_mysql = StdioServerParameters(
	command="uv",  # Executable
	args=[
		'run', 
		'mcp_server.py', 
		'--mysql+host', CREDENTIALS["host"],
		'--mysql+port', str(CREDENTIALS["port"]),
		'--mysql+username', CREDENTIALS["username"],
		'--mysql+password', CREDENTIALS["password"],
		'--mysql+database_name', CREDENTIALS["database_name"],
		'--mysql+read_only', str(CREDENTIALS["read_only"]).lower(),
	],  # we use our own version of stdio_client so that it does use_shell=True
	# append path_to_append to the PATH environment variable
	cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
)

"""@pytest.fixture(scope="module", autouse=True)
def setup_mysql_container():
	logger.info("Setting up MySQL container for testing")
	container_name = "test_mysql"
	image = "mysql:9"
	env_vars = {
		"MYSQL_USER": CREDENTIALS["username"],
		"MYSQL_PASSWORD": CREDENTIALS["password"],
		"MYSQL_DATABASE": CREDENTIALS["database_name"],
	}

	# Run the MySQL container
	command = [
		"docker", "run", "--rm", "--name", container_name,
		"-e", f"MYSQL_USER={env_vars['MYSQL_USER']}",
		"-e", f"MYSQL_PASSWORD={env_vars['MYSQL_PASSWORD']}",
		"-e", f"MYSQL_ROOT_PASSWORD={env_vars['MYSQL_PASSWORD']}",
		"-e", f"MYSQL_DATABASE={env_vars['MYSQL_DATABASE']}",
		"-p", f"{CREDENTIALS['port']}:3306", "-d", image
	]

	subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

	# Wait for the database to be ready
	time.sleep(10)

	yield

	# Stop the container after tests
	subprocess.run(["docker", "stop", container_name], check=True)"""

@pytest.mark.asyncio
async def test_mysql_tools():
	from contextlib import AsyncExitStack
	async with AsyncExitStack() as exit_stack:
		stdio, write = await exit_stack.enter_async_context(stdio_client(server_params_mysql))
		session = await exit_stack.enter_async_context(ClientSession(stdio, write))
		await session.initialize()
		result = await session.list_tools()
		assert result.tools

@pytest.mark.asyncio
async def test_mysql_query():
	from contextlib import AsyncExitStack
	async with AsyncExitStack() as exit_stack:
		stdio, write = await exit_stack.enter_async_context(stdio_client(server_params_mysql))
		session = await exit_stack.enter_async_context(ClientSession(stdio, write))
		await session.initialize()
		result = await session.call_tool("database_query_mysql_1", {"query": "SELECT 1 + 1 AS result"})
		assert result.get('result')==2, f"Expected 2, got {result.get('result')}"

if __name__ == "__main__":
	pytest.main(["-v", "--log-cli-level=INFO", "pytest_mysql_connection.py"])