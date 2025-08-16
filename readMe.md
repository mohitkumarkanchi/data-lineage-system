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

