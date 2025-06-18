# AgentMode ✨

AgentMode is an all-in-one Model Context Protocol (MCP) server that connects your coding AI to dozens of databases, data warehouses, and data pipelines.

![flow diagram!](https://cdn.hashnode.com/res/hashnode/image/upload/v1746248830909/723435d9-255c-43a2-a2a2-1691a161e45f.webp "AgentMode flow diagram")

## Installation 👨‍💻

### Quick start for VS Code, Cursor, and VS Code Insiders
VS Code Button (see the instructions below for how to add other databases)
Cursor button
VS Code Insiders button

### Configuring database connections

Start with MCP server by installing uv if you haven't already, then run: `uvx agentmode`
Pass the following keyword arguments for each database you'd like to connect to, with the name of the database as the prefix before the ':'

You can configure each database connection by specifying the following parameters:

- `host`
- `port`
- `username`
- `password`
- `database_name`
- `read_only`

For example, to configure a MySQL connection, use the following arguments:

```bash
uvx agentmode \
--mysql:host host \
--mysql:port port \
--mysql:username username \
--mysql:password password \
--mysql:database_name database_name \
--mysql:read_only true
```

The full list of supported databases is:
- `mysql`
- `postgresql`
- `bigquery`
- `redshift`
- `snowflake`
- `mariadb`
- `vitess`
- `timescaledb`
- `sqlserver`
- `cockroachdb`
- `oracle`
- `sap_hana`
- `clickhouse`
- `presto`
- `hive`
- `trino`
- `bigquery`
- `redshift`
- `snowflake`
- `databricks`
- `teradata`
- `aws_athena`

<details>
<summary>Manual MCP configuration for VS Code</summary>
Please create a .vscode/settings.json file in your workspace, and add the following:
```json
{
    "mcp": {
        "servers": {
            "agentmode": {
                "command": "uvx agentmode",
                "args": [
                    "--mysql:host", "host",
                    "--mysql:port", "port",
                    "--mysql:username", "username",
                    "--mysql:password", "password",
                    "--mysql:database_name", "database_name",
                    "--mysql:read_only", "true"
                ],
                "env": {}
            }
        }
    }
}
```
<details>


<summary>Manual MCP configuration for Cursor</summary>
Please create a \~/.cursor/mcp.json file in your home directory. This makes MCP servers available in all your Cursor workspaces.
  
```json
{
    "mcpServers": {
        "inputs": [],
        "servers": {
            "agentmode": {
                "command": "uvx agentmode",
                "args": [
                    "--mysql:host", "host",
                    "--mysql:port", "port",
                    "--mysql:username", "username",
                    "--mysql:password", "password",
                    "--mysql:database_name", "database_name",
                    "--mysql:read_only", "true"
                ]
            }
        }
    }
}

```
</details>

<details>
<summary>MCP configuration for Windsurf</summary>
Open the file ~/.codeium/windsurf/mcp_config.json
Add the code below to the JSON file.
Press the refresh button in Windsurf.
Please replace 'YOUR_INSTALLATION_FOLDER' below with the folder you setup your uv environment in:

```json
{
    "mcpServers": {
        "servers": {
            "agentmode": {
                "command": "uvx agentmode",
                "args": [
                    "--mysql:host", "host",
                    "--mysql:port", "port",
                    "--mysql:username", "username",
                    "--mysql:password", "password",
                    "--mysql:database_name", "database_name",
                    "--mysql:read_only", "true"
                ]
            }
        }
    }
}

```
</details>

## MCP (Model Context Protocol) 🌐

AgentMode leverages the [Model Context Protocol](https://modelcontextprotocol.io) (MCP) to enable your coding AI to:
- Access and query databases and data warehouses.
- Interact with data pipelines for real-time or batch processing.
- Use a web browser.
- See logs from your production services.
- Connect to cloud services for storage, computation, and more.

## Connections 🔌

![connections setup!](https://cdn.hashnode.com/res/hashnode/image/upload/v1746249095886/cf437270-7eb4-4e5a-ac19-7165cdcd2eeb.png?auto=compress,format&format=webp "AgentMode connections")

AgentMode supports a wide range of connections, including:
- **Databases**: MySQL, PostgreSQL, etc.
- **Data Warehouses**: Snowflake, BigQuery, Redshift, etc.
- **Data Pipelines**: Airflow, Prefect, etc.

To configure connections, follow these steps:
1. Start the MCP server and go to `http://localhost:13000/setup`
2. Click on the icon of the connection you'd like to setup.
3. Fill out the connection details and credentials (all credentials are stored locally on your machine).
4. Any required dependencies will be installed on-the-fly.

## Help 🛟

If you encounter any issues or have questions, you can:
- See the [documentation](https://docs.agentmode.app/default-guide/installation/server-installation).
- Open an issue in the [GitHub repository](https://github.com/agentmode/extension).
- Chat with us on our [Discord server](https://discord.gg/qwDjr29q).

## Contributing 💬
- add more connectors & tests
