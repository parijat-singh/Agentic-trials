# Simple AI Agent

A simple implementation of a ReAct (Reasoning + Acting) agent built from scratch in Python.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Environment Variables**:
    -   Open `.env` file.
    -   Add your OpenAI API Key: `OPENAI_API_KEY=sk-...`

## Running the Agent

1.  Navigate to the `simple_agent` directory:
    ```bash
    cd simple_agent
    ```

2.  Run the main script:
    ```bash
    python main.py
    ```

## Example Usage

Once the agent is running, try asking:

-   "What is 25 * 48 + 120?"
-   "What time is it?"
-   "What is the time plus 5 hours?" (Note: The agent might struggle with complex time math without a specific tool, but it's a good test!)
