# Recipe 04: RAG with Vector Search

This recipe details how to integrate Google Cloud Vertex AI Vector Search into an ADK pipeline to enable Retrieval-Augmented Generation (RAG).

## Why It Matters
Agents hallucinate when they lack ground-truth data. Injecting a massive corpus of context directly into the prompt is often impossible due to token limits or cost. Vector Search allows the agent to semantically query a local or cloud-based database and pull only the most relevant text chunks into its context window precisely when needed.

## Building the Vector Search Store

In ADK, Vector Search is often exposed as a tool to the LLM. 
To power that tool, we need a data pipeline to ingest and embed documents. 

Using the `google.genai.Client`, you can create a corpus, document, and chunk:

```python
from google import genai
from google.genai import types

client = genai.Client()

def create_corpus_and_document(corpus_name: str, document_name: str, content: str):
    # 1. Create Corpus
    corpus = client.models.create_corpus(
        corpus=types.Corpus(
            name=f"corpora/{corpus_name}",
            display_name=corpus_name,
        )
    )
    
    # 2. Create Document
    document = client.models.create_document(
        corpus.name,
        document=types.Document(
            name=f"{corpus.name}/documents/{document_name}",
            display_name=document_name,
        )
    )
    
    # 3. Create Chunk & Embed
    chunk = client.models.create_chunk(
        document.name,
        chunk=types.Chunk(
            name=f"{document.name}/chunks/chunk_1",
            data=types.ChunkData(string_value=content),
        )
    )
    
    return corpus.name
```

## Creating the ADK Tool

To let the agent access this data, wrap the semantic search functionality into a native Python tool with the `verb_noun` naming convention, using explicit docstrings to guide the LLM's usage.

```python
def search_vector_search_tool(query: str, filters: str = "") -> str:
    """Searches the local Vector Search cache for insights.
    
    Args:
        query: The semantic search string.
        filters: Optional metadata filters.
        
    Returns:
        The matched text chunks.
    """
    client = genai.Client()
    corpora = list(client.models.list_corpora())
    if not corpora:
        return "No insights available in cache."
        
    results = client.models.query_corpus(
        corpora[0].name,
        query=query,
        results_count=3
    )
    
    # Format and return the text chunks to the LLM
    text_results = []
    for r in results:
        text_results.append(r.chunk.data.string_value)
        
    return "\n\n".join(text_results)
```

## Attaching to the Agent

Finally, pass the tool directly into the `tools` array of your ADK `Agent`. The framework handles the JSON schema translation and tool execution loop natively.

```python
from google.adk.agents.llm_agent import Agent

analyst_agent = Agent(
    name="financial_analyst",
    instruction="Answer the user's questions based ONLY on retrieved case studies.",
    tools=[search_vector_search_tool],  # <-- ADK hooks this up natively
)
```

## Key Takeaways
1.  **Tool Signatures Matter:** The LLM only knows how to use your tool based on the arguments (`query`, `filters`) and the docstring you provide. Be explicit about what the tool does and what it returns.
2.  **RAG is just a Tool:** In ADK, RAG isn't a complex architectural pattern; it's simply a tool that executes semantic search and returns a string to the prompt.
