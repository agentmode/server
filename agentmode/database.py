import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, create_engine
import pandas as pd

from agentmode.logs import logger

subclasses = {}

@dataclass
class DatabaseConnection:
	settings: dict
	threadpool: ThreadPoolExecutor = None
	create_engine_kwargs: dict = field(default_factory=dict)  # Use default_factory for mutable default

	def __init_subclass__(cls, **kwargs):
		super().__init_subclass__(**kwargs)
		subclasses[cls.platform] = cls

	@classmethod
	def create(cls, platform, settings, **kwargs):
		if platform not in subclasses.keys():
			raise ValueError('Unknown DatabaseConnection platform {}'.format(platform))
		instance = subclasses[platform](settings=settings, **kwargs)
		if instance.driver_type == 'sync':
			instance.threadpool = ThreadPoolExecutor()
		return instance

	def is_read_only_query(self, query_string: str, method="blocklist") -> bool:
		"""
		Determine if the query is a read-only query.
		There are 2 approaches: use a blocklist or an allowlist of query types
		the blocklist is easier to maintain for all database types, but the allowlist is more secure
		uses the sqlglot library for fast query parsing
		"""
		from sqlglot import parse, parse_one, exp
		try:
			if method == "blocklist":
				expression_tree = parse_one(query_string)

				# Define the types of expressions that indicate a write operation
				write_operations = (
					exp.Insert,
					exp.Update,
					exp.Delete,
					exp.Create,
					exp.Drop,
					exp.Alter,
					exp.Truncate,
				)

				# Check if the root expression is a write operation
				if isinstance(expression_tree, write_operations):
					return False

				# Traverse the AST and check for any write operation expressions
				for node, _, _ in expression_tree.walk():
					if isinstance(node, write_operations):
						return False

				# If no write operations are found, the query is read-only
				return True
			elif method == "allowlist":
				# only allows SELECT, ANALYZE, VACUUM, EXPLAIN SELECT, and SHOW queries
				query = parse(query_string)
				if not query:
					return False
				for q in query:
					if q['type'] == 'SELECT':
						return True
					elif q['type'] == 'SHOW':
						return True
					elif q['type'] == 'ANALYZE':
						return True
					elif q['type'] == 'VACUUM':
						return True
					elif q['type'] == 'EXPLAIN':
						if q['subquery']:
							return True
		except Exception as e:
			logger.error(f"Error parsing query: {e}")
			return False
		return False

	async def connect(self):
		"""
		Initialize the database connection.
		we do this in a separate method so we can return a boolean value on success/failure
		"""
		try:
			if self.driver_type == 'async':
				self.engine = create_async_engine(self.database_uri, echo=False, future=True, **self.create_engine_kwargs) # echo is False, as we don't want to log to stdout (it interferes with MCP on stdio)
				self.session_factory = sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)
			elif self.driver_type == 'sync':
				def sync_connect():
					self.engine = create_engine(self.database_uri, echo=False, future=True, **self.create_engine_kwargs)
					self.connection = self.engine.connect()
				await asyncio.get_event_loop().run_in_executor(self.threadpool, sync_connect)
			return True
		except Exception as e:
			logger.error(f"Failed to create database connection: {e}")
			return False

	async def query(self, query_string: str) -> pd.DataFrame:
		try:
			if self.settings.get('read_only', True):
				if not self.is_read_only_query(query_string):
					logger.error(f"Query is not read-only, not executing: {query_string}")
					return False, None
			logger.debug(f"Executing query: {query_string}")
			if self.driver_interface == 'sqlalchemy':
				if self.driver_type == 'async':
					async with self.session_factory() as session:
						result = await session.execute(text(query_string))
						# Convert result to pandas DataFrame
						df = pd.DataFrame(result.fetchall(), columns=result.keys())
						return True, df
				elif self.driver_type == 'sync':
					def sync_query():
						result = self.connection.execute(text(query_string))
						return pd.DataFrame(result.fetchall(), columns=result.keys())
					df = await asyncio.get_event_loop().run_in_executor(self.threadpool, sync_query)
					return True, df
			elif self.driver_interface == 'dbapi':
				if self.driver_type == 'sync':
					cur = self.connection.cursor()
					cur.execute(query_string)
					rows = cur.fetchall()
					columns = [desc[0] for desc in cur.description]
					df = pd.DataFrame(rows, columns=columns)
					cur.close()
					return True, df
				elif self.driver_type == 'async':
					cur = await self.connection.cursor()
					await cur.execute(query_string)
					rows = await cur.fetchall()
					columns = [desc[0] for desc in await cur.description()]
					df = pd.DataFrame(rows, columns=columns)
					await cur.close()
					return True, df
		except Exception as e:
			# Log the error and re-raise it
			logger.error(f"Query failed: {e}")
			return False, None

	async def disconnect(self):
		if self.driver_interface == 'sqlalchemy':
			if self.driver_type == 'async':
				await self.engine.dispose()
			else:
				def sync_disconnect():
					self.connection.close()
					self.engine.dispose()
				await asyncio.get_event_loop().run_in_executor(self.threadpool, sync_disconnect)
		elif self.driver_interface == 'dbapi':
			if self.driver_type == 'async':
				await self.connection.close()
			else:
				def sync_disconnect():
					self.connection.close()
				await asyncio.get_event_loop().run_in_executor(self.threadpool, sync_disconnect)

	async def generate_mcp_resources_and_tools(self, connection_name, mcp, connection_name_counter, connection_mapping):
		"""
		Generate MCP resources and tools based on the database connection.
		"""
		try:
			# Check if the connection name already exists in the mapping
			tool_name = f"database_query_{connection_name}"
			# Increment the counter for the connection name
			connection_name_counter[tool_name] += 1
			if connection_name_counter[tool_name] > 1:
				tool_name = f"{tool_name}_{connection_name_counter[tool_name]}"
			
			connection_mapping[tool_name] = self
			tool_name = f"{tool_name}_{connection_name_counter[tool_name]}"
		
			connection_mapping[tool_name] = self

			# Define a function dynamically using a closure
			def create_dynamic_tool(fn_name):
				async def dynamic_tool(query: str) -> str:
					"""Run a database query on the connection."""
					db = connection_mapping.get(fn_name)
					if not db:
						logger.error(f"No database connection found for tool: {fn_name}")
						return None
					try:
						logger.debug(f"Executing query: {query} in dynamic tool")
						success_flag, result = await db.query(query)
						if success_flag:
							# convert the result pandas dataframe to a list of dictionaries
							result = result.to_dict('records')
							logger.debug(f"Query result: {result}")
							# we don't need to convert to JSON string here, as the mcp server will handle it for us
							return result
						else:
							logger.error(f"Query execution failed for {fn_name}")
							return 'error'
					except Exception as e:
						logger.error(f"Error executing query: {e}")
						return 'error' + str(e)
				return dynamic_tool

			# Create the dynamic tool function with the tool name
			tool_function = create_dynamic_tool(tool_name)

			# Register the function as an MCP tool
			tool_function.__name__ = tool_name
			tool_function.__doc__ = f"Run a query on the {connection_name} database."
			mcp.tool()(tool_function)
		except Exception as e:
			logger.error(f"Error generating MCP resources and tools: {e}")
			return None

