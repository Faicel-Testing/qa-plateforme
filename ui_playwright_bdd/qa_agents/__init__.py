"""Python/LangChain runtime for the QA framework."""
import os

# No prompts or credentials are exported to a tracing SaaS.
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
