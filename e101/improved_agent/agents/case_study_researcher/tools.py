import os
import subprocess
from string import punctuation


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
                output += f"\n\n### Snapshot Content ({snapshot_path})\n{snapshot_content}\n"
            except Exception as read_err:
                output += f"\n\n### Snapshot Content Error\nCould not read snapshot: {read_err}\n"
                
        return {"status": "success", "output": output}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def save_case_study(topic: str, company: str, markdown_content: str) -> dict:
    """Saves a markdown string to the local knowledge base directory.

    Args:
        topic: The search topic or domain (e.g. 'retail', 'agentic_ai').
        company: The name of the customer/company.
        markdown_content: The formatted markdown text to save.

    Returns:
        dict with status and filepath.
    """
    # Sanitize names for filenames
    def sanitize(name: str):
         return name.translate(str.maketrans("", "", punctuation)).replace(" ", "_").lower()
    
    topic_clean = sanitize(topic)
    company_clean = sanitize(company)
    
    filename = f"{topic_clean}_{company_clean}.md"
    
    # Target directory setup
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    kb_dir = os.path.join(base_dir, "knowledge_base")
    os.makedirs(kb_dir, exist_ok=True)
    
    filepath = os.path.join(kb_dir, filename)
    
    try:
        with open(filepath, "w") as f:
            f.write(markdown_content)
        return {"status": "success", "filepath": filepath}
    except Exception as e:
        return {"status": "error", "message": str(e)}
