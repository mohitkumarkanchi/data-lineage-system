import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from interface.service import QueryService

logger = logging.getLogger(__name__)

app = FastAPI(title="Social Media Query API")


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    result: str


@app.post("/query", response_model=QueryResponse)
def process_query(req: QueryRequest):
    if not req.question.strip():
        logger.warning("Empty question submitted.")
        raise HTTPException(status_code=400, detail="Question must not be empty")

    try:
        result = QueryService.run_query(req.question)
        logger.info("API query processed successfully.")
        return QueryResponse(result=result)
    except Exception as e:
        logger.error(f"API error processing query: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
