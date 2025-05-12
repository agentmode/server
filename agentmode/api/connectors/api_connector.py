from dataclasses import dataclass, field
import base64

from agentmode.logs import logger

subclasses = {}

@dataclass
class APIConnector():
	settings: dict
	create_engine_kwargs: dict = field(default_factory=dict)  # Use default_factory for mutable default

	def __init_subclass__(cls, **kwargs):
		super().__init_subclass__(**kwargs)
		subclasses[cls.name] = cls

	@classmethod
	def create(cls, name, settings, **kwargs):
		if name not in subclasses.keys():
			logger.info(f'no subclass for APIConnector name {name}, returning base class')
			return APIConnector(settings=settings, **kwargs)
		instance = subclasses[name](settings=settings, **kwargs)
		return instance

	def base64_decode(self, data, key_to_decode):
		"""
		Decode base64 encoded data.
		"""
		if key_to_decode in data:
			data[key_to_decode] = base64.b64decode(data[key_to_decode]).decode('utf-8')
		return data

	def _parse_keypath(self, keypath):
		"""
		Parse a keypath string into a list of keys.
		"""
		return keypath.split('.')
	
	def _apply_filters(self, data, keypath):
		"""
		Recursively apply filters to the data based on the keypath.
		"""
		if not keypath:
			return data

		key = keypath[0]
		
		try:
			if key.endswith('[]'):
				key = key[:-2]
				if isinstance(data, list):
					# keypath[1:] is the remaining path after the current key
					return [self._apply_filters(item, keypath[1:]) for item in data if key in item]

			if isinstance(data, dict) and key in data:
				# keypath[1:] is the remaining path after the current key
				return {key: self._apply_filters(data[key], keypath[1:])}

			logger.warning(f"Key '{key}' not found in the current data structure.")
		except Exception as e:
			logger.error(f"Error while processing key '{key}': {e}", exc_info=True)

		return None

	def post_process_response(self, response, filters):
		"""
		Filters the response to include only the specified keys while maintaining the structure.
		Handles nested filters and lists using recursion.
		"""
		if isinstance(response, list):
			# If the response is a list, process each item individually
			filtered_response = [self.post_process_response(item, filters) for item in response]
		elif isinstance(response, dict):
			filtered_response = {}
			for filter in filters:
				keypath = self._parse_keypath(filter)
				result = self._apply_filters(response, keypath)
				if result:
					filtered_response.update(result)

		return filtered_response