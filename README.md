# AgentMode ✨

AgentMode is an all-in-one Model Context Protocol (MCP) server that connects your coding AI to dozens of databases, data warehouses, data pipelines, cloud services, and more. This extension is designed to streamline your development workflow by providing seamless integration with various data and cloud platforms.

![flow diagram!](https://cdn.hashnode.com/res/hashnode/image/upload/v1746248830909/723435d9-255c-43a2-a2a2-1691a161e45f.webp "AgentMode flow diagram")

## Installation 👨‍💻

### quick start with VS code
1. Install our [VS Code extension](https://marketplace.visualstudio.com/items?itemName=agentmode.agentmode).
2. Click the 'Install' button next to the agentmode extension.
3. Start the MCP server via the Command Palette (`Ctrl+Shift+P` or `Cmd+Shift+P` on macOS), then type in 'MCP', then select 'MCP: List Servers' and click on agentmode.
4. Click on the 'AgentMode' text in the bottom-right status bar corner of VS Code to open a browser tab, sign in, and then setup your connections.

### without VS code (Python package)
1. Open the terminal and install uv with `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. `uv init`
3. `uv add agentmode`
4. `uv run agentmode`

<details>
<summary>MCP configuration for VS code</summary>
If you installed our VS Code extension, it will automatically create or update your settings.json file for you.
If you installed agentmode manually, please create a .vscode/settings.json file in your workspace, and replace ‘YOUR_INSTALLATION_FOLDER’ with the path to your uv environment below:

```json
{
    "mcp": {
        "servers": {
            "agentmode": {
                "command": "cd 'YOUR_INSTALLATION_FOLDER' && uv run agentmode",
                "env": {}
            }
        }
    }
}
```
</details>

<details>
<summary>MCP configuration for Cursor</summary>
Please create a \~/.cursor/mcp.json file in your home directory. This makes MCP servers available in all your Cursor workspaces.
Please replace 'YOUR_INSTALLATION_FOLDER' below with the folder you setup your uv environment in:
  
```json
{
    "mcpServers": {
        "inputs": [],
        "servers": {
            "agentmode": {
                "command": "cd 'YOUR_INSTALLATION_FOLDER' && uv run agentmode",
                "env": {}
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
        "inputs": [],
        "servers": {
            "agentmode": {
                "command": "cd 'YOUR_INSTALLATION_FOLDER' && uv run agentmode",
                "env": {}
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
- **Cloud Services**: AWS, Azure, Google Cloud, etc. (coming soon!)

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
