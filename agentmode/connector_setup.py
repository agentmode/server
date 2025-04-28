import os
import copy

import gradio as gr
from benedict import benedict

from agentmode.logs import logger

# Load connectors from a TOML file
CONNECTORS_FILE = "connectors.toml"
CONNECTIONS_FILE = "connections.toml"

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
        {"type": "text", "label": "URL", "name": "url", "required": True},
        {"type": "text", "label": "Port", "name": "port", "required": True},
        {"type": "password", "label": "API Key", "name": "api_key", "required": True},
        {"type": "text", "label": "Headers", "name": "headers", "required": False}
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
    # flatten the connectors data so we can look up connectors by name
    list_connectors = {}
    for group_name, group_connectors in connectors.items():
        for connector_info in group_connectors:
            list_connectors[connector_info.get("name")] = connector_info
    logger.debug(f"Loaded connectors: {connectors}")
    logger.debug(f"Loaded connections: {connections}")
    return connectors, connections, list_connectors

connectors_data, connections_data, list_connectors = load_connectors()
selected_connector = None
selected_form_type = None
selected_connection_index = None
existing_connection_counter = 0

def create_group(group_name, connectors, type, state):
    """Create a group for each connector."""
    gr.Markdown(f"## {group_name}")
    if type == 'connections':
        global existing_connection_counter
        existing_connection_counter = 0
    # iterate through the list of connectors in groups of 4
    for i in range(0, len(connectors), 4):
        create_row(connectors[i:i+4], type, state)

def create_row(data, type, state):
    """Create a row for each connector."""
    with gr.Row() as row:
        for connector in data:
            create_card(connector, type, state)
        if len(data) < 4:
            for _ in range(4 - len(data)):
                with gr.Column():
                    pass
    return row

def create_card(input, type, state):
    """Create a card for each connector."""
    global list_connectors
    with gr.Column() as card:
        if type == 'connections':
            global existing_connection_counter
            counter = copy.deepcopy(existing_connection_counter)
            gr.Markdown(input.get("connector"))
            connector = list_connectors.get(input.get("connector"))
            if connector:
                logger.debug(f"adding existing connection for {input.get('connector')} with index {existing_connection_counter}")
                gr.Image(value=connector.get("logo"), show_label=False, interactive=False, scale=1, elem_classes=["logo"]).select(lambda: event_handler(connector, counter), None, state)
                existing_connection_counter += 1
            else:
                logger.error(f"Connector {input.get('connector')} not found in connectors data")
        elif type == 'connectors':
            connector = input
            gr.Markdown(connector.get("name"))
            gr.Image(value=connector.get("logo"), show_label=False, interactive=False, scale=1, elem_classes=["logo"]).select(lambda: event_handler(connector, None), None, state)
    return card
    
def create_gradio_interface():
    """Create the Gradio interface."""
    with gr.Blocks(title='agentmode', css_paths=['static/custom.css']) as demo:
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
            elif layout_type == 'form':
                with gr.Column():
                    gr.Markdown("## Form")
                    create_form(state)
    return demo

def handle_submit(*args, **kwargs):
    # Example validation logic
    logger.info(f"Form submitted with args: {args}, kwargs: {kwargs}")
    global selected_connector, selected_connection_index, selected_form_type, connections_data
    if selected_form_type in FORM_TYPES:
        # zip the form fields with their values
        form_data = dict(zip(FORM_TYPES[selected_form_type].keys(), args))
        logger.info(f"Form data: {form_data}")
    elif selected_form_type=='custom':
        form_fields = selected_connector.get("form_fields")
        if form_fields:
            form_data = dict(zip(form_fields.keys(), args))
    else:
        logger.error("Unknown form type")

    if form_data:
        form_data["connector"] = selected_connector.get("name")
        # update the connections_data with the new connection
        # and persist it to the TOML file
        if selected_connection_index is not None:
            connections_data['connections'][selected_connection_index] = form_data
        else:
            # generate a new connection ID
            connections_data['connections'].append(form_data)
        # save the updated connections data to the TOML file
        connections_data.to_toml(filepath=CONNECTIONS_FILE)
    return 'connectors'

def event_handler(connector, connection_index):
    logger.info(connector)
    global selected_connector, selected_connection_index, selected_form_type
    selected_connector = connector
    selected_connection_index = connection_index
    selected_form_type = connector.get("authentication_form_type")
    return 'form'

def create_form(state):
    global selected_connector, selected_connection_index, selected_form_type
    if selected_form_type=='custom':
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

            if field_type == "text":
                inputs.append(gr.Textbox(label=label, value=existing_connection.get(name, ""), interactive=True))
            elif field_type == "integer":
                inputs.append(gr.Number(label=label, value=existing_connection.get(name, 0), interactive=True))
            elif field_type == "password":
                inputs.append(gr.Textbox(label=label, value=existing_connection.get(name, ""), type="password", interactive=True))
            elif field_type == "json":
                inputs.append(gr.Textbox(label=label, value=existing_connection.get(name, ""), lines=5, placeholder="Enter JSON here", interactive=True))
            elif field_type == "checkbox":
                inputs.append(gr.Checkbox(label=label, value=existing_connection.get(name, False), interactive=True))

        with gr.Column():
            gr.Button("Submit", variant="primary").click(handle_submit, inputs, state)
            gr.Button("Go Back", variant="secondary").click(lambda: 'connectors', None, state)
    return column

if __name__ == "__main__":
    demo = create_gradio_interface()  # Assign the returned interface to `demo`
    demo.launch()  # Launch the interface