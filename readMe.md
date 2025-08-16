# Viral and Fake News Data Lineage Tracking System

This project is designed to track the lifecycle of social media posts or news articles to understand their origin, transformations (like edits or re-shares), propagation paths, and engagement metrics that contribute to virality or misinformation.

## Features

- Query social media data using natural language.
- Generate Cypher queries for Neo4j using LLaMA-based AI.
- Visualize results in a Streamlit web application.
- Fact-check and track viral posts.

## Architecture

Refer to the [architecture.txt](architecture.txt) file for a detailed description of the system's use case, entities, and relationships.

## Prerequisites

1. Install Python 3.10 or higher.
2. Install Neo4j and ensure it is running. Update the `.env` file with your Neo4j credentials:
NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=tempInstance

3. Install Conda (optional but recommended).

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/mohitkumarkanchi/data-lineage-system.git
cd data-lineage-system
```

### 2. Create a Virtual Environment

Using Conda:

```bash
conda env create -f environment.yml
conda activate data_lineage_env
```

Using venv and pip:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

###  3. Start the FastAPI Backend

Run the FastAPI server to handle queries:
```bash
uvicorn interface.api:app --reload
```
### 4 . 4. Start the Streamlit Frontend
Run the Streamlit app to interact with the system:

```bash
streamlit run streamlit_app.py
```


## Architecture

This system provides natural language query (NLQ) to Cypher translation for lineage analytics over social media graph data, powered by **Llama 3.2B** and **Neo4j**. It supports temporal filtering, multi-hop relationship queries, schema enforcement, result summarization, and robust Cypher validation.

***

## Components

### 1. `agent.py`
- Entry function (`run_agent_query`) accepts the user question and initializes the state for the graph workflow.
- Invokes the stategraph pipeline, returning the generated Llama prompt, Cypher query, query results, and summary.
- Handles workflow errors gracefully.

***

### 2. `stategraph.py`
- Defines the overall pipeline using LangGraph nodes.
- **Temporally aware prompt builder:**
  - Parses date phrases like "this week," "last week," "this month," "last year" and injects ISO datetime literals for Cypher queries.
- **Prompt template:**
  - Instructs Llama to output ONLY the Cypher query, with schema, examples, and robust instructions.
  - Schema matches the actual data, including extended user and post properties.
  - Multi-hop examples clarify intended complex lineage queries.
- **Nodes:**
  - `build_llama_prompt_node`: Creates the prompt.
  - `call_llama_node`: Runs the Llama model.
  - `execute_cypher_node`: Validates Cypher using Neo4j `EXPLAIN`, then executes.
  - `llama_summarize_node`: Summarizes the query result for user readability.
- Error handling and logging is present throughout.

***

### 3. `tools.py`
- Handles database connection and Cypher execution (`execute_cypher`), extracting Cypher queries (`extract_cypher_query`), and calling Llama (`call_llama`).
- Robust heuristic fallbacks for NLQ-to-Cypher translation when Ollama/Llama SDK isn’t available.
- Ensures Cypher extraction and execution errors are logged and returned cleanly.

***

## Key Architecture Improvements

- **Flexible Natural Date Parsing:** Supports “this week,” “last week,” “this month,” “last month,” etc.
- **Explicit Multi-Hop Prompting:** Prompt examples include multi-part queries across the graph.
- **Schema-Driven Validation:** Template and instructions tightly control query generation.
- **Cypher Validation Step:** Queries are dry-run validated before actual execution for safety and feedback.
- **Result Summarization:** Converts database results into readable summaries via Llama.
- **Extensible:** Easy to add new nodes for extra validation, enrichment, or analytics.

***

## Example Test Prompts and Expected Cyphers

#### 1. Viral Twitter posts this week
**Prompt:**  
Show me the most viral posts on Twitter this week  
**Cypher:**  
```cypher
MATCH (p:Post)
WHERE p.shares > 100 AND p.platform = 'Twitter' AND p.timestamp >= datetime('2025-08-11T00:00:00')
RETURN p.id, p.content, p.shares, p.timestamp
ORDER BY p.shares DESC
LIMIT 5
```

#### 2. Fact-checked false news this month
**Prompt:**  
Find posts verified as false news this month  
**Cypher:**  
```cypher
MATCH (p:Post)-[:VERIFIED_BY]->(f:FactCheck {status: "False"})
WHERE p.timestamp >= datetime('2025-08-01T00:00:00')
RETURN p.id, p.content, f.comments
LIMIT 5
```

#### 3. Who shared the COVID variant news?
**Prompt:**  
Who shared the COVID variant news?  
**Cypher:**  
```cypher
MATCH (u:User)-[:SHARED]->(p:Post)
WHERE toLower(p.content) CONTAINS 'covid variant'
RETURN u.id, u.name, p.content, p.timestamp
LIMIT 5
```

#### 4. Posts created by 'john_doe' and shared by 'emma_green' last month
**Prompt:**  
Find posts created by 'john_doe' and shared by 'emma_green' last month  
**Cypher:**  
```cypher
MATCH (u1:User {username: 'john_doe'})-[:CREATED]->(p:Post)= datetime('2025-07-01T00:00:00')
RETURN p.id, p.content, p.timestamp
LIMIT 5
```

#### 5. Posts about 'climate change' this year created by verified users
**Prompt:**  
Show posts about 'climate change' created by verified users this year  
**Cypher:**  
```cypher
MATCH (u:User)-[:CREATED]->(p:Post)
WHERE toLower(p.content) CONTAINS 'climate change'
  AND u.verified = true
  AND p.timestamp >= datetime('2025-01-01T00:00:00')
RETURN p.id, p.content, u.name, p.timestamp
LIMIT 10
```

#### 6. Top Instagram posts shared last week
**Prompt:**  
Show the top Instagram posts shared last week  
**Cypher:**  
```cypher
MATCH (u:User)-[:SHARED]->(p:Post)
WHERE p.platform = 'Instagram' AND p.timestamp >= datetime('2025-08-04T00:00:00')
RETURN p.id, p.content, p.shares, p.timestamp
ORDER BY p.shares DESC
LIMIT 5
```

***

## System Usage Notes

- NL queries are translated by Llama using an enforced schema and instructions for reliability.
- Date expressions are parsed and always injected as exact Cypher datetime filters.
- The system gracefully handles errors (both in query generation and execution).
- Output includes Cypher result and a descriptive summary for user consumption.

***

This architecture ensures that temporal and lineage-aware queries over social media graph data can be handled robustly, efficiently, and with clear user feedback.  
For further customization or extension (e.g., new temporal expressions, new relationships), simply adjust or add prompt examples and schema nodes/relations in `stategraph.py`.

UI : 

<img width="1324" height="813" alt="Screenshot 2025-08-16 at 6 13 36 PM" src="https://github.com/user-attachments/assets/628c2611-e1e1-46ab-ad41-8b400e7424b2" />



