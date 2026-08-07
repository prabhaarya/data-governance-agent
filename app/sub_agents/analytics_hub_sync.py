from google.adk.agents import Agent
from app.app_utils.tools import publish_analytics_hub

analytics_hub_agent = Agent(
    name="AnalyticsHubAgent",
    model="gemini-3.1-pro-preview",
    instruction=\"\"\"You are the Analytics Hub Publisher Agent.
Your goal is to create or update data product listings in BigQuery Analytics Hub for business discovery.
Use the `publish_analytics_hub` tool to sync the logical data products to the business storefront.
Ensure that the published product has a business-friendly description.\"\"\",
    description="Updates the e-commerce storefront for business users in Analytics Hub.",
    tools=[publish_analytics_hub],
)
