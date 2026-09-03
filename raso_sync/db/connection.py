import logging
from contextlib import contextmanager

# TODO: import threading
from typing import Any, ClassVar

import frappe
import pymssql

from ..utils.system_notifications import clear_server_unavailable_notification_mark
from .exceptions import RASOServerUnavailableError

logger = frappe.logger("raso_sync.db")
logger.setLevel(logging.INFO)


class MSSQLConnection:
	"""
	Manages a single MSSQL connection.
	Uses context managers for safe cursor operations.
	"""

	def __init__(
		self,
		host: str,
		user: str,
		password: str,
		database: str,
		port: int = 1433,
		encryption: str = "request",
		login_timeout: int = 60,
	):
		"""
		Initialize connection configuration.
		"""
		self.host = host
		self.user = user
		self.password = password
		self.database = database
		self.port = port
		self.encryption = encryption
		self.login_timeout = login_timeout
		self._connection: pymssql.Connection | None = None
		self._is_connected = False

	def _connect(self) -> pymssql.Connection:
		"""
		Create a new MSSQL connection.

		Returns:
		    pymssql.Connection: Active database connection

		Raises:
		    frappe.ValidationError: If connection fails
		"""
		try:
			logger.info(
				f"Opening MSSQL connection to host={self.host}, port={self.port}, "
				f"database={self.database}, user={self.user}, encryption={self.encryption}"
			)
			conn = pymssql.connect(
				server=self.host,
				user=self.user,
				password=self.password,
				database=self.database,
				port=self.port,
				encryption=self.encryption,
				as_dict=True,  # Return results as dictionaries
				autocommit=True,
				login_timeout=self.login_timeout,
			)
			self._is_connected = True

			self._update_sync_status(is_running=True)

			logger.info(f"Connected to MSSQL database at {self.host}:{self.port}/{self.database}")
			return conn
		except pymssql.OperationalError as e:
			# Server unreachable or connection timed out
			self._is_connected = False
			self._update_sync_status(is_running=False)
			frappe.log_error("RASO DB Connection", f"MSSQL Server Unavailable/Timeout: {e!s}")
			raise RASOServerUnavailableError(
				f"Database connection failed (server unavailable or timed out): {e!s}"
			) from e
		except pymssql.Error as e:
			self._is_connected = False
			self._update_sync_status(is_running=False)
			frappe.log_error("RASO DB Connection", f"MSSQL Connection Error: {e!s}")
			raise frappe.ValidationError(f"Database connection failed: {e!s}") from e

	def connect(self) -> pymssql.Connection:
		"""
		Get or create an active connection.

		Returns:
		    pymssql.Connection: Active database connection
		"""
		if self._connection is None or not self._is_connected:
			self._connection = self._connect()
		return self._connection

	def close(self):
		"""Close the active connection if it exists."""
		if self._connection is not None and self._is_connected:
			try:
				self._connection.close()
				logger.info("Database connection closed")
			except pymssql.Error as e:
				logger.warning(f"Error closing connection: {e!s}")
			finally:
				self._connection = None
				self._is_connected = False

				clear_server_unavailable_notification_mark()
				self._update_sync_status(is_running=False)

	def is_connected(self) -> bool:
		"""Check if connection is active."""
		return self._is_connected and self._connection is not None

	@staticmethod
	def _update_sync_status(is_running: bool):
		"""
		Send a real-time notification to the front-end about the synchronisation status.
		"""
		frappe.publish_realtime("raso_sync_status_update", {"is_running": is_running})

	@contextmanager
	def cursor(self):
		"""
		Context manager for database cursor operations.
		Automatically handles commit/rollback and cursor cleanup.

		Yields:
		    pymssql.Cursor: Database cursor

		Example:
		    with connection.cursor() as cursor:
		        cursor.execute("SELECT * FROM table")
		        results = cursor.fetchall()
		"""
		conn = self.connect()
		cursor = conn.cursor()
		try:
			yield cursor
			conn.commit()
		except Exception as e:
			conn.rollback()
			logger.error(f"Cursor operation error: {e!s}")
			raise
		finally:
			cursor.close()
			# Ensure running flag is reset when cursor usage is finished
			try:
				self.close()
			except Exception:
				# close() already logs/handles its own errors
				pass

	def __del__(self):
		"""Cleanup connection on garbage collection."""
		self.close()


