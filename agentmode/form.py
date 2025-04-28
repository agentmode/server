import gradio as gr

FORM_TYPES = {
    "database": {
        "host": "text",
        "port": "integer",
        "username": "text",
        "password": "password"
    },
    "api": {
        "url": "text",
        "port": "integer",
        "api_key": "password",
        "headers": "json"
    },
}

def handle_submit(form_type, **kwargs):
    # Example validation logic
    if form_type == "database" and kwargs.get("host") and kwargs.get("port"):
        return True, "Form submitted successfully!"
    elif form_type == "api" and kwargs.get("url") and kwargs.get("api_key"):
        return True, "Form submitted successfully!"
    return False, "Form submission failed. Please check your inputs."

def create_form(form_type):
    form_fields = FORM_TYPES.get(form_type, {})
    with gr.Column() as column:
        for field, field_type in form_fields.items():
            if field_type == "text":
                gr.Textbox(label=field.capitalize(), value=field, interactive=True)
            elif field_type == "integer":
                gr.Number(label=field.capitalize(), value=field, interactive=True)
            elif field_type == "password":
                gr.Textbox(label=field.capitalize(), value=field, type="password", interactive=True)
            elif field_type == "json":
                gr.Textbox(label=field.capitalize(), value=field, lines=5, placeholder="Enter JSON here", interactive=True)
        # add a submit button
        gr.Button("Submit", variant="primary")
    return column

def gradio_form(form_type):
    with gr.Blocks() as app:
        create_form(form_type)
        
    return app

if __name__ == "__main__":
    demo = gradio_form('database')
    demo.launch()