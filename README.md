# AgentMode VS Code Extension

AgentMode is an all-in-one Model Context Protocol (MCP) server that connects your coding AI to databases, data warehouses, data pipelines, cloud services, and more. This extension is designed to streamline your development workflow by providing seamless integration with various data and cloud platforms.

## Installation

1. Open Visual Studio Code.
2. Go to the Extensions view by clicking on the Extensions icon in the Activity Bar on the side of the window.
3. In the `Search Extensions in Marketplace` textbox, type in 'agentmode' and click Enter.
5. Click the 'Install' button next to the agentmode extension.
6. Start the MCP server via the Command Palette (`Ctrl+Shift+P` or `Cmd+Shift+P` on macOS), then type in 'MCP', then select 'MCP: List Servers' and click on agentmode.
7. Click on the 'AgentMode' text in the bottom-right corner of VS Code to open a browser tab, and sign in.

## MCP (Model Context Protocol)

AgentMode leverages the [Model Context Protocol](https://modelcontextprotocol.io) (MCP) to enable your coding AI to:
- Access and query databases and data warehouses.
- Interact with data pipelines for real-time or batch processing.
- Use a web browser.
- See logs from your production services.
- Connect to cloud services for storage, computation, and more.

## Connections

AgentMode supports a wide range of connections, including:
- **Databases**: MySQL, PostgreSQL, etc.
- **Data Warehouses**: Snowflake, BigQuery, Redshift, etc.
- **Data Pipelines**: Airflow, Prefect, etc.
- **Cloud Services**: AWS, Azure, Google Cloud, etc.

To configure connections, follow these steps:
1. Start the MCP server and go to `http://localhost:13000/setup`
2. Click on the icon of the connection you'd like to setup.
3. Fill out the connection details and credentials (all credentials are stored locally on your machine).
4. Any required dependencies will be installed on-the-fly.

## Help

If you encounter any issues or have questions, you can:
- Open an issue in the [GitHub repository](https://github.com/agentmode/extension).
- Chat with us on our [Discord server]().