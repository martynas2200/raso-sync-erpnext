"""
Database procedure executor for running stored procedures with arguments.
Provides type-safe execution and result mapping.
"""

from typing import Any

import frappe
import pymssql

from .connection import MSSQLConnectionManager

logger = frappe.logger("raso_sync.db")


class ProcedureParameter:
	"""
	Represents a parameter for a stored procedure.
	Handles type conversion and validation.
	"""

	def __init__(self, name: str, value: Any, param_type: str = "VARCHAR", direction: str = "INPUT"):
		"""
		Initialize procedure parameter.

		Args:
		    name: Parameter name (without @ prefix)
		    value: Parameter value
		    param_type: SQL data type (VARCHAR, INT, FLOAT, DATETIME, etc.)
		    direction: INPUT, OUTPUT, or INOUT
		"""
		self.name = name if name.startswith("@") else f"@{name}"
		self.value = value
		self.param_type = param_type
		self.direction = direction

	def get_declaration(self) -> str:
		"""Get the SQL parameter declaration."""
		return f"{self.name} {self.param_type}"

	def __repr__(self) -> str:
		return f"<Parameter {self.name}={self.value}>"


class ProcedureExecutor:
	"""
	Executes MSSQL stored procedures with proper parameter handling and error management.
	Uses a single connection per site from the connection manager.
	"""

	def __init__(self, procedure_name: str):
		"""
		Initialize executor for a specific procedure.

		Args:
		    procedure_name: Name of the stored procedure (with or without schema)
		"""
		self.procedure_name = procedure_name
		self.parameters: list[ProcedureParameter] = []
		self.connection = MSSQLConnectionManager.get_connection()

	def add_parameter(
		self, name: str, value: Any, param_type: str = "VARCHAR", direction: str = "INPUT"
	) -> "ProcedureExecutor":
		"""
		Add a parameter to the procedure.

		Args:
		    name: Parameter name
		    value: Parameter value
		    param_type: SQL data type
		    direction: INPUT, OUTPUT, or INOUT

		Returns:
		    ProcedureExecutor: Self for method chaining
		"""
		param = ProcedureParameter(name, value, param_type, direction)
		self.parameters.append(param)
		return self

	def add_parameters(self, params: list[dict[str, Any]]) -> "ProcedureExecutor":
		"""
		Add multiple parameters at once.

		Args:
		    params: List of parameter dictionaries with keys: name, value, param_type (optional), direction (optional)

		Returns:
		    ProcedureExecutor: Self for method chaining
		"""
		for param in params:
			self.add_parameter(
				name=param["name"],
				value=param["value"],
				param_type=param.get("param_type", "VARCHAR"),
				direction=param.get("direction", "INPUT"),
			)
		return self

	def _build_command(self) -> str:
		"""
		Build the EXEC command string.

		Returns:
		    str: T-SQL EXEC command
		"""
		param_strings = []
		for param in self.parameters:
			if param.direction == "INPUT":
				param_strings.append(f"{param.name} = %s")
			elif param.direction == "OUTPUT":
				param_strings.append(f"{param.name} {param.param_type} OUTPUT")
			elif param.direction == "INOUT":
				param_strings.append(f"{param.name} {param.param_type} OUTPUT")

		params_str = ", ".join(param_strings) if param_strings else ""

		if params_str:
			return f"EXEC {self.procedure_name} {params_str}"
		else:
			return f"EXEC {self.procedure_name}"

	def _get_input_values(self) -> list[Any]:
		"""Get list of input parameter values."""
		return [param.value for param in self.parameters if param.direction in ["INPUT", "INOUT"]]

	def execute(self) -> dict[str, Any]:
		"""
		Execute the stored procedure.

		Returns:
		    dict: Execution result with keys: success, rows_affected, result_set, message

		Raises:
		    frappe.ValidationError: If execution fails
		"""
		try:
			with self.connection.cursor() as cursor:
				command = self._build_command()
				values = self._get_input_values()

				logger.info(
					f"Executing procedure: {self.procedure_name} with {len(self.parameters)} parameters"
				)

				if values:
					cursor.execute(command, values)
				else:
					cursor.execute(command)

				# Fetch results if any
				result_set = []
				try:
					result_set = cursor.fetchall()
				except (pymssql.Error, AttributeError):
					# Procedure might not return results
					pass

				rows_affected = cursor.rowcount

				result = {
					"success": True,
					"rows_affected": rows_affected,
					"result_set": result_set,
					"message": f"Procedure executed successfully. Rows affected: {rows_affected}",
				}

				logger.info(f"Procedure {self.procedure_name} executed. Rows affected: {rows_affected}")
				return result

		except pymssql.Error as e:
			error_msg = f"Procedure execution error in {self.procedure_name}: {e!s}"
			logger.error(error_msg)
			frappe.log_error(error_msg, "Procedure Execution")
			raise frappe.ValidationError(error_msg)

	def execute_scalar(self) -> Any | None:
		"""
		Execute procedure and return first column of first row.

		Returns:
		    Any: Scalar value or None

		Raises:
		    frappe.ValidationError: If execution fails
		"""
		result = self.execute()
		if result["result_set"] and len(result["result_set"]) > 0:
			row = result["result_set"][0]
			if isinstance(row, dict):
				return next(iter(row.values()))
			return row[0]
		return None

	def execute_single_row(self) -> dict[str, Any] | None:
		"""
		Execute procedure and return first row as dictionary.

		Returns:
		    dict: First row or None

		Raises:
		    frappe.ValidationError: If execution fails
		"""
		result = self.execute()
		if result["result_set"] and len(result["result_set"]) > 0:
			return result["result_set"][0]
		return None

	def execute_row_list(self) -> list[dict[str, Any]]:
		"""
		Execute procedure and return all rows as list of dictionaries.

		Returns:
		    list: Result rows

		Raises:
		    frappe.ValidationError: If execution fails
		"""
		result = self.execute()
		return result["result_set"]


class ProcedureBuilder:
	"""
	Fluent builder for constructing and executing procedures.
	"""

	@staticmethod
	def create(procedure_name: str) -> ProcedureExecutor:
		"""
		Create a new procedure executor.

		Args:
		    procedure_name: Name of the stored procedure

		Returns:
		    ProcedureExecutor: Executor instance
		"""
		return ProcedureExecutor(procedure_name)

	@staticmethod
	def execute_procedure(procedure_name: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
		"""
		Execute a procedure with given parameters in one call.

		Args:
		    procedure_name: Name of the stored procedure
		    parameters: dictionary mapping parameter names to values

		Returns:
		    dict: Execution result

		Example:
		    result = ProcedureBuilder.execute_procedure(
		        "usp_GetItemsByGroup",
		        {"group_id": 123, "status": "active"}
		    )
		"""
		executor = ProcedureBuilder.create(procedure_name)

		if parameters:
			for name, value in parameters.items():
				executor.add_parameter(name, value)

		return executor.execute()
