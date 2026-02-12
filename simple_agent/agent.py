import re
from llm_client import LLMClient
from tools import TOOL_DEFINITIONS, TOOL_REGISTRY

# System Prompt defining the ReAct behavior
SYSTEM_PROMPT = f"""You are a smart AI assistant.
You do NOT know the current date or time. You MUST use the 'get_time' tool to find out.

You have access to the following tools:

{TOOL_DEFINITIONS}

To use a tool, please use the following format:

Thought: Do I need to use a tool? Yes
Action: the action to take, should be one of [{', '.join(TOOL_REGISTRY.keys())}]
Action Input: the input to the action
Observation: the result of the action

When you have a response for the human, or if you do not need to use a tool, you MUST use the format:

Thought: Do I need to use a tool? No
Final Answer: [your response here]
"""

class Agent:
    def __init__(self):
        self.llm = LLMClient()
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        #print("dubegged code")

    def run(self, user_input, max_turns=5):
        """
        Runs the ReAct loop for a given user input.
        """
        print(f"User: {user_input}")
        self.messages.append({"role": "user", "content": user_input})
        
        turn_count = 0
        while turn_count < max_turns:
            print(f"--- Turn {turn_count + 1} ---")
            
            # 1. Get LLM Response
            # added stop sequence to prevent hallucinating the observation
            response_text = self.llm.get_completion(self.messages, stop=["Observation:"])
            print(f"LLM Response:\n{response_text}\n")
            
            # Append LLM's thought/action to history so it knows what it did
            self.messages.append({"role": "assistant", "content": response_text})

            # 2. Check for "Final Answer"
            if "Final Answer:" in response_text:
                return response_text.split("Final Answer:")[-1].strip()

            # 3. Parse Action
            # Regex to find Action and Action Input
            action_match = re.search(r"Action: (.*?)[\n\r]", response_text)
            action_input_match = re.search(r"Action Input: (.*?)[\n\r]", response_text)

            if action_match and action_input_match:
                tool_name = action_match.group(1).strip()
                tool_input = action_input_match.group(1).strip()
                
                # 4. Execute Tool
                if tool_name in TOOL_REGISTRY:
                    print(f"-> Executing Tool: {tool_name} with input: {tool_input}")
                    try:
                        tool_func = TOOL_REGISTRY[tool_name]
                        # Clean up input (remove quotes if LLM added them)
                        if (tool_input.startswith('"') and tool_input.endswith('"')) or \
                           (tool_input.startswith("'") and tool_input.endswith("'")):
                            tool_input = tool_input[1:-1]

                        # Special handling if the tool takes no args (optional but good for robustness if we had such tools)
                        # But here, both tools CAN take a string argument (get_time takes optional timezone).
                        # We pass the input if it's not empty.
                        if tool_input:
                            result = tool_func(tool_input)
                        else:
                            result = tool_func()
                            
                    except Exception as e:
                        result = f"Error executing tool: {e}"
                    
                    print(f"<- Tool Result: {result}")
                    
                    # 5. Append Observation
                    observation = f"Observation: {result}"
                    self.messages.append({"role": "user", "content": observation})
                else:
                    self.messages.append({"role": "user", "content": f"Observation: Tool '{tool_name}' not found."})

            else:
                 # If the model didn't follow format or decided no tool but didn't say Final Answer,
                 # we nudge it or simply return what it said if it looks like an answer.
                 # Ideally, we enforce format. For now, let's assume it might have just chatted.
                 if "Thought: Do I need to use a tool? No" in response_text:
                     # It probably just forgot "Final Answer" or formatted it deeply.
                     return response_text
                 pass

            turn_count += 1
        
        return "I'm sorry, I couldn't finish the task within the turn limit."
