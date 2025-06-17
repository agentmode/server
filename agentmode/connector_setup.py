import os
import copy
import importlib.resources
import uuid

import gradio as gr
from benedict import benedict
import platformdirs

from agentmode.logs import logger
from agentmode.package_manager import install_dependencies
from agentmode.mcp_server import setup_connections

# Load connectors from a TOML file
connectors_path = importlib.resources.files('agentmode').joinpath('connectors.toml')
CONNECTORS_FILE = str(connectors_path)
HOME_DIRECTORY = platformdirs.user_data_dir('agentmode', ensure_exists=True)
CONNECTIONS_FILE = os.path.join(HOME_DIRECTORY, "connections.toml")
CARDS_PER_ROW = 8

# beyond these standard forms, some connectors have their own defined in connectors.toml
FORM_TYPES = {
    "database": [
        {"type": "text", "label": "Host", "name": "host", "required": True},
        {"type": "integer", "label": "Port", "name": "port", "required": True},
        {"type": "text", "label": "Username", "name": "username", "required": True},
        {"type": "password", "label": "Password", "name": "password", "required": True},
        {"type": "text", "label": "Database Name", "name": "database_name", "required": True},
        {"type": "checkbox", "label": "Only Allow Read-Only Queries", "name": "read_only", "required": False}
    ],
    "api": [
        {"type": "text", "label": "Server URL", "name": "server_url", "required": True},
        {"type": "integer", "label": "Port", "name": "port", "required": False},
        {"type": "select", "label": "Authentication Type", "name": "authentication_type", 
         "options": ["None", "API key in headers", "Basic Auth", "Bearer Token", "Digest Auth"], "required": True,
         "click_mapping": {
             "None": {"username": False, "password": False, "headers": False, "token": False},
             "API key in headers": {"username": False, "password": False, "headers": True, "token": False},
             "Basic Auth": {"username": True, "password": True, "headers": False, "token": False},
             "Bearer Token": {"username": False, "password": True, "headers": False, "token": True},
             "Digest Auth": {"username": True, "password": True, "headers": False, "token": False}
         }
        },
        {"type": "text", "label": "Username", "name": "username", "required": False, "hidden": True},
        {"type": "password", "label": "Password", "name": "password", "required": False, "hidden": True},
        {"type": "text", "label": "Bearer Token", "name": "token", "required": False, "hidden": True},
        {"type": "json", "label": "Headers (as JSON dictionary)", "name": "headers", "required": False, "hidden": True}
        # actual username/password/header fields will be added dynamically based on the selected authentication type
    ],
}

def load_connectors():
    # read the TOML file using benedict
    connectors = benedict.from_toml(CONNECTORS_FILE)
    if os.path.exists(CONNECTIONS_FILE):
        connections = benedict.from_toml(CONNECTIONS_FILE)
    else:
        connections = benedict({"connections": []})
        connections.to_toml(filepath=CONNECTIONS_FILE)
    # flatten the connectors data so we can look up connectors by label or name
    list_connectors = {}
    for group_name, group_connectors in connectors.items():
        for connector_info in group_connectors:
            list_connectors[connector_info.get("label", connector_info.get("name"))] = connector_info
    logger.debug(f"Loaded connectors: {connectors}")
    logger.debug(f"Loaded connections: {connections}")
    return connectors, connections, list_connectors

connectors_data, connections_data, list_connectors = load_connectors()
selected_connector = None
selected_form_type = None
selected_connection_index = None
existing_connection_counter = 0
selected_authentication_type = None
progress_bar = None
server_url = None # for API form persistence
port = None # for API form persistence
form_field_keys = []

def create_group(group_name, connectors, type, state):
    """Create a group for each connector."""
    gr.Markdown(f"## {group_name}")
    if type == 'connections':
        global existing_connection_counter
        existing_connection_counter = 0
    # iterate through the list of connectors in groups of CARDS_PER_ROW
    for i in range(0, len(connectors), CARDS_PER_ROW):
        create_row(connectors[i:i+CARDS_PER_ROW], type, state)

