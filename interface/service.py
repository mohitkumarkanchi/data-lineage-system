import logging
from langgraph_workflow.agent import run_agent_query

logger = logging.getLogger(__name__)


class QueryService:
    @staticmethod
    def run_query(user_question: str) -> str:
        """
        Run the multi-node LangGraph workflow for the user question.

        Returns:
            str: The Neo4j query results or error message.
        """
        try:
            final_state = run_agent_query(user_question)
            logger.info("QueryService: run_query completed.")
            return final_state.get("cypher_result", "No results found.")
        except Exception as e:
            logger.error(f"QueryService error: {e}")
            return f"Error running query: {str(e)}"
