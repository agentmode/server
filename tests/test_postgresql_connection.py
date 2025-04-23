import asyncio
import subprocess
import time
import logging

import pytest

from agentmode.database import PostgreSQLConnection

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

CREDENTIALS = {
    "username": "test_user",
    "password": "password",
    "host": "127.0.0.1",
    "port": 5432,
    "database_name": "test_database",
    "read_only": False
}


@pytest.fixture(scope="module", autouse=True)
def setup_postgresql_container():
    logger.info("Setting up PostgreSQL container for testing")
    container_name = "test_postgresql"
    image = "postgres:17"
    env_vars = {
        "POSTGRES_USER": CREDENTIALS["username"],
        "POSTGRES_PASSWORD": CREDENTIALS["password"],
        "POSTGRES_DB": CREDENTIALS["database_name"],
    }

    # Run the PostgreSQL container
    command = [
        "docker", "run", "--rm", "--name", container_name,
        "-e", f"POSTGRES_USER={env_vars['POSTGRES_USER']}",
        "-e", f"POSTGRES_PASSWORD={env_vars['POSTGRES_PASSWORD']}",
        "-e", f"POSTGRES_DB={env_vars['POSTGRES_DB']}",
        "-p", f"{CREDENTIALS['port']}:5432", "-d", image
    ]

    subprocess.run(command, check=True)

    # Wait for the database to be ready
    time.sleep(10)

    yield

    # Stop the container after tests
    subprocess.run(["docker", "stop", container_name], check=True)


@pytest.mark.asyncio
async def test_postgresql_connection():
    logger.info("Starting test_postgresql_connection")
    connection = PostgreSQLConnection(settings=CREDENTIALS)
    connected = await connection.connect()
    logger.info("Connection status: %s", connected)
    assert connected, "Failed to connect to the PostgreSQL database"
    await connection.disconnect()
    logger.info("Disconnected from the database")


@pytest.mark.asyncio
async def test_postgresql_query():
    logger.info("Starting test_postgresql_query")
    connection = PostgreSQLConnection(settings=CREDENTIALS)
    connected = await connection.connect()
    logger.info("Connection status: %s", connected)
    assert connected, "Failed to connect to the PostgreSQL database"

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