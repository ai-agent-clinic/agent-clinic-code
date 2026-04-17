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

import asyncio
import json
import csv
import io
import datetime
from quart import Quart, request, make_response, render_template
from quart_cors import cors

# Import the SequentialAgent runner function
from improved_agent.agents.titanium_pro.agent import generate_intel

app = Quart(__name__)
# Enable CORS for the streaming endpoint if frontend is served separately
app = cors(app, allow_origin="*")

@app.before_serving
async def startup():
    from improved_agent.agents.titanium_pro.vector_search import initialize_collection
    import asyncio
    print("Checking/Initializing Vector Search Collection...")
    try:
        await asyncio.to_thread(initialize_collection)
    except Exception as e:
        print(f"Failed to initialize Vector Search collection: {e}")

@app.route("/")
async def index():
    """Renders the main dashboard interface."""
    return await render_template("index.html")

@app.route("/stream", methods=["POST"])
async def stream():
    """
    Accepts a JSON payload with:
    - csv_data: A string containing CSV rows (Company Name, Domain, Industry).
    - persona: The target persona constraint (e.g., 'CFO', 'CTO').
    
    Returns a Server-Sent Events (SSE) stream of JSON objects detailing 
    execution progress and the final payload.
    """
    data = await request.get_json()
    csv_data = data.get("csv_data", "")
    persona = data.get("persona", "CTO")

    # Parse the CSV data
    companies = []
    if csv_data:
        reader = csv.reader(io.StringIO(csv_data))
        for row in reader:
            if not row or len(row) < 2:
                continue
            # Skip common header strings
            if row[0].strip().lower() in ["company name", "company", "name"]:
                continue
            
            companies.append({
                "Company Name": row[0].strip(),
                "Domain": row[1].strip()
            })
    
    if not companies:
        return {"error": "No valid companies found in CSV data."}, 400

    async def event_stream():
        # Setup queues to communicate between the background runners and the SSE stream
        queue = asyncio.Queue()

        async def worker(company):
            target_str = f"{company['Company Name']} ({company['Domain']})"
            
            # Send start event
            await queue.put({
                "type": "status",
                "company": company['Company Name'],
                "message": f"Initializing Titanium Pro pipeline for {company['Company Name']}..."
            })
            
            try:
                # Execute the ADK Sequential Agent
                # TODO: To get Granular steps, we would need to yield from the Runner
                # But since we are using asyncio.run under the hood of runner in a single awaitable 
                # We will just emit the final result when complete.
                
                await queue.put({
                    "type": "status",
                    "company": company['Company Name'],
                    "message": "Gathering Strategic Context, Planning Search, Down-Selecting Case Studies, and Drafting Email..."
                })
                
                result = await generate_intel(
                    target_name=company['Company Name'],
                    domain=company['Domain'],
                    role=persona
                )
                
                await queue.put({
                    "type": "complete",
                    "company": company['Company Name'],
                    "data": result
                })
                
            except Exception as e:
                await queue.put({
                    "type": "error",
                    "company": company['Company Name'],
                    "message": str(e)
                })

        # Fire off all workers concurrently
        tasks = [asyncio.create_task(worker(c)) for c in companies]

        # Monitor queue and yield to SSE client
        # We need a way to know when all tasks are done.
        async def task_monitor():
            await asyncio.gather(*tasks)
            await queue.put({"type": "done"})

        monitor_task = asyncio.create_task(task_monitor())

        while True:
            event = await queue.get()
            if event["type"] == "done":
                break
            
            # Format as SSE
            yield f"data: {json.dumps(event)}\n\n"
            
    response = await make_response(event_stream(), {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Transfer-Encoding': 'chunked',
    })
    response.timeout = None
    return response

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
