from google.adk.agents import Agent
from app.app_utils.tools import parse_dbt_artifacts

dbt_parser_agent = Agent(
    name="DbtParserAgent",
    model="gemini-3.1-pro-preview",
    instruction=\"\"\"You are the dbt Artifact Parser Agent. 
Your goal is to extract table descriptions, column metadata, and bookkeeping hashes from dbt manifest and catalog files.
Use the `parse_dbt_artifacts` tool to read the files and extract the single source of truth metadata.
Return the extracted metadata to be used by other agents.\"\"\",
    description="Extracts metadata hashes and descriptions from dbt artifacts.",
    tools=[parse_dbt_artifacts],
)
