# AgentMode ✨

AgentMode is an all-in-one Model Context Protocol (MCP) server that connects your coding AI to dozens of databases, data warehouses, and data pipelines.

![flow diagram!](https://cdn.hashnode.com/res/hashnode/image/upload/v1746248830909/723435d9-255c-43a2-a2a2-1691a161e45f.webp "AgentMode flow diagram")

## Installation 👨‍💻

### Quick start for VS Code, and VS Code Insiders

[![Install in VS Code](https://img.shields.io/badge/VS_Code-VS_Code?style=flat-square&label=Install%20Server&color=0098FF)](https://insiders.vscode.dev/redirect?url=vscode:mcp/install?%7B%22name%22%3A%22agentmode%22%2C%22command%22%3A%22uvx%20agentmode%22%2C%22args%22%3A%5B%22--mysql%3Ahost%22%2C%22host%22%2C%22--mysql%3Aport%22%2C%22port%22%2C%22--mysql%3Ausername%22%2C%22username%22%2C%22--mysql%3Apassword%22%2C%22password%22%2C%22--mysql%3Adatabase_name%22%2C%22database_name%22%2C%22--mysql%3Aread_only%22%2C%22true%22%5D%7D)

[![Install in VS Code Insiders](https://img.shields.io/badge/VS_Code_Insiders-VS_Code_Insiders?style=flat-square&label=Install%20Server&color=24bfa5)](https://insiders.vscode.dev/redirect?url=vscode-insiders:mcp/install?%7B%22name%22%3A%22agentmode%22%2C%22command%22%3A%22uvx%20agentmode%22%2C%22args%22%3A%5B%22--mysql%3Ahost%22%2C%22host%22%2C%22--mysql%3Aport%22%2C%22port%22%2C%22--mysql%3Ausername%22%2C%22username%22%2C%22--mysql%3Apassword%22%2C%22password%22%2C%22--mysql%3Adatabase_name%22%2C%22database_name%22%2C%22--mysql%3Aread_only%22%2C%22true%22%5D%7D)

(replace the credentials in the config with your own, and see the instructions below for how to add other databases)

### Configuring database connections

Start with MCP server by [installing uv](https://docs.astral.sh/uv/getting-started/installation/) if you haven't already, then run: `uvx agentmode` from your terminal.

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
                ]
            }
        }
    }
}
```
</details>

<details>
<summary>Manual MCP configuration for Cursor</summary>
Copy and paste this link into your browser: 
cursor://anysphere.cursor-deeplink/mcp/install?name=agentmode&config=eyJhZ2VudG1vZGUiOnsiY29tbWFuZCI6InV2eCBhZ2VudG1vZGUiLCJhcmdzIjpbIi0tbXlzcWw6aG9zdCIsImhvc3QiLCItLW15c3FsOnBvcnQiLCJwb3J0IiwiLS1teXNxbDp1c2VybmFtZSIsInVzZXJuYW1lIiwiLS1teXNxbDpwYXNzd29yZCIsInBhc3N3b3JkIiwiLS1teXNxbDpkYXRhYmFzZV9uYW1lIiwiZGF0YWJhc2VfbmFtZSIsIi0tbXlzcWw6cmVhZF9vbmx5IiwidHJ1ZSJdfX0=

OR 

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

## Help 🛟

If you encounter any issues or have questions, you can:
- See the [documentation](https://docs.agentmode.app/default-guide/installation/server-installation).
- Open an issue in the [GitHub repository](https://github.com/agentmode/extension).
- Chat with us on our [Discord server](https://discord.gg/qwDjr29q).

## Contributing 💬
- add more connectors & tests
