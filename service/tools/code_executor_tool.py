# code_executor_tool.py — 通用 Python 代码执行工具

import ast
import contextlib
import io
import traceback

from smolagents import tool


def execute_python_code(code: str, extra_globals: dict | None = None) -> dict:
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    globals_dict = {"__builtins__": __builtins__}
    if extra_globals:
        globals_dict.update(extra_globals)

    result = None
    success = True

    try:
        tree = ast.parse(code, mode="exec")
        expression = None
        body = tree.body
        if body and isinstance(body[-1], ast.Expr):
            expression = ast.Expression(body.pop().value)
            ast.fix_missing_locations(expression)
        module = ast.Module(body=body, type_ignores=[])
        ast.fix_missing_locations(module)

        with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
            if body:
                exec(compile(module, "<lobster-exec>", "exec"), globals_dict, globals_dict)
            if expression is not None:
                result = eval(compile(expression, "<lobster-exec>", "eval"), globals_dict, globals_dict)
            elif "_result" in globals_dict:
                result = globals_dict["_result"]
    except Exception:
        success = False
        traceback.print_exc(file=stderr_buffer)

    stdout = stdout_buffer.getvalue().strip()
    stderr = stderr_buffer.getvalue().strip()
    parts = []
    if stdout:
        parts.append(f"Stdout:\n{stdout}")
    if stderr:
        parts.append(f"Stderr:\n{stderr}")
    if result is not None:
        parts.append(f"Result:\n{result}")

    rendered = "\n\n".join(parts).strip()
    if success and not rendered:
        rendered = "Code executed successfully with no output."

    return {
        "success": success,
        "stdout": stdout,
        "stderr": stderr,
        "result": result,
        "rendered": rendered,
    }


@tool
def execute_python(code: str) -> str:
    """Execute arbitrary Python code and return stdout, stderr, and the final value.

    Args:
        code: Python code to execute. The last expression or a `_result` variable will be returned when present.
    """
    return execute_python_code(code)["rendered"]
