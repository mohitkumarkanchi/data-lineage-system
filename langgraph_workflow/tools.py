import os
import logging
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from neo4j import GraphDatabase, exceptions as neo4j_exceptions

try:
    import ollama
except ImportError:
    ollama = None  # Ollama SDK not installed

# Configure logger
logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "tempInstance")

try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    logger.info("Connected to Neo4j database.")
except neo4j_exceptions.ServiceUnavailable as e:
    logger.error(f"Failed to connect to Neo4j: {e}")
    driver = None  # Handle connection failure gracefully


@tool
def execute_cypher(query: str) -> str:
    """
    Execute Cypher query on Neo4j and return results as string.
    Returns error message if execution fails.
    """
    if driver is None:
        error_msg = "Neo4j driver not initialized."
        logger.error(error_msg)
        return error_msg

    try:
        with driver.session() as session:
            result = session.run(query)
            records = [record.data() for record in result]
        logger.debug(f"Cypher query executed: {query}")
        return str(records)
    except neo4j_exceptions.Neo4jError as e:
        logger.error(f"Cypher query failed: {e}")
        return f"Cypher query error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error during Cypher query execution: {e}")
        return f"Unexpected error: {str(e)}"

def extract_cypher_query(text: str) -> str:
    """
    Extracts the Cypher query from the LLaMA output text, assuming it starts with a Cypher keyword like MATCH.
    """
    import re
    # Common Cypher keywords that can start a query
    keywords = ["MATCH", "WITH", "CREATE", "MERGE", "OPTIONAL MATCH", "UNWIND"]
    
    # Find the earliest occurrence of one of the keywords ignoring case
    pattern = re.compile(
        r"(" + "|".join(keywords) + r")", re.IGNORECASE
    )
    match = pattern.search(text)
    if match:
        # Return text starting at the first matched keyword
        return text[match.start():].strip()
    else:
        # If no keyword found, return original text (fallback)
        return text.strip()

@tool
def call_llama(prompt: str) -> str:
    """
    Call LLaMA model via Ollama SDK to generate Cypher query.
    Falls back to heuristic if SDK unavailable or on error.
    """
    if ollama is not None:
        model_name = "llama3.2"  # Adjust as needed
        try:
            response = ollama.generate(model=model_name, prompt=prompt)
            output_text = response.get("response", "").strip()
            cypher_query = extract_cypher_query(output_text)
            logger.debug(f"LLaMA model response received.")
            return cypher_query
        except Exception as e:
            logger.error(f"Error calling LLaMA model: {e}")
            return f"Error calling LLaMA model: {str(e)}"
    else:
        logger.warning("Ollama SDK not installed, using fallback heuristic.")
        prompt_lower = prompt.lower()
        try:
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
        except Exception as e:
            logger.error(f"Fallback heuristic error: {e}")
            return f"Fallback heuristic error: {str(e)}"
