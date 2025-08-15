import logging
from langgraph_workflow.stategraph import graph

logger = logging.getLogger(__name__)


def run_agent_query(user_question: str):
    """
    Run the LangGraph workflow graph with user question and return query results.
    """
    initial_state = {
        "query": user_question,
        "llama_prompt": "",
        "llama_response": "",
        "cypher_result": "",
    }
    try:
        final_state = graph.invoke(initial_state)
        logger.info("Graph invoked successfully.")
        return final_state
    except Exception as e:
        logger.error(f"Error during graph invocation: {e}")
        return {
            "query": user_question,
            "llama_prompt": "",
            "llama_response": "",
            "cypher_result": f"Error during graph invocation: {str(e)}",
        }
