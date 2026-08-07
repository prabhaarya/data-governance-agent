#!/usr/bin/env python3
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utility to register a deployed A2A Agent to Gemini Enterprise."""

import json
import logging
from typing import Any

import click
import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest
import requests


def parse_ge_app_id(app_id: str) -> dict[str, str]:
    """Parse Gemini Enterprise app resource name to extract components."""
    parts = app_id.split("/")
    if len(parts) == 8 and parts[0] == "projects" and parts[6] == "engines":
        return {
            "project_number": parts[1],
            "location": parts[3],
            "collection": parts[5],
            "engine_id": parts[7],
        }
    raise ValueError(
        f"Invalid Gemini Enterprise App ID format: {app_id}\n"
        "Expected: projects/{project_number}/locations/{location}/collections/{collection}/engines/{engine_id}"
    )


def get_discovery_engine_endpoint(location: str) -> str:
    """Get the Discovery Engine API endpoint for the given location."""
    if location == "global":
        return "https://discoveryengine.googleapis.com"
    return f"https://{location}-discoveryengine.googleapis.com"


def get_access_token() -> str:
    """Get Google Cloud access token."""
    credentials, _ = google.auth.default()
    auth_req = GoogleAuthRequest()
    credentials.refresh(auth_req)
    return credentials.token


def get_secret_from_secret_manager(project_number: str, secret_id: str, access_token: str) -> str:
    """Fetch a secret value from Google Cloud Secret Manager."""
    import base64
    import requests

    url = f"https://secretmanager.googleapis.com/v1/projects/{project_number}/secrets/{secret_id}/versions/latest:access"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-goog-user-project": project_number,
    }
    logging.info(f"🔒 Fetching secret '{secret_id}' from Secret Manager...")
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data_b64 = resp.json().get("payload", {}).get("data", "")
            return base64.b64decode(data_b64).decode("utf-8").strip()
        err_detail = resp.text
    except Exception as e:
        err_detail = str(e)
    raise RuntimeError(f"Failed to retrieve secret '{secret_id}' from Secret Manager: {err_detail}")


def get_client_secret_from_secret_manager(project_number: str, access_token: str) -> str:
    """Fetch client secret from Google Cloud Secret Manager."""
    import os
    secret_id = os.environ.get("CLIENT_SECRET_ID", "gemini_enterprise_client_secret")
    return get_secret_from_secret_manager(project_number, secret_id, access_token)


def get_client_id_from_secret_manager(project_number: str, access_token: str) -> str:
    """Fetch client ID from Google Cloud Secret Manager."""
    import os
    secret_id = os.environ.get("CLIENT_ID_SECRET_ID", "gemini_enterprise_client_id")
    return get_secret_from_secret_manager(project_number, secret_id, access_token)


def create_agent_authorization(
    base_endpoint: str,
    project_number: str,
    location: str,
    access_token: str,
    display_name: str,
    agent_engine_id: str = "",
) -> str:
    """Create a new agent authorization resource."""
    import re

    if agent_engine_id:
        auth_id = f"{agent_engine_id}_auth"[:60]
    else:
        # Generate a safe authorization ID
        safe_name = re.sub(r"[^a-z0-9]", "_", display_name.lower()).strip("_")
        auth_id = f"{safe_name}_auth"[:60]

    auth_url = f"{base_endpoint}/v1alpha/projects/{project_number}/locations/{location}/authorizations?authorizationId={auth_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-goog-user-project": project_number,
        "Content-Type": "application/json",
    }

    client_id = get_client_id_from_secret_manager(project_number, access_token)
    client_secret = get_client_secret_from_secret_manager(project_number, access_token)
    auth_uri = (
        f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}"
        "&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Fstatic%2Foauth%2Foauth.html"
        "&scope=https://www.googleapis.com/auth/cloud-platform&include_granted_scopes=true"
        "&response_type=code&access_type=offline&prompt=consent"
    )

    resource_name = f"projects/{project_number}/locations/{location}/authorizations/{auth_id}"
    payload = {
        "name": resource_name,
        "serverSideOauth2": {
            "clientId": client_id,
            "clientSecret": client_secret,
            "authorizationUri": auth_uri,
            "tokenUri": "https://oauth2.googleapis.com/token",
        },
    }

    logging.info(f"🔐 Creating new agent authorization '{auth_id}' for '{display_name}'...")
    resp = requests.post(auth_url, headers=headers, json=payload, timeout=30)
    
    if resp.status_code in (400, 409):
        err_msg = resp.json().get("error", {}).get("message", "").lower()
        if "already exists" in err_msg or "duplicate" in err_msg:
            logging.info(f"  ⚠️ Authorization '{auth_id}' already exists. Reusing it.")
            return resource_name

    resp.raise_for_status()
    auth_name = resp.json().get("name", resource_name)
    logging.info(f"  ✅ Created authorization: {auth_name}")
    return auth_name


def write_deployment_metadata(
    agent_name: str,
    metadata_file: str = "deployment_metadata.json",
) -> None:
    """Write Gemini Enterprise agent name to deployment metadata file."""
    import os
    if not agent_name:
        return

    metadata = {}
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception as e:
            logging.warning(f"Failed to read existing metadata file: {e}")

    metadata["gemini_enterprise_agent_name"] = agent_name

    try:
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        logging.info(f"Gemini Enterprise agent name written to {metadata_file}")
    except Exception as e:
        logging.error(f"Failed to write metadata file: {e}")


def execute_registration(
    gemini_enterprise_app_id: str,
    agent_card_url: str,
    display_name: str,
    description: str,
    agent_engine_id: str = "",
) -> dict[str, Any]:
    """Execute registration of an A2A agent to Gemini Enterprise."""
    logging.info(f"🪪 Using Agent Card URL: {agent_card_url}")
    logging.info("🔑 Fetching access token and agent card...")
    access_token = get_access_token()

    try:
        card_resp = requests.get(
            agent_card_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        card_resp.raise_for_status()
        agent_card = card_resp.json()
    except Exception as e:
        raise RuntimeError(f"Failed to fetch agent card from {agent_card_url}: {e}")

    ge_parts = parse_ge_app_id(gemini_enterprise_app_id)
    final_display_name = display_name or agent_card.get("name", "My A2A Agent")
    final_description = description or agent_card.get("description", "A2A Agent")

    base_endpoint = get_discovery_engine_endpoint(ge_parts["location"])
    reg_url = (
        f"{base_endpoint}/v1alpha/projects/{ge_parts['project_number']}/"
        f"locations/{ge_parts['location']}/collections/{ge_parts['collection']}/engines/{ge_parts['engine_id']}/"
        "assistants/default_assistant/agents"
    )
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-goog-user-project": ge_parts["project_number"],
        "Content-Type": "application/json",
    }

    # 1. Check if an agent exists with the same description
    logging.info("🔍 Checking if agent already exists...")
    try:
        list_resp = requests.get(reg_url, headers=headers, timeout=30)
        if list_resp.status_code == 200:
            for agent in list_resp.json().get("agents", []):
                if agent.get("description") == final_description:
                    logging.info(f"⚠️ Agent with description '{final_description}' already exists. Skipping registration.")
                    _print_console_url(ge_parts)
                    write_deployment_metadata(agent.get("name"))
                    return agent
    except Exception as e:
        logging.warning(f"Failed to list existing agents: {e}")

    # 2. Create new authorization automatically
    auth_name = ""
    try:
        auth_name = create_agent_authorization(
            base_endpoint,
            ge_parts["project_number"],
            ge_parts["location"],
            access_token,
            final_display_name,
            agent_engine_id,
        )
    except Exception as e:
        logging.warning(f"Failed to create agent authorization: {e}")

    payload: dict[str, Any] = {
        "displayName": final_display_name,
        "description": final_description,
        "icon": {
            "uri": "https://fonts.gstatic.com/s/i/short-term/release/googlesymbols/smart_toy/default/24px.svg"
        },
        "a2aAgentDefinition": {"jsonAgentCard": json.dumps(agent_card)},
        "sharingConfig": {"scope": "ALL_USERS"},
    }
    if auth_name:
        payload["authorizationConfig"] = {
            "agentAuthorization": auth_name
        }

    logging.info(f"🚀 Registering A2A agent '{final_display_name}' to Gemini Enterprise...")

    try:
        resp = requests.post(reg_url, headers=headers, json=payload, timeout=30)
        if resp.status_code in (400, 409):
            err_msg = resp.json().get("error", {}).get("message", "").lower()
            logging.info(f"Gemini Enterprise Registration error message: {err_msg}")
            if "already exists" in err_msg or "duplicate" in err_msg:
                logging.info("⚠️ Agent already registered. Updating existing registration...")

                list_resp = requests.get(reg_url, headers=headers, timeout=30)
                list_resp.raise_for_status()
                for agent in list_resp.json().get("agents", []):
                    a2a_def = agent.get("a2aAgentDefinition", {})
                    if a2a_def:
                        try:
                            card = json.loads(a2a_def.get("jsonAgentCard", "{}"))
                            if card.get("url") == agent_card_url:
                                patch_url = f"{base_endpoint}/v1alpha/{agent['name']}"
                                patch_resp = requests.patch(
                                    patch_url, headers=headers, json=payload, timeout=30
                                )
                                patch_resp.raise_for_status()
                                logging.info(
                                    f"✅ Successfully updated A2A agent registration:\n   {agent['name']}"
                                )
                                _print_console_url(ge_parts)
                                write_deployment_metadata(agent.get("name"))
                                return patch_resp.json()
                        except Exception:
                            continue
        resp.raise_for_status()
        result = resp.json()
        logging.info(
            f"✅ Successfully registered A2A agent to Gemini Enterprise:\n   {result.get('name')}"
        )
        _print_console_url(ge_parts)
        write_deployment_metadata(result.get("name"))
        return result

    except Exception as e:
        raise RuntimeError(f"Registration failed: {e}")


def _print_console_url(ge_parts: dict[str, str]) -> None:
    console_url = (
        f"https://console.cloud.google.com/gemini-enterprise/locations/{ge_parts['location']}/"
        f"engines/{ge_parts['engine_id']}/overview/dashboard?project={ge_parts['project_number']}"
    )
    logging.info(f"\n🔗 View in Console:\n   {console_url}\n")


@click.command()
@click.option(
    "--gemini-enterprise-app-id",
    envvar="GEMINI_ENTERPRISE_APP_ID",
    required=True,
    help="Full resource name of the Gemini Enterprise App.",
)
@click.option(
    "--agent-card-url",
    required=True,
    help="URL of the A2A agent card.",
)
@click.option(
    "--display-name",
    default="",
    help="Display name for the agent.",
)
@click.option(
    "--description",
    default="",
    help="Description for the agent.",
)
@click.option(
    "--agent-engine-id",
    default="",
    help="Optional Agent Engine ID to make authorization ID unique.",
)
def main(
    gemini_enterprise_app_id: str,
    agent_card_url: str,
    display_name: str,
    description: str,
    agent_engine_id: str,
) -> None:
    """Register a deployed A2A Agent to Gemini Enterprise."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    execute_registration(
        gemini_enterprise_app_id,
        agent_card_url,
        display_name,
        description,
        agent_engine_id,
    )


if __name__ == "__main__":
    main()