def create_row(data, type, state):
    """Create a row for each connector."""
    with gr.Row() as row:
        for connector in data:
            create_card(connector, type, state)
        if len(data) < CARDS_PER_ROW:
            for _ in range(CARDS_PER_ROW - len(data)):
                with gr.Column(min_width=200, elem_classes=["column"]): # will wrap if not enough space
                    pass
    return row

def create_card(input, type, state):
    """Create a card for each connector."""
    global list_connectors
    with gr.Column(min_width=200, elem_classes=["column"]) as card:
        if type == 'connections':
            global existing_connection_counter
            counter = copy.deepcopy(existing_connection_counter)
            connector = list_connectors.get(input.get("connector"))
            gr.Markdown(connector.get("label", connector.get("name")))
            if connector:
                image_file_path = str(importlib.resources.files('agentmode').joinpath(connector.get("logo")))
                logger.debug(f"adding existing connection for {input.get('connector')} with index {existing_connection_counter}")
                gr.Image(value=image_file_path, show_label=False, interactive=False, scale=1, elem_classes=["logo"]).select(lambda: event_handler(connector, counter), None, state)
                existing_connection_counter += 1
            else:
                logger.error(f"Connector {input.get('connector')} not found in connectors data")
        elif type == 'connectors':
            connector = input
            gr.Markdown(connector.get("label", connector.get("name")))
            image_file_path = str(importlib.resources.files('agentmode').joinpath(connector.get("logo")))
            gr.Image(value=image_file_path, show_label=False, interactive=False, scale=1, elem_classes=["logo"]).select(lambda: event_handler(connector, None), None, state)
    return card
    
def create_gradio_interface():
    """Create the Gradio interface."""
    css_file_path = str(importlib.resources.files('agentmode').joinpath('resources/css/custom.css'))
    with gr.Blocks(title='agentmode', css_paths=[css_file_path]) as demo:
        gr.Markdown("# Connector Management")

        state = gr.State('connectors')

        @gr.render(inputs=[state])
        def dynamic_layout(layout_type):
            if layout_type == 'connectors':
                # first load any existing connections
                if connections_data['connections']:
                    create_group("Existing Connections", connections_data['connections'], 'connections', state)
                # then load all available connectors
                for group_name, group_connectors in connectors_data.items():
                    create_group(group_name, group_connectors, 'connectors', state)
            elif layout_type == 'form' or 'form_refreshed' in layout_type:
                with gr.Column():
                    gr.Markdown("## Form")
                    create_form(state)
    return demo

async def handle_submit(*args, **kwargs):
    logger.info(f"Form submitted with args: {args}, kwargs: {kwargs}")
    global selected_connector, selected_connection_index, selected_form_type, connections_data, form_field_keys, progress_bar

    # zip the form fields with their values
    form_data = dict(zip(form_field_keys, args))
    logger.info(f"Form data: {form_data}")

    if form_data:
        form_data["connector"] = selected_connector.get("name")
        form_data["connection_type"] = selected_connector.get("connection_type")
        # update the connections_data with the new connection
        # and persist it to the TOML file
        if selected_connection_index is not None:
            connections_data['connections'][selected_connection_index] = form_data
        else:
            # generate a new connection
            form_data["uuid"] = str(uuid.uuid4())
            connections_data['connections'].append(form_data)
        # save the updated connections data to the TOML file
        connections_data.to_toml(filepath=CONNECTIONS_FILE)

        # install any required python packages
        if package_names := selected_connector.get("requires_python_packages"):
            logger.info(f"Installing packages: {package_names}")
            # make the progress bar visible
            gr.Warning('Installing package dependencies...', duration=5)

            successfull_install = install_dependencies(package_names)
            if not successfull_install:
                # display an alert in gradio if the installation fails
                raise gr.Error("Failed to install dependencies, please see the logs", duration=5)
            
        # create the new MCP resources/tools
        await setup_connections()
    return 'connectors'

