import datetime

def calculate(expression):
    """
    Evaluates a mathematical expression.
    Example: calculate("2 + 2 * 5")
    """
    try:
        # Note: eval is dangerous in production, but defined here for simplicity in learning.
        # In a real app, use a safer math parser.
        return str(eval(expression))
    except Exception as e:
        return f"Error: {str(e)}"

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo # For older python versions if needed

def get_time(timezone="America/Los_Angeles"):
    """
    Returns the current date and time in the specified timezone.
    Default is America/Los_Angeles (PST/PDT).
    """
    try:
        now = datetime.datetime.now(ZoneInfo(timezone))
        return now.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception as e:
        return f"Error: {str(e)}. Please use a valid IANA timezone (e.g., 'America/New_York', 'UTC', 'Europe/London')."

# Tool Registry
TOOL_REGISTRY = {
    "calculate": calculate,
    "get_time": get_time
}

# Tool Definitions for the LLM System Prompt
TOOL_DEFINITIONS = """
1. calculate(expression): A calculator. Use this for math questions. Argument 'expression' is a string like "2 + 2".
2. get_time(timezone): Returns the current date and time. Argument 'timezone' is optional (default 'America/Los_Angeles'). Use IANA format like 'America/New_York'.
"""
