from dataclasses import dataclass

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import pandas as pd

from logs import logger

subclasses = {}

@dataclass
class DatabaseConnection:
	credentials: dict

	def __init_subclass__(cls, **kwargs):
		super().__init_subclass__(**kwargs)
		subclasses[cls.platform] = cls

	@classmethod
	def create(cls, platform, credentials, **kwargs):
		if platform not in ['MySQL', 'PostgreSQL', 'SQLite']:
			raise ValueError('Bad DatabaseConnection platform {}'.format(platform))
		return subclasses[platform](credentials=credentials, **kwargs)
	
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
	
@dataclass
class PostgreSQLConnection(DatabaseConnection):
	platform = 'PostgreSQL'

	async def connect(self):
		"""
		Initialize the PostgreSQL connection.
		we do this in a separate method so we can return a boolean value on success/failure
		"""
		try:
			database_uri = f"postgresql+asyncpg://{self.credentials['username']}:{self.credentials['password']}@{self.credentials['host']}:{self.credentials['port']}/{self.credentials['database_name']}"
			self.engine = create_async_engine(database_uri, echo=False, future=True) # echo is False, as we don't want to log to stdout (it interferes with MCP on stdio)
			self.session_factory = sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)
			return True
		except Exception as e:
			logger.error(f"Failed to create PostgreSQL connection: {e}")
			return False

	async def query(self, query_string: str) -> pd.DataFrame:
		try:
			logger.debug(f"Executing query: {query_string}")
			async with self.session_factory() as session:
				result = await session.execute(text(query_string))
				# Convert result to pandas DataFrame
				df = pd.DataFrame(result.fetchall(), columns=result.keys())
				return True, df
		except Exception as e:
			# Log the error and re-raise it
			logger.error(f"Query failed: {e}")
			return False, None

	async def disconnect(self):
		await self.engine.dispose()
