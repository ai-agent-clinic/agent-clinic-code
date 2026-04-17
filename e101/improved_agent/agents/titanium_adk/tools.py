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

import datetime
from pydantic import BaseModel, Field

class SolutionRecommendation(BaseModel):
    name: str = Field(description="Executive to pitch to.")
    persona: str = Field(description="Role of the executive.")
    solution: str = Field(description="Specific technical solution recommended.", validate_default=True)
    hook: str = Field(description="The angle or pitch opening.")

class CrossSellMatrix(BaseModel):
    gemini_enterprise: SolutionRecommendation = Field(description="Gemini pitch focused on VP of Cust Success/Product.")
    security: SolutionRecommendation = Field(description="Security pitch (Mandiant or BeyondCorp) focused on CISO.")
    data_ai: SolutionRecommendation = Field(description="Data pitch (BigQuery, Vertex AI, or Looker) focused on Head of Data/AI.")

class SourceLink(BaseModel):
    title: str = Field(description="Name/title of the source link.")
    url: str = Field(description="Valid URL of the source link.")

class OutreachEmail(BaseModel):
    target_name: str = Field(description="Full name of the target executive.")
    bio: str = Field(description="Strategic snapshot including the specific quote, tech stack, or roadmap finding.")
    subject: str = Field(description="Professional subject line.")
    outreach_body: str = Field(description="3-sentence punchy email body focused on high-cognition thought leadership.")
    hack: CrossSellMatrix = Field(description="The multi-thread cross sell matrix targeted at peer executives.")
    sources: list[SourceLink] = Field(description="List of verified source URLs supporting the email context.")

class TargetAccountOutput(BaseModel):
    account_name: str = Field(description="The name of the target company.")
    outreach: OutreachEmail = Field(description="The drafted outreach and intelligence for this account.")

class OutreachEmailList(BaseModel):
    accounts: list[TargetAccountOutput] = Field(description="A list of target accounts and their corresponding outreach intelligence.")

def google_search(query: str) -> str:
    """Searches the web for the given query using Google Search.

    Args:
        query: The search term or question to execute.

    Returns:
        The search results as a string.
    """
    return f"Execute search for: {query}"
