# calculator_tool.py — 数学计算工具

from smolagents import tool


@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression safely.

    Args:
        expression: A math expression string, e.g. '2 ** 10', '(3 + 5) * 12 / 4'.
    """
    # 白名单校验：只允许数字和基本运算符，防止代码注入
    # 例如 "__import__('os').system('rm -rf /')" 会被拦截
    allowed = set("0123456789+-*/(). ")
    if not all(c in allowed for c in expression):
        return "Invalid expression: only basic arithmetic is allowed."
    try:
        # 传入空的 __builtins__ 沙箱，禁止访问任何内置函数
        # 这样即使绕过了字符白名单，也无法执行危险操作
        result = eval(expression, {"__builtins__": {}})  # noqa: S307
        return f"{expression} = {result}"
    except Exception as e:
        return f"Error evaluating '{expression}': {e}"
