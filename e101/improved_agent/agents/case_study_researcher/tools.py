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

import os
import subprocess
from string import punctuation
from pydantic import BaseModel, Field

class CaseStudy(BaseModel):
    source_url: str = Field(description="The URL where the case study was found.")
    customer_name: str = Field(description="The name of the customer.")
    extracted_contents: str = Field(description="The full text content extracted from the page.")
    summary: str = Field(description="A brief summary of the case study.")
    industry: str = Field(description="The industry of the customer.")
    location: str = Field(description="The geographic location of the customer.")
    products: list[str] = Field(description="A list of Google Cloud products used.")

class CaseStudyList(BaseModel):
    case_studies: list[CaseStudy] = Field(description="A list of case studies.")

class SearchPlan(BaseModel):
    queries: list[str] = Field(description="A list of 3-5 specific search queries to use for finding case studies.")

def run_browser_command(command: str) -> dict:
    """Executes a playwright-cli command safely.

    Args:
        command: The playwright-cli command to execute (must start with 'playwright-cli').

    Returns:
        dict with status and output.
    """
    if not command.strip().startswith("playwright-cli"):
        return {"status": "error", "message": "Only 'playwright-cli' commands are permitted."}

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
             return {"status": "error", "message": f"Command Failed: {result.stderr or result.stdout}"}
             
        output = result.stdout
        
        # Check if a snapshot file was generated
        import re
        match = re.search(r"\[Snapshot\]\((.*\.yml)\)", output)
        if match:
            snapshot_path = match.group(1).strip()
            try:
                with open(snapshot_path, "r") as f:
                    snapshot_content = f.read()
                    
                import os
                if os.path.exists(snapshot_path):
                    os.remove(snapshot_path)

                output += f"\n\n### Snapshot Content ({snapshot_path})\n{snapshot_content}\n"
            except Exception as read_err:
                output += f"\n\n### Snapshot Content Error\nCould not read snapshot: {read_err}\n"
                
        return {"status": "success", "output": output}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def save_case_study(topic: str, case_studies: CaseStudyList) -> dict:
    """Saves a structured list of case studies to the local knowledge base directory as a JSON file.

    Args:
        topic: The search topic or domain (e.g. 'retail', 'agentic_ai').
        case_studies: The structured CaseStudyList object containing extracted case studies.

    Returns:
        dict with status and filepath.
    """
    # Sanitize names for filenames
    def sanitize(name: str):
         return name.translate(str.maketrans("", "", punctuation)).replace(" ", "_").lower()
    
    topic_clean = sanitize(topic)
    
    filename = f"{topic_clean}_top_case_studies.json"
    
    # Target directory setup
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    kb_dir = os.path.join(base_dir, "knowledge_base")
    os.makedirs(kb_dir, exist_ok=True)
    
    filepath = os.path.join(kb_dir, filename)
    
    try:
        with open(filepath, "w") as f:
            f.write(case_studies.model_dump_json(indent=2))
        return {"status": "success", "filepath": filepath}
    except Exception as e:
        return {"status": "error", "message": str(e)}
