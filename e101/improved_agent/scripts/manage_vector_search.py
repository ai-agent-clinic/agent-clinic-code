import argparse
import sys

from improved_agent.agents.titanium_pro.vector_search import (
    initialize_collection,
    search_vector_search,
    get_clients,
    _get_project_and_location,
    get_collection_id
)

def delete_collection():
    project_id, location = _get_project_and_location()
    collection_id = get_collection_id()
    client, _, _ = get_clients()
    parent = f"projects/{project_id}/locations/{location}"
    col_name = f"{parent}/collections/{collection_id}"
    try:
        print(f"Deleting collection: {col_name}...")
        operation = client.delete_collection(name=col_name)
        operation.result()
        print("Deleted successfully.")
    except Exception as e:
        print(f"Failed to delete or collection doesn't exist: {e}")

def reset_collection():
    delete_collection()
    print("Re-initializing collection...")
    initialize_collection()

def query_collection(query_text, company):
    print(f"Querying for '{query_text}' with company filter '{company}'...")
    results = search_vector_search(query_text, company)
    if not results:
        print("No results found.")
    for i, res in enumerate(results):
        print(f"\n--- Result {i+1} ---")
        print(f"ID: {res.get('id')}")
        print(f"Company: {res.get('company')}")
        print(f"Industry: {res.get('industry')}")
        print(f"Content snippet: {res.get('content', '')[:300]}...\n")

import json
import os
from google.cloud import vectorsearch_v1beta

def export_collection(output_file="data/exported_case_studies.jsonl"):
    print(f"Exporting Vector Search collection to {output_file}...")
    project_id, location = _get_project_and_location()
    collection_id = get_collection_id()
    client, _, search_client = get_clients()
    
    parent = f"projects/{project_id}/locations/{location}/collections/{collection_id}"
    
    # We use empty query and exact match or broad fields to fetch as many as possible
    # We will fetch up to 2000 results since our crawler found 1669 URLs
    try:
        request = vectorsearch_v1beta.BatchSearchDataObjectsRequest(
            parent=parent,
            searches=[
                vectorsearch_v1beta.Search(
                    text_search=vectorsearch_v1beta.TextSearch(
                        search_text="Cloud", # almost every case study contains "Cloud"
                        data_field_names=["company", "content", "industry"],
                        top_k=2000,
                        output_fields=vectorsearch_v1beta.OutputFields(
                            data_fields=["*"]
                        ),
                    )
                )
            ]
        )
        response = search_client.batch_search_data_objects(request)
        
        exported_count = 0
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w') as f:
            if response.results:
                for combined_results in response.results:
                    for result in combined_results.results:
                        data = result.data_object.data
                        record = {
                            "id": result.data_object.name.split("/")[-1],
                            "company": data.get("company", ""),
                            "content": data.get("content", ""),
                            "industry": data.get("industry", ""),
                            "products_used": data.get("products_used", ""),
                            "metrics": data.get("metrics", ""),
                        }
                        f.write(json.dumps(record) + "\n")
                        exported_count += 1
                    
        print(f"Successfully exported {exported_count} records to {output_file}")
    except Exception as e:
        print(f"Error exporting collection: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage the Titanium Pro Vector Search Cache")
    parser.add_argument("action", choices=["delete", "reset", "init", "query", "export"], help="The action to perform")
    parser.add_argument("--query", type=str, help="Search query text (required for 'query')", default="")
    parser.add_argument("--company", type=str, help="Company name for filtering (optional for 'query')", default="")
    parser.add_argument("--output", type=str, help="Output file for export", default="data/exported_case_studies.jsonl")
    
    args = parser.parse_args()
    
    if args.action == "delete":
        delete_collection()
    elif args.action == "reset":
        reset_collection()
    elif args.action == "init":
        initialize_collection()
    elif args.action == "query":
        if not args.query and not args.company:
            print("Error: Please provide --query or --company for searching.")
            sys.exit(1)
        query_collection(args.query, args.company)
    elif args.action == "export":
        export_collection(args.output)
