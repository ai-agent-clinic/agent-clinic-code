import os
import hashlib
from google.cloud import vectorsearch_v1beta


def _get_project_and_location():
    project_id = os.environ.get("PROJECT_ID")
    location = os.environ.get("LOCATION", "us-central1")
    if not project_id:
        raise ValueError("PROJECT_ID environment variable not set.")
    return project_id, location


def get_collection_id() -> str:
    return os.environ.get("VECTOR_SEARCH_COLLECTION_ID", "case-studies")


def get_clients():
    vector_search_service_client = vectorsearch_v1beta.VectorSearchServiceClient()
    data_object_service_client = vectorsearch_v1beta.DataObjectServiceClient()
    data_object_search_service_client = (
        vectorsearch_v1beta.DataObjectSearchServiceClient()
    )
    return (
        vector_search_service_client,
        data_object_service_client,
        data_object_search_service_client,
    )


def initialize_collection():
    """Initializes the Vector Search Collection if it doesn't exist."""
    project_id, location = _get_project_and_location()
    collection_id = get_collection_id()
    vector_search_service_client, _, _ = get_clients()

    parent = f"projects/{project_id}/locations/{location}"
    collection_name = f"{parent}/collections/{collection_id}"

    # Check if exists
    try:
        vector_search_service_client.get_collection(name=collection_name)
        print(f"Collection {collection_id} already exists.")
        return
    except Exception as e:
        if "NOT_FOUND" not in str(e) and "404" not in str(e):
            print(f"Error checking collection: {e}")
            # we might just want to continue or raise
            pass

    print(f"Creating Collection: {collection_id}...")
    request = vectorsearch_v1beta.CreateCollectionRequest(
        parent=parent,
        collection_id=collection_id,
        collection={
            "data_schema": {
                "type": "object",
                "properties": {
                    "source_url": {"type": "string"},
                    "company": {"type": "string"},
                    "content": {"type": "string"},
                    "industry": {"type": "string"},
                    "products_used": {"type": "string"},
                    "metrics": {"type": "string"},
                },
            },
            "vector_schema": {
                "content_embedding": {
                    "dense_vector": {
                        "dimensions": 768,
                        "vertex_embedding_config": {
                            "model_id": os.environ.get(
                                "EMBEDDING_MODEL", "gemini-embedding-001"
                            ),
                            "text_template": ("Company: {company} Content: {content}"),
                            "task_type": "RETRIEVAL_DOCUMENT",
                        },
                    }
                },
            },
        },
    )

    operation = vector_search_service_client.create_collection(request=request)
    operation.result()
    print(f"Collection {collection_id} created successfully.")


def search_vector_search(query: str, company: str, top_k: int = 5) -> list[dict]:
    """Executes a Hybrid Search against the Vector Search Collection."""
    project_id, location = _get_project_and_location()
    collection_id = get_collection_id()
    _, _, data_object_search_service_client = get_clients()
    parent = f"projects/{project_id}/locations/{location}/collections/{collection_id}"

    # We will do hybrid search looking for both semantic meaning and keyword matches.
    batch_search_request = vectorsearch_v1beta.BatchSearchDataObjectsRequest(
        parent=parent,
        searches=[
            vectorsearch_v1beta.Search(
                semantic_search=vectorsearch_v1beta.SemanticSearch(
                    search_text=f"{company} {query}",
                    search_field="content_embedding",
                    task_type="QUESTION_ANSWERING",
                    top_k=top_k,
                    output_fields=vectorsearch_v1beta.OutputFields(data_fields=["*"]),
                )
            ),
            vectorsearch_v1beta.Search(
                text_search=vectorsearch_v1beta.TextSearch(
                    search_text=f"{company} {query}",
                    data_field_names=["company", "content", "industry"],
                    top_k=top_k,
                    output_fields=vectorsearch_v1beta.OutputFields(data_fields=["*"]),
                )
            ),
        ],
        combine=vectorsearch_v1beta.BatchSearchDataObjectsRequest.CombineResultsOptions(
            ranker=vectorsearch_v1beta.Ranker(
                rrf=vectorsearch_v1beta.ReciprocalRankFusion(weights=[1.0, 1.0])
            )
        ),
    )

    try:
        batch_results = data_object_search_service_client.batch_search_data_objects(
            batch_search_request
        )
        results = []
        if batch_results.results:
            combined_results = batch_results.results[0]
            for result in combined_results.results:
                data = result.data_object.data
                results.append(
                    {
                        "id": result.data_object.name.split("/")[-1],
                        "company": data.get("company", ""),
                        "content": data.get("content", ""),
                        "industry": data.get("industry", ""),
                        "products_used": data.get("products_used", ""),
                        "metrics": data.get("metrics", ""),
                    }
                )
        return results
    except Exception as e:
        print(f"Vector search failed: {e}")
        return []


def insert_case_study_into_cache(
    source_url: str,
    company: str,
    content: str,
    industry: str = "",
    products_used: str = "",
    metrics: str = "",
):
    """Inserts a single case study into the Vector Search Collection for lazy caching."""
    project_id, location = _get_project_and_location()
    collection_id = get_collection_id()
    _, data_object_service_client, _ = get_clients()
    parent = f"projects/{project_id}/locations/{location}/collections/{collection_id}"

    # Create an idempotent ID using a hash of the URL to prevent duplicates from breaking.
    # The user asked to use the URL itself as the ID, but it should be a valid string for data_object_id.
    # URLs often contain slashes and special characters which might not be valid for resource names.
    # Let's URL-encode it just in case, or hash it as originally suggested?
    # "Since every case study has a unique URL, let's use that as the dedupe key."
    # Let's try inserting with the URL encoded. If it fails due to character limits, we hash.
    import hashlib

    safe_id = hashlib.sha256(source_url.encode("utf-8")).hexdigest()

    request = vectorsearch_v1beta.CreateDataObjectRequest(
        parent=parent,
        data_object_id=safe_id,
        data_object={
            "data": {
                "source_url": source_url,
                "company": company,
                "content": content[
                    -32000:
                ],  # ensure we don't exceed text max length limits
                "industry": industry,
                "products_used": products_used,
                "metrics": metrics,
            },
            "vectors": {},  # Trigger auto-embed
        },
    )
    try:
        data_object_service_client.create_data_object(request=request)
    except Exception as e:
        if "already exists" not in str(e).lower() and "409" not in str(e):
            print(f"Failed to insert into vector search cache: {e}")