def event_handler(connector, connection_index):
    logger.info(connector)
    global selected_connector, selected_connection_index, selected_form_type
    selected_connector = connector
    selected_connection_index = connection_index
    selected_form_type = connector.get("authentication_form_type")
    return 'form'

def create_form(state):
    logger.debug(f"state in form: {state.value}")
    global selected_connector, selected_connection_index, selected_form_type, selected_authentication_type, form_field_keys, server_url, port, progress_bar
    form_field_keys = []
    if selected_form_type == 'custom':
        form_fields = selected_connector.get('form_fields')
    else:
        form_fields = FORM_TYPES.get(selected_form_type, {})
    existing_connection = {}
    if selected_connection_index is not None:
        # pre-fill the form with existing connection data
        logger.debug(f"Selected connection index: {selected_connection_index}")
        existing_connection = connections_data['connections'][selected_connection_index]

    with gr.Column() as column:
        inputs = []
        for field_info in form_fields:
            label = field_info["label"]
            name = field_info["name"]
            required = field_info["required"]
            field_type = field_info["type"]
            hidden = field_info.get("hidden", False)

            if hidden:
                continue

            form_field_keys.append(field_info["name"])

            if field_type == "text":
                textbox = gr.Textbox(label=label, value=existing_connection.get(name, server_url), interactive=True)
                if name == "server_url":
                    textbox.input(lambda x: globals().__setitem__('server_url', x), inputs=[textbox], outputs=None)
                inputs.append(textbox)
            elif field_type == "integer":
                number = gr.Number(label=label, value=existing_connection.get(name, port), interactive=True)
                if name == "port":
                    number.change(lambda x: globals().__setitem__('port', x), inputs=[number], outputs=None)
                inputs.append(number)
            elif field_type == "password":
                inputs.append(gr.Textbox(label=label, value=existing_connection.get(name, ""), type="password", interactive=True))
            elif field_type == "json":
                json_field = gr.Textbox(label=label, value=existing_connection.get(name, ""), lines=5, placeholder="Enter JSON here", interactive=True)
                if name == "headers":
                    json_field.placeholder = "{\"x-api-key\": \"YOUR API KEY HERE\"}"
                inputs.append(json_field)
            elif field_type == "checkbox":
                inputs.append(gr.Checkbox(label=label, value=existing_connection.get(name, ""), interactive=True))
            elif field_type == "select":
                options = field_info.get("options", [])
                click_mapping = field_info.get("click_mapping", {})
                dropdown = gr.Dropdown(label=label, choices=options, value=existing_connection.get(name, selected_authentication_type), interactive=True)

                if click_mapping:
                    def update_form(selected_option):
                        global selected_authentication_type
                        selected_authentication_type = selected_option
                        logger.debug(f"Selected authentication type: {selected_authentication_type}")
                        if selected_authentication_type:
                            for field in form_fields:
                                if field["name"] in click_mapping.get(selected_option, []):
                                    logger.debug(f"Updating field {field['name']} based on selected option {selected_option}")
                                    field["hidden"] = not click_mapping[selected_option][field["name"]]
                                else:
                                    if "hidden" in field.keys():
                                        field["hidden"] = True
                            # Re-render the form with the updated fields without returning a value
                            return f'form_refreshed_{selected_authentication_type}' # we append the authentication type so anytime the auth type changes it'll refresh
                        return 'form'

                    dropdown.input(update_form, inputs=[dropdown], outputs=state)

                inputs.append(dropdown)

        with gr.Column():
            gr.Button("Submit", variant="primary").click(handle_submit, inputs, state)
            gr.Button("Go Back", variant="secondary").click(lambda: 'connectors', None, state)
    return column

if __name__ == "__main__":
    demo = create_gradio_interface()  # Assign the returned interface to `demo`
    demo.launch()  # Launch the interface