@dataclass
class PostgreSQLConnection(DatabaseConnection):
	platform = 'postgresql'
	driver_type = 'async'
	driver_interface = 'sqlalchemy'

	def __post_init__(self):
		self.database_uri = f"postgresql+asyncpg://{self.settings['username']}:{self.settings['password']}@{self.settings['host']}:{self.settings['port']}/{self.settings['database_name']}"

@dataclass
class MySQLConnection(DatabaseConnection):
	platform = 'mysql'
	driver_type = 'async'
	driver_interface = 'sqlalchemy'

	def __post_init__(self):
		self.database_uri = f"mysql+aiomysql://{self.settings['username']}:{self.settings['password']}@{self.settings['host']}:{self.settings['port']}/{self.settings['database_name']}"

@dataclass
class OracleDBConnection(DatabaseConnection):
	platform = 'oracle'
	driver_type = 'async'
	driver_interface = 'sqlalchemy'

	def __post_init__(self):
		self.database_uri = f"oracle+oracledb://{self.settings['username']}:{self.settings['password']}@{self.settings['host']}:{self.settings['port']}/?service_name={self.settings['service_name']}"

@dataclass
class SQLServerConnection(DatabaseConnection):
	platform = 'sqlserver'
	driver_type = 'async'
	driver_interface = 'sqlalchemy'

	def __post_init__(self):
		self.database_uri = f"mssql+aioodbc://{self.settings['username']}:{self.settings['password']}@{self.settings['host']}:{self.settings['port']}/{self.settings['database_name']}?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"

@dataclass
class HiveConnection(DatabaseConnection):
	platform = 'hive'
	driver_type = 'sync'
	driver_interface = 'sqlalchemy'

	def __post_init__(self):
		self.database_uri = f"hive+https://{self.settings['username']}:{self.settings['password']}@{self.settings['host']}:{self.settings['port']}/"

