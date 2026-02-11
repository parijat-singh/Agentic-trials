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

def get_time():
    """
    Returns the current date and time.
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Tool Registry
# This dictionary maps tool names to the actual function objects.
# The agent will use this to execute the requested tool.
TOOL_REGISTRY = {
    "calculate": calculate,
    "get_time": get_time
}

# Tool Definitions for the LLM System Prompt
# This tells the LLM what tools are available and how to use them.
TOOL_DEFINITIONS = """
1. calculate(expression): A calculator. Use this for math questions. Argument 'expression' is a string like "2 + 2".
2. get_time(): Returns the current date and time. No arguments needed.
"""
