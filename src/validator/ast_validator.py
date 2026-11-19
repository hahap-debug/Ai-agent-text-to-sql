"""
AST Validator Module for SQL Queries
Uses sqlglot to enforce read-only safety, prevent SQL injection / stacked queries,
and validate MySQL 8.x syntax before database execution.
"""

from typing import List, Set, Optional
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


def validate_ast_safety(query: str, allowed_tables: Optional[Set[str]] = None, dialect: str = "mysql") -> exp.Expression:
    """
    Parses and inspects the SQL query AST.
    
    Args:
        query: SQL string to validate.
        allowed_tables: Optional set of allowed lowercase table names.
        dialect: SQL dialect (defaults to 'mysql').
        
    Returns:
        The validated sqlglot Expression.
        
    Raises:
        SQLSyntaxError: If the SQL contains syntax errors.
        SQLSecurityError: If the query performs non-read-only operations.
    """
    cleaned_query = query.strip().rstrip(";")
    if not cleaned_query:
        raise SQLSecurityError("Empty SQL query is not allowed.")

    # 1. Check for multi-statements (stacked queries)
    try:
        statements = sqlglot.parse(cleaned_query, read=dialect)
    except errors.ParseError as e:
        raise SQLSyntaxError(f"SQL Syntax Error: {str(e)}")

    if not statements or statements[0] is None:
        raise SQLSyntaxError("No valid SQL statement found.")

    if len(statements) > 1:
        raise SQLSecurityError("Multiple SQL statements (semicolon chaining) are strictly prohibited.")

    ast = statements[0]

    # 2. Top-level statement MUST be a Select or Union expression
    if not isinstance(ast, (exp.Select, exp.Union)):
        stmt_type = type(ast).__name__
        raise SQLSecurityError(f"Statement type '{stmt_type}' is forbidden. Only SELECT queries are permitted.")

    # 3. Deep search for any forbidden/mutating statements inside CTEs or subqueries
    for forbidden in FORBIDDEN_EXPRESSIONS:
        if ast.find(forbidden):
            raise SQLSecurityError(f"Detected forbidden modifying clause ({forbidden.__name__}). Only read-only operations are allowed.")

    # 4. Check for 'INTO OUTFILE' or file manipulation
    if ast.find(exp.Into):
        raise SQLSecurityError("SELECT INTO / OUTFILE operations are forbidden.")

    # 5. Optional Catalog / Allowed Tables Guard
    if allowed_tables:
        allowed_lower = {t.lower() for t in allowed_tables}
        for table in ast.find_all(exp.Table):
            t_name = table.name.lower()
            if t_name and t_name not in allowed_lower:
                # Could be a CTE or alias, check if it is defined as CTE
                cte_names = {c.alias_or_name.lower() for c in ast.find_all(exp.CTE)}
                if t_name not in cte_names:
                    raise SQLSecurityError(f"Access to table '{table.name}' is outside the authorized catalog.")

    return ast


def extract_tables(query: str, dialect: str = "mysql") -> List[str]:
    """Helper to extract table names used in a query."""
    try:
        ast = sqlglot.parse_one(query, read=dialect)
        cte_names = {c.alias_or_name.lower() for c in ast.find_all(exp.CTE)}
        tables = []
        for table in ast.find_all(exp.Table):
            t_name = table.name.lower()
            if t_name and t_name not in cte_names and t_name not in tables:
                tables.append(t_name)
        return tables
    except Exception:
        return []
