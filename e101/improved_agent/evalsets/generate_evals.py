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

from google.adk.evaluation.eval_case import EvalCase
from google.adk.evaluation.eval_set import EvalSet

case1 = EvalCase(
    name="find_retail_bigquery_case_study",
    dataset=[
        {
            "messages": [
                {
                    "content": "Find a retail case study involving BigQuery.",
                    "role": "user"
                }
            ],
            "metrics": {
                "trajectory_metrics": [
                    {
                        "type": "tool_trajectory_exact_match",
                        "tool_names": [
                            "run_browser_command",
                            "run_browser_command",
                            "run_browser_command",
                            "run_browser_command",
                            "save_case_study",
                            "run_browser_command"
                        ]
                    }
                ]
            }
        }
    ]
)

case2 = EvalCase(
    name="find_agentic_ai_case_study",
    dataset=[
        {
            "messages": [
                {
                    "content": "Can you find a customer success story related to Agentic AI?",
                    "role": "user"
                }
            ],
            "metrics": {
                "trajectory_metrics": [
                    {
                        "type": "tool_trajectory_avg_precision",
                        "tool_names": [
                            "run_browser_command",
                            "save_case_study"
                        ]
                    }
                ]
            }
        }
    ]
)

evalset = EvalSet(
    name="research_evals",
    eval_cases=[case1, case2]
)

import json
with open("/Users/luissala/development/agent-clinic/e101/improved_agent/evalsets/research_evals_dump.json", "w") as f:
    f.write(evalset.model_dump_json(indent=4))
