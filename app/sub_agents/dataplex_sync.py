from google.adk.agents import Agent
from app.app_utils.tools import apply_dataplex_aspects, map_business_glossary

dataplex_sync_agent = Agent(
    name="DataplexSyncAgent",
    model="gemini-3.1-pro-preview",
    instruction=\"\"\"You are the Dataplex Sync Agent.
Your goal is to programmatically apply global Aspect Types and map technical fields to Business Glossary terms in Dataplex.
Use `apply_dataplex_aspects` to bind aspects (e.g., DataProductStatus, ColumnMetadata) using the metadata provided.
Use `map_business_glossary` to link technical column names to business terms.
Coordinate these bindings without modifying physical RLS/CLS, which is strictly managed in BigQuery.\"\"\",
    description="Binds Aspect Types and maps Business Glossary terms in Dataplex.",
    tools=[apply_dataplex_aspects, map_business_glossary],
)
