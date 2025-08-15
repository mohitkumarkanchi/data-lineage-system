import os

FILES = {
    # Data folders (empty here, you can add JSONs separately)
    # We focus on code directories and files
    "neo4j_scripts/create_schema.cypher":
        """
// Ensure unique node ids for each entity type
CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (p:Post) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (f:FactCheck) REQUIRE f.id IS UNIQUE;
        """.strip(),

    "neo4j_scripts/import_data.cypher":
        """
// Import Users
CALL apoc.load.json("file:///users.json") YIELD value AS user
MERGE (u:User {id: user.id})
SET u.name = user.name,
    u.username = user.username,
    u.email = user.email,
    u.followers = user.followers,
    u.account_created = date(user.account_created),
    u.verified = user.verified,
    u.location = user.location;

// Import Posts
CALL apoc.load.json("file:///posts.json") YIELD value AS post
MERGE (p:Post {id: post.id})
SET p.content = post.content,
    p.timestamp = datetime(post.timestamp),
    p.likes = post.likes,
    p.shares = post.shares,
    p.comments = post.comments,
    p.platform = post.platform,
    p.tags = post.tags,
    p.shared_post_id = post.shared_post_id;

// Import FactChecks
CALL apoc.load.json("file:///factchecks.json") YIELD value AS fc
MERGE (f:FactCheck {id: fc.id})
SET f.status = fc.status,
    f.verified_at = datetime(fc.verified_at),
    f.comments = fc.comments,
    f.source_url = fc.source_url;

// Create relationships from relationships.json
CALL apoc.load.json("file:///relationships.json") YIELD value AS rel
MATCH (fromNode {id: rel.from}), (toNode {id: rel.to})
CALL apoc.do.when(
  rel.relationship = "CREATED",
  'MERGE (fromNode)-[:CREATED]->(toNode)',
  '',
  {fromNode: fromNode, toNode: toNode}
) YIELD value
CALL apoc.do.when(
  rel.relationship = "VERIFIED_BY",
  'MERGE (fromNode)-[:VERIFIED_BY]->(toNode)',
  '',
  {fromNode: fromNode, toNode: toNode}
) YIELD value
CALL apoc.do.when(
  rel.relationship = "SHARED",
  'MERGE (fromNode)-[:SHARED]->(toNode)',
  '',
  {fromNode: fromNode, toNode: toNode}
) YIELD value
RETURN "Import complete";
        """.strip(),

    "langgraph_workflow/tools.py":
        """\
import os
from langgraph import tool
from pydantic import BaseModel, Field
from neo4j import GraphDatabase

try:
    import ollama
except ImportError:
    ollama = None  # Ollama SDK not installed

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


class CypherQuery(BaseModel):
    query: str = Field(description="Cypher query string")


@tool
def execute_cypher(query: str) -> str:
    with driver.session() as session:
        result = session.run(query)
        records = [record.data() for record in result]
    return str(records)


def build_llama_prompt(user_question: str) -> str:
    template = \"\"\"
You are a helpful assistant that converts natural language queries about social media viral posts and fact-check lineage into Cypher queries for the Neo4j database.

Here are some examples:

Q: Show me the most viral posts on Twitter
A: MATCH (p:Post) WHERE p.shares > 100 AND p.platform = 'Twitter' RETURN p.id, p.content, p.shares ORDER BY p.shares DESC LIMIT 5

Q: Find posts verified as false news
A: MATCH (p:Post)-[:VERIFIED_BY]->(f:FactCheck {status: "False"}) RETURN p.id, p.content, f.comments LIMIT 5

Now, generate a Cypher query for the following question:
Q: {question}
A:\"\"\"
    return template.format(question=user_question)


class LLaMAPrompt(BaseModel):
    prompt: str = Field(description="Natural language prompt for LLaMA model")


@tool
def call_llama(prompt: str) -> str:
    # If ollama SDK available, call real LLaMA model
    if ollama is not None:
        model_name = "llama3.2b"  # Adjust model name accordingly
        full_prompt = build_llama_prompt(prompt)
        try:
            response = ollama.generate(model=model_name, prompt=full_prompt)
            return response.get("response", "").strip()
        except Exception as e:
            return f"Error calling LLaMA model: {str(e)}"
    else:
        # Fallback: simple heuristic mock
        prompt_lower = prompt.lower()

        if "viral" in prompt_lower:
            return (
                "MATCH (p:Post) WHERE p.shares > 100 RETURN p.id, p.content, p.shares "
                "ORDER BY p.shares DESC LIMIT 5"
            )
        elif "fake news" in prompt_lower:
            return (
                "MATCH (p:Post)-[:VERIFIED_BY]->(f:FactCheck {status:'False'}) "
                "RETURN p.id, p.content, f.comments LIMIT 5"
            )
        elif "shared" in prompt_lower or "share" in prompt_lower:
            return (
                "MATCH (p:Post)-[:SHARED]->(original:Post) "
                "RETURN p.id, p.content, original.id as shared_post_id LIMIT 5"
            )
        else:
            safe_prompt = prompt.replace("'", "\\'")
            return (
                f"MATCH (p:Post) WHERE toLower(p.content) CONTAINS toLower('{safe_prompt}') "
                "RETURN p.id, p.content, p.timestamp LIMIT 5"
            )
        """,

    "langgraph_workflow/state_graph.py":
        """\
from langgraph import StateGraph, State, GraphConfig
from langgraph_workflow.tools import call_llama, execute_cypher


class LineageGraph(StateGraph):
    def __init__(self):
        super().__init__(GraphConfig(name="SocialMediaLineageGraph"))

        # Define states
        self.start = State(name="start")
        self.generating_cypher = State(name="generating_cypher")
        self.executing_query = State(name="executing_query")
        self.done = State(name="done")

        # User input text (the natural language query)
        self.query_text: str = ""

        # Response storage
        self.cypher_query: str = ""
        self.query_result: str = ""

        @self.start.on_action
        def generate_cypher():
            self.cypher_query = call_llama(self.query_text)
            return self.generating_cypher

        @self.generating_cypher.on_action
        def run_cypher():
            self.query_result = execute_cypher(self.cypher_query)
            return self.executing_query

        @self.executing_query.on_action
        def finish():
            return self.done
        """,

    "langgraph_workflow/agent.py":
        """\
from langgraph_workflow.state_graph import LineageGraph


class LineageAgent:
    def __init__(self):
        self.graph = LineageGraph()

    def query_lineage(self, natural_language_query: str) -> str:
        self.graph.query_text = natural_language_query

        current_state = self.graph.start

        while current_state.name != "done":
            next_state = current_state.action()
            current_state = next_state

        return self.graph.query_result
        """,

    "interface/service.py":
        """\
from langgraph_workflow.agent import LineageAgent


class LineageService:
    def __init__(self):
        self.agent = LineageAgent()

    def ask_lineage(self, query: str) -> str:
        return self.agent.query_lineage(query)
        """,

    "interface/api.py":
        """\
import logging
import os

from fastapi import FastAPI, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader, APIKey
from pydantic import BaseModel

from interface.service import LineageService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY_NAME = "access_token"
API_KEY = os.getenv("API_KEY", "YOUR_SECRET_API_KEY")  # Replace or set env var securely

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

app = FastAPI(title="Social Media Viral/Fake News Data Lineage API")

service = LineageService()


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str


async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == API_KEY:
        return api_key_header
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing API Key"
        )


@app.post("/query_lineage", response_model=QueryResponse)
async def query_lineage(request: QueryRequest, api_key: APIKey = Security(get_api_key)):
    try:
        logger.info(f"Received query: {request.question}")
        answer = service.ask_lineage(request.question)
        logger.info(f"Returning answer")
        return QueryResponse(answer=answer)
    except Exception:
        logger.exception("Error processing query")
        raise HTTPException(status_code=500, detail="Internal server error")
        """,

    "streamlit_app.py":
        """\
import streamlit as st
import requests
import json
import re

API_URL = "http://localhost:8000/query_lineage"  # Adjust to your API URL


def make_links_clickable(text):
    url_pattern = r"https?://[^\s]+"
    return re.sub(url_pattern, lambda m: f"[{m.group(0)}]({m.group(0)})", text)


st.title("Social Media Viral/Fake News Data Lineage Explorer")

st.markdown(
    \"\"\"
Enter a natural language question to explore data lineage, viral posts, or fact-check information.

Examples:
- Show me the most viral posts this week.
- Are there any fake news posts about 5G?
- Who shared the COVID variant news?
\"\"\"
)

query = st.text_input("Enter your question:")

if "history" not in st.session_state:
    st.session_state.history = []

if st.button("Ask"):
    if not query.strip():
        st.error("Please enter a question before submitting.")
    else:
        with st.spinner("Fetching results..."):
            try:
                response = requests.post(API_URL, json={"question": query})
                response.raise_for_status()
                answer = response.json().get("answer", "")

                # Save to history
                st.session_state.history.append((query, answer))

                # Try parse JSON and display nicely
                try:
                    parsed_answer = json.loads(answer)
                    if isinstance(parsed_answer, list) and parsed_answer:
                        st.table(parsed_answer)
                    else:
                        st.json(parsed_answer)
                except json.JSONDecodeError:
                    answer_md = make_links_clickable(answer)
                    st.markdown(answer_md)

            except requests.exceptions.RequestException as e:
                st.error(f"API request failed. Details: {e}")

if st.session_state.history:
    st.sidebar.header("Query History")
    for q, a in reversed(st.session_state.history[-10:]):
        st.sidebar.markdown(f"**Q:** {q}")
        st.sidebar.markdown(f"**A:** {a}")
        st.sidebar.markdown("---")
        """,
}

DIRS = [
    "neo4j_scripts",
    "langgraph_workflow",
    "interface",
]

def create_dirs():
    for d in DIRS:
        os.makedirs(d, exist_ok=True)
        print(f"Ensured directory: {d}")

def write_files():
    for filepath, content in FILES.items():
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
        print(f"Wrote file: {filepath}")

def main():
    print("Setting up project directories and files...")
    create_dirs()
    write_files()
    print("Setup complete!")
    print("Please adjust environment variables (Neo4j, Ollama, API_KEY) as needed.")
    print("Place your JSON data files in Neo4j import directory before running Cypher import.")
    print("Run FastAPI with uvicorn interface.api:app --reload")
    print("Run Streamlit with streamlit run streamlit_app.py")

if __name__ == "__main__":
    main()
