import os

import uvicorn
from starlette.routing import Route
from starlette.applications import Starlette
from starlette.background import BackgroundTasks
from starlette.responses import (
	JSONResponse,
	PlainTextResponse,
	Response,
	HTMLResponse,
)
from starlette.middleware import Middleware
from starlette.authentication import (
	AuthenticationBackend,
	AuthenticationError,
	AuthCredentials,
)

PORT = os.getenv("PORT", 13000)

import gradio as gr

from logs import logger
from connectors import create_gradio_interface
from form import gradio_form

async def startup():
	"""
	aiohttp.ClientSession should be created once for the lifetime
	of the server in order to benefit from connection pooling
	"""
	pass

async def shutdown():
	logger.debug("shutdown called")
	pass

async def connection_form(request):
	"""
	Handle the connection form submission.
	"""
	if request.method == "GET":
		return JSONResponse({"status": "success", "message": "GET request received"})
	elif request.method == "POST":
		data = await request.json()
		logger.debug(f"Received form data: {data}")
		return JSONResponse({"status": "success", "data": data})

async def ping(request):
	"""
	return 200 OK
	"""
	return PlainTextResponse("OK", status_code=200)

async def test(request):
	"""
	return 200 OK
	"""
	form = gradio_form('database')
	result = form.launch(share=False, inline=True, prevent_thread_lock=True)
	return HTMLResponse(result[0], status_code=200)
	
routes = [
	Route("/connection_form/{id}", endpoint=connection_form, methods=['GET']), # get credentials for an existing connection
	Route("/connection_form", endpoint=connection_form, methods=['POST']), # save credentials for a new connection
	Route("/health_check", endpoint=ping, methods=['GET']),
	Route("/test", endpoint=test, methods=['GET']),
]

connectors_grid = create_gradio_interface()
web_app = Starlette(routes=routes, on_startup=[startup], on_shutdown=[shutdown], debug=True)
web_app = gr.mount_gradio_app(web_app, connectors_grid, path="/connectors")

if __name__ == "__main__":
	uvicorn.run(web_app, host="0.0.0.0", port=PORT, log_level="debug")