import os
import google.auth
from google.adk.agents import Agent
from google.adk.apps import App

from app.sub_agents.dbt_parser import dbt_parser_agent
from app.sub_agents.dataplex_sync import dataplex_sync_agent
from app.sub_agents.analytics_hub_sync import analytics_hub_agent

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

root_agent = Agent(
    name="GovernanceOrchestrator",
    model="gemini-3.1-pro-preview",
    instruction=\"\"\"You are the Data Governance Orchestrator. 
Your role is to coordinate the end-to-end onboarding of Enterprise Data Products at Sinch.
You must ensure dbt remains the single source of truth, verify physical schemas in BigQuery project 'prabha-test', and delegate metadata application to specialized sub-agents.
    
Workflow:
1. Delegate extraction of metadata to the `DbtParserAgent`.
2. Upon successful extraction, delegate the metadata binding and business glossary mapping to the `DataplexSyncAgent`.
3. Finally, delegate the publishing of the data product listing to the `AnalyticsHubAgent`.
    
Always ensure strict decoupling: logical metadata is in Dataplex, but physical security is in BigQuery. Ensure multi-region replicated metadata is handled accurately.\"\"\",
    description="Main agent managing the workflow and verifying physical schemas.",
    sub_agents=[dbt_parser_agent, dataplex_sync_agent, analytics_hub_agent],
)

app = App(
    root_agent=root_agent,
    name="app",
)
