import logging
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph_workflow.tools import call_llama, execute_cypher
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)

class GraphState(TypedDict):
    query: str
    llama_prompt: str
    llama_response: str
    cypher_result: str
    summary_result: str  # Add this new key for summary output

def build_llama_prompt_node(state: GraphState) -> dict:
    """
    Build prompt string for LLaMA to generate valid Cypher queries from natural language,
    supporting natural date expressions (this week, this month, etc.) that are converted
    to concrete ISO datetime strings, and prompt-enforced output validation.
    """

    def parse_natural_date_expression(nl_text: str) -> dict:
        """
        Detects natural language time expressions in the input question
        and returns a dict of date parameters for Cypher usage.
        Returns keys like 'start_of_week', 'start_of_month', 'start_of_year' as ISO strings.
        """
        res = {}
        text = nl_text.lower()
        today = datetime.utcnow()
        start_of_week = today - timedelta(days=today.weekday())  # Monday
        start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_of_year = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

        if "this week" in text:
            res["start_of_week"] = start_of_week.isoformat()

        if "last week" in text:
            last_week_start = start_of_week - timedelta(days=7)
            res["start_of_week"] = last_week_start.isoformat()

        if "this month" in text:
            res["start_of_month"] = start_of_month.isoformat()

        if "last month" in text:
            last_month = (start_of_month - timedelta(days=1)).replace(day=1)
            res["start_of_month"] = last_month.isoformat()

        if "this year" in text:
            res["start_of_year"] = start_of_year.isoformat()

        if "last year" in text:
            last_year_start = start_of_year.replace(year=start_of_year.year - 1)
            res["start_of_year"] = last_year_start.isoformat()

        return res

    date_params = parse_natural_date_expression(state["query"])

    date_clauses = []
    if "start_of_week" in date_params:
        date_clauses.append(f"p.timestamp >= datetime('{date_params['start_of_week']}')")
    if "start_of_month" in date_params:
        date_clauses.append(f"p.timestamp >= datetime('{date_params['start_of_month']}')")
    if "start_of_year" in date_params:
        date_clauses.append(f"p.timestamp >= datetime('{date_params['start_of_year']}')")

    if date_clauses:
        date_filter_clause = " AND (" + " OR ".join(date_clauses) + ")"
    else:
        date_filter_clause = ""

    template = f"""
You are a Cypher query generation assistant specialized in social media data lineage with temporal and relationship complexity.

Given a user's natural language question, generate a **valid Neo4j Cypher query only** — no explanations or comments.

---

**Important Instructions:**

- Only output the Cypher query.
- Use explicit datetime literals in ISO 8601 format like: datetime('2023-08-10T00:00:00')
- For natural language dates like 'this week', 'this month', 'this year', 'last week', 'last month', filter posts accordingly.
- Use the following date filters in your query:

{date_filter_clause if date_filter_clause else 'No date filters requested.'}

- Avoid any Cypher commands that modify or delete data such as DROP, DELETE, REMOVE.
- Prioritize read-only queries (MATCH, OPTIONAL MATCH, WHERE, RETURN).
- Return only relevant fields like p.id, p.content, p.shares, p.timestamp, user.id, etc.
- Limit results to reasonable numbers when applicable (e.g., LIMIT 5 or 10).

---

**Graph Database Schema:**

Nodes:

User: {{id (string), name (string), username (string), email (string), followers (integer), account_created (date), verified (boolean), location (string)}}

Post: {{id (string), content (string), likes (integer), shares (integer), comments (integer), platform (string), timestamp (datetime), author_id (string), tags (list of strings)}}

FactCheck: {{id (string), status (string), comments (string)}}

Relationships:

(u:User)-[:CREATED]->(p:Post)

(p:Post)-[:VERIFIED_BY]->(f:FactCheck)

(u:User)-[:SHARED]->(p:Post)

---

Examples:

Q: Show me the most viral posts on Twitter this week
A: MATCH (p:Post) WHERE p.shares > 100 AND p.platform = 'Twitter' AND p.timestamp >= datetime('{date_params.get("start_of_week", "2023-01-01T00:00:00")}') RETURN p.id, p.content, p.shares, p.timestamp ORDER BY p.shares DESC LIMIT 5

Q: Find posts verified as false news this month
A: MATCH (p:Post)-[:VERIFIED_BY]->(f:FactCheck {{status: "False"}}) WHERE p.timestamp >= datetime('{date_params.get("start_of_month", "2023-01-01T00:00:00")}') RETURN p.id, p.content, f.comments LIMIT 5

Q: Who shared the COVID variant news?
A: MATCH (u:User)-[:SHARED]->(p:Post) WHERE toLower(p.content) CONTAINS 'covid variant' RETURN u.id, u.name, p.content, p.timestamp LIMIT 5

Q: Find posts created by 'john_doe' and shared by 'emma_green' last month
A: MATCH (u1:User {{username: 'john_doe'}})-[:CREATED]->(p:Post)<-[:SHARED]-(u2:User {{username: 'emma_green'}}) WHERE p.timestamp >= datetime('2025-07-01T00:00:00') RETURN p.id, p.content, p.timestamp LIMIT 5

Q: List posts created by user john_doe this year
A: MATCH (u:User {{username: 'john_doe'}})-[:CREATED]->(p:Post) WHERE p.timestamp >= datetime('{date_params.get("start_of_year", "2023-01-01T00:00:00")}') RETURN p.id, p.content, p.timestamp LIMIT 5

---

Now, generate a Cypher query for the following user question.

Remember: Output only the Cypher query.

Q: {state['query']}

A:
"""
    return {"llama_prompt": template}

def call_llama_node(state: GraphState) -> dict:
    """Call LLaMA model to get Cypher query from prompt."""
    try:
        query = call_llama(state["llama_prompt"])
        logger.debug("LLaMA node generated Cypher query.")
        print("Constructed Query = ", query)
        return {"llama_response": query}
    except Exception as e:
        logger.error(f"Error in LLaMA node: {e}")
        return {"llama_response": ""}

def execute_cypher_node(state: GraphState) -> dict:
    """Run Cypher query and fetch results with validation."""
    try:
        # Validate Cypher query with EXPLAIN before executing
        explain_query = "EXPLAIN " + state["llama_response"]
        _ = execute_cypher(explain_query)  # Will raise if query invalid
        # Now execute actual query
        results = execute_cypher(state["llama_response"])
        print("results", results)
        logger.debug("Executed Cypher query successfully.")
        return {"cypher_result": results}
    except Exception as e:
        logger.error(f"Error executing Cypher query: {e}")
        return {"cypher_result": f"Error executing Cypher: {str(e)}"}

def llama_summarize_node(state: GraphState) -> dict:
    """
    Summarize Cypher results into human-readable text.
    """
    raw_result = state.get("cypher_result", "")
    prompt_template = f"""
summarize {raw_result} and give it in a descriptive way.
"""
    summary = call_llama(prompt_template)
    return {"summary_result": summary}

builder = StateGraph(GraphState)
builder.add_node(build_llama_prompt_node)
builder.add_node(call_llama_node)
builder.add_node(execute_cypher_node)
builder.add_node(llama_summarize_node)
builder.add_edge(START, "build_llama_prompt_node")
builder.add_edge("build_llama_prompt_node", "call_llama_node")
builder.add_edge("call_llama_node", "execute_cypher_node")
builder.add_edge("execute_cypher_node", "llama_summarize_node")
builder.add_edge("llama_summarize_node", END)
graph = builder.compile()
logger.info("LangGraph StateGraph compiled successfully.")
