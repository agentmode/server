import asyncio
import subprocess
import time
import logging

import pytest

from agentmode.database import MySQLConnection

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

CREDENTIALS = {
    "username": "test_user",
    "password": "password",
    "host": "127.0.0.1",
    "port": 3306,
    "database_name": "test_database",
    "read_only": False
}


@pytest.fixture(scope="module", autouse=True)
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
    subprocess.run(["docker", "stop", container_name], check=True)


@pytest.mark.asyncio
async def test_mysql_connection():
    logger.info("Starting test_mysql_connection")
    connection = MySQLConnection(settings=CREDENTIALS)
    connected = await connection.connect()
    logger.info("Connection status: %s", connected)
    assert connected, "Failed to connect to the MySQL database"
    await connection.disconnect()
    logger.info("Disconnected from the database")


@pytest.mark.asyncio
async def test_mysql_query():
    logger.info("Starting test_mysql_query")
    connection = MySQLConnection(settings=CREDENTIALS)
    connected = await connection.connect()
    logger.info("Connection status: %s", connected)
    assert connected, "Failed to connect to the MySQL database"

    query = "SELECT 1;"
    logger.info("Executing query: %s", query)
    success, result = await connection.query(query)
    logger.info("Query success: %s, Result: %s", success, result)
    assert success, "Query execution failed"
    assert result is not None, "Query result is None"
    assert not result.empty, "Query result is empty"

    await connection.disconnect()
    logger.info("Disconnected from the database")


if __name__ == "__main__":
    pytest.main()