class MSSQLConnectionManager:
	"""
	Per-site connection manager for MSSQL.
	Ensures only one connection per Frappe site to prevent connection conflicts.
	"""

	_connections: ClassVar[dict[str, MSSQLConnection]] = {}

	@staticmethod
	def _get_site_key() -> str:
		"""
		Get unique key for current Frappe site.

		Returns:
		    str: Site identifier
		"""
		return frappe.local.site if hasattr(frappe.local, "site") else "default"

	@staticmethod
	def get_connection() -> MSSQLConnection:
		"""
		Get connection for current site, creating if necessary.
		Ensures only one connection per site.

		Returns:
		    MSSQLConnection: Connection instance for current site

		Raises:
		    frappe.ValidationError: If configuration is invalid
		"""
		site_key = MSSQLConnectionManager._get_site_key()

		# Return existing connection if available
		if site_key in MSSQLConnectionManager._connections:
			conn = MSSQLConnectionManager._connections[site_key]
			if conn.is_connected():
				return conn
			else:
				# Connection was closed, remove it
				del MSSQLConnectionManager._connections[site_key]

		# Create new connection from settings
		config = MSSQLConnectionManager._get_config_from_settings()
		connection = MSSQLConnection(
			host=config["host"],
			user=config["user"],
			password=config["password"],
			database=config["database"],
			port=config.get("port", 1433),
			encryption=config.get("encryption", "request"),
			login_timeout=config.get("login_timeout", 60),
		)

		MSSQLConnectionManager._connections[site_key] = connection
		logger.info(f"Created new MSSQL connection for site: {site_key}")

		return connection

	@staticmethod
	def _get_config_from_settings() -> dict[str, Any]:
		"""
		Retrieve MSSQL configuration from Frappe settings.

		Returns:
		    dict: Configuration dictionary

		Raises:
		    frappe.ValidationError: If settings are not properly configured
		"""
		try:
			settings_doc = frappe.get_doc("RASO Sync Settings")
		except frappe.DoesNotExistError:
			raise frappe.ValidationError(
				"RASO Sync Settings document not found. Please create and configure it."
			)

		# Validate required fields
		required_fields = {
			"ip": "Server IP Address",
			"database_username": "Database Username",
			"database_password": "Database Password",
			"database_name": "Database Name",
		}

		missing_fields = []
		for field, label in required_fields.items():
			if not getattr(settings_doc, field, None):
				missing_fields.append(label)

		if missing_fields:
			raise frappe.ValidationError(
				f"Missing required MSSQL configuration fields: {', '.join(missing_fields)}"
			)

		# Optional login timeout (in seconds) for slow SQL servers
		try:
			login_timeout = int(getattr(settings_doc, "login_timeout", 60) or 60)
		except Exception:
			login_timeout = 60

		config = {
			"host": settings_doc.ip,
			"user": settings_doc.database_username,
			"password": settings_doc.get_password("database_password"),
			"database": settings_doc.database_name,
			"port": settings_doc.port or 1433,
			"encryption": settings_doc.encryption or "request",
			"login_timeout": login_timeout,
		}

		return config

	@staticmethod
	def close_connection(site_key: str | None):
		"""
		Close connection for specific site or current site.

		Args:
		    site_key: Site identifier (uses current site if None)
		"""
		if site_key is None:
			site_key = MSSQLConnectionManager._get_site_key()

		if site_key in MSSQLConnectionManager._connections:
			MSSQLConnectionManager._connections[site_key].close()
			del MSSQLConnectionManager._connections[site_key]
			logger.info(f"Closed MSSQL connection for site: {site_key}")

	@staticmethod
	def close_all():
		"""Close all active connections across all sites."""
		for site_key in list(MSSQLConnectionManager._connections.keys()):
			MSSQLConnectionManager.close_connection(site_key)
		logger.info("All MSSQL connections closed")

	@staticmethod
	def reset():
		"""Reset all connections (close and clear)."""
		MSSQLConnectionManager.close_all()
		MSSQLConnectionManager._connections.clear()


def cleanup_connections():
	"""
	Close all MSSQL connections after request/job completes.
	Called by Frappe's lifecycle hooks.
	"""
	try:
		MSSQLConnectionManager.close_all()
		logger.info("MSSQL connections closed up after request/job")
	except Exception as e:
		logger.error(f"Error closing connections in cleanup: {e!s}")


# Register cleanup hooks for both web requests and background jobs
def register_cleanup_hooks():
	"""Register connection cleanup for various Frappe lifecycle events."""
	# Web requests
	if hasattr(frappe, "after_request") and cleanup_connections not in frappe.after_request:
		frappe.after_request.append(cleanup_connections)

	# Background jobs - cleanup after job completes
	if hasattr(frappe, "after_job") and cleanup_connections not in frappe.after_job:
		frappe.after_job.append(cleanup_connections)


# Auto-register on module import
try:
	register_cleanup_hooks()
except Exception as e:
	logger.warning(f"Could not register cleanup hooks: {e!s}")
