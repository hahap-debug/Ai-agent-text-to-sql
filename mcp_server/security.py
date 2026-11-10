"""
AST Security Guardrail for MCP Server
Uses sqlglot to strictly enforce Read-Only SELECT queries and block DDL/DML.
"""

from typing import Set, Optional
import sqlglot
from sqlglot import exp, errors

FORBIDDEN_EXPRESSIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.TruncateTable if hasattr(exp, "TruncateTable") else exp.Command,
    exp.Command,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Grant,
    exp.Revoke,
    exp.Set,
)

class SQLSecurityError(Exception):
    """Raised when an SQL query violates read-only or safety constraints."""
    pass

class SQLSyntaxError(Exception):
    """Raised when an SQL query cannot be parsed."""
    pass

def validate_mcp_query(query: str, dialect: str = "mysql") -> exp.Expression:
    """
    Validates that the SQL query is strictly read-only and safe to execute.
    """
    cleaned_query = query.strip().rstrip(";")
    if not cleaned_query:
        raise SQLSecurityError("Empty SQL query is not allowed.")

    try:
        statements = sqlglot.parse(cleaned_query, read=dialect)
    except errors.ParseError as e:
        raise SQLSyntaxError(f"SQL Syntax Error: {str(e)}")

    if not statements or statements[0] is None:
        raise SQLSyntaxError("No valid SQL statement found.")

    if len(statements) > 1:
        raise SQLSecurityError("Multiple SQL statements (semicolon chaining) are strictly prohibited.")

    ast = statements[0]

    if not isinstance(ast, (exp.Select, exp.Union)):
        stmt_type = type(ast).__name__
        raise SQLSecurityError(f"Statement type '{stmt_type}' is forbidden. Only SELECT queries are permitted.")

    for forbidden in FORBIDDEN_EXPRESSIONS:
        if ast.find(forbidden):
            raise SQLSecurityError(f"Forbidden mutating clause ({forbidden.__name__}) detected. Only read-only operations are allowed.")

    if ast.find(exp.Into):
        raise SQLSecurityError("SELECT INTO / OUTFILE operations are forbidden.")

    return ast
