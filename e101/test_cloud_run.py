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

import urllib.request
import json
import subprocess
import time
import os

env = os.environ.copy()
env['GUNICORN_CMD_ARGS'] = "--timeout 600"
env['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = "YES"
server = subprocess.Popen(["uv", "run", "functions-framework", "--source", "improved_agent/agents/titanium_pro/agent.py", "--target", "run_agent_logic", "--port", "8082"], env=env)

time.sleep(3)

data = json.dumps({"role": "CFO", "csv_data": "CVS Health,cvs.com\nTarget,target.com"}).encode('utf-8')
req = urllib.request.Request("http://localhost:8082", data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as response:
        print("Response Status:", response.status)
        print("Response HTML snippet:", response.read().decode('utf-8')[:200])
except Exception as e:
    print(f"Request failed: {e}")

server.terminate()