@dataclass
class PrestoConnection(DatabaseConnection):
	"""
	PyHive via SQLAlchemy also supports Presto, but it is no longer maintained
	so we use https://github.com/prestodb/presto-python-client via DBAPI
	"""
	platform = 'presto'
	driver_type = 'sync'
	driver_interface = 'dbapi'

	async def connect(self):
		"""
		Initialize the database connection.
		we do this in a separate method so we can return a boolean value on success/failure
		"""
		try:
			def sync_connect():
				import prestodb
				credentials = {
					'host': self.settings['host'],
					'port': self.settings['port'],
					'user': self.settings['username'],
					'catalog': self.settings.get('catalog', 'hive'),
					'schema': self.settings.get('schema', 'default'),
				}
				if self.settings.get('username') and self.settings.get('password'):
					auth=prestodb.auth.BasicAuthentication(self.settings['username'], self.settings['password'])
					credentials['auth'] = auth
				self.connection = prestodb.dbapi.connect(**credentials)
			await asyncio.get_event_loop().run_in_executor(self.threadpool, sync_connect)
			return True
		except Exception as e:
			logger.error(f"Failed to create database connection: {e}")
			return False

@dataclass
class Trino(DatabaseConnection):
	"""
	
	"""
	platform = 'trino'
	driver_type = 'async'
	driver_interface = 'dbapi'

	async def connect(self):
		try:
			import aiotrino
			credentials = {
				'host': self.settings['host'],
				'port': self.settings['port'],
				'user': self.settings['username'],
				'catalog': self.settings.get('catalog', 'hive'),
				'schema': self.settings.get('schema', 'default'),
			}
			if self.settings.get('username') and self.settings.get('password'):
				auth=auth=aiotrino.auth.BasicAuthentication(self.settings['username'], self.settings['password'])
				credentials['auth'] = auth
			self.connection = aiotrino.dbapi.connect(**credentials)
			return True
		except Exception as e:
			logger.error(f"Failed to create database connection: {e}")
			return False
		
@dataclass
class Snowflake(DatabaseConnection):
	platform = 'snowflake'
	driver_type = 'sync' # https://github.com/snowflakedb/snowflake-sqlalchemy/issues/218
	driver_interface = 'sqlalchemy'

	def __post_init__(self):
		from snowflake.sqlalchemy import URL
		credentials = {key: self.settings.get(key) for key in ['account', 'user', 'password', 'database', 'schema', 'warehouse', 'role', 'timezone'] if key in self.settings}
		self.database_uri = URL(**self.credentials)

@dataclass
class BigQuery(DatabaseConnection):
	platform = 'bigquery'
	driver_type = 'sync' # https://github.com/googleapis/python-bigquery-sqlalchemy/issues/1071
	driver_interface = 'sqlalchemy'

	def __post_init__(self):
		self.database_uri = f"bigquery://{self.settings['project_name']}"
		self.create_engine_kwargs = {
			'credentials_path': self.settings.get('credentials_path', None),
		}

@dataclass
class Clickhouse(DatabaseConnection):
	platform = 'clickhouse'
	driver_type = 'sync'
	driver_interface = 'sqlalchemy'

	def __post_init__(self):
			self.database_uri = f"clickhouse+{self.settings['protocol']}://{self.settings['user']}:{self.settings['password']}@{self.settings['host']}:{self.settings['port']}/{self.settings['database']}"

@dataclass
class Databricks(DatabaseConnection):
	platform = 'databricks'
	driver_type = 'sync'
	driver_interface = 'sqlalchemy'

	def __post_init__(self):
		self.database_uri = f"databricks://token:{self.settings['access_token']}@{self.settings['host']}?http_path={self.settings['http_path']}&catalog={self.settings['catalog']}&schema={self.settings['schema']}"

@dataclass
class SAPHana(DatabaseConnection):
	platform = 'sap_hana'
	driver_type = 'sync'
	driver_interface = 'sqlalchemy'

	def __post_init__(self):
		self.database_uri = f"hana://{self.settings['username']}:{self.settings['password']}@{self.settings['host']}:{self.settings['port']}"
		if self.settings.get('database_name'):
			self.database_uri += f'/{self.settings['database_name']}'

@dataclass
class Teradata(DatabaseConnection):
	platform = 'teradata'
	driver_type = 'sync'
	driver_interface = 'sqlalchemy'

	def __post_init__(self):
		self.database_uri = f"teradatasql://{self.settings['username']}:{self.settings['password']}@{self.settings['host']}"

@dataclass
class CockroachDB(DatabaseConnection):
	platform = 'cockroachdb'
	driver_type = 'async'
	driver_interface = 'sqlalchemy'

	def __post_init__(self):
		self.database_uri = f"cockroachdb+asyncpg://{self.settings['username']}@{self.settings['host']}:{self.settings['port']}/defaultdb"

@dataclass
class AWSAthena(DatabaseConnection):
	platform = 'aws_athena'
	driver_type = 'sync'
	driver_interface = 'sqlalchemy'

	def __post_init__(self):
		self.database_uri = f"awsathena+rest://{self.settings['aws_access_key_id']}:{self.settings['aws_secret_access_key']}@athena.{self.settings['region_name']}.amazonaws.com:443/{self.settings['schema_name']}?s3_staging_dir={self.settings['s3_staging_dir']}"