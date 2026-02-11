from agent import Agent
import os

def main():
    print("Welcome to the Simple AI Agent CLI!")
    print("Type 'exit' or 'quit' to stop.")
    
    # Check for API Key
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY not found. Please set it in .env file.")

    agent = Agent()
    
    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.lower() in ['exit', 'quit']:
                print("Goodbye!")
                break
            
            if not user_input.strip():
                continue

            response = agent.run(user_input)
            print(f"\nAgent: {response}")

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
