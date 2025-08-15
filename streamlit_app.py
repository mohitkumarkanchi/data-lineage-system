import streamlit as st
import requests
import json
import re
import logging

logger = logging.getLogger(__name__)

API_URL = "http://localhost:8000/query"  # Adjust to your API URL


def make_links_clickable(text):
    """Convert URLs in the text into markdown clickable links."""
    url_pattern = r"https?://[^\s]+"
    return re.sub(url_pattern, lambda m: f"[{m.group(0)}]({m.group(0)})", text)


st.title("Social Media Viral/Fake News Data Lineage Explorer")

st.markdown(
    """
Enter a natural language question to explore data lineage, viral posts, or fact-check information.

Examples:
- Show me the most viral posts this week.
- provide top 5 posts with more likes this week.
- Who shared the COVID variant news?
"""
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
                data = response.json()
                answer = data.get("result", "")

                st.session_state.history.append((query, answer))

                try:
                    parsed_answer = json.loads(answer)
                    if isinstance(parsed_answer, list) and parsed_answer:
                        if all(isinstance(item, dict) for item in parsed_answer):
                            st.table(parsed_answer)
                        else:
                            st.json(parsed_answer)
                    else:
                        st.markdown(make_links_clickable(answer))
                except json.JSONDecodeError:
                    st.markdown(make_links_clickable(answer))

                logger.info(f"Question processed: {query}")
            except requests.exceptions.RequestException as e:
                st.error(f"API request failed. Details: {e}")
                logger.error(f"API request failed: {e}")

if st.session_state.history:
    st.sidebar.header("Query History")
    for q, a in reversed(st.session_state.history[-10:]):
        st.sidebar.markdown(f"**Q:** {q}")
        st.sidebar.markdown(f"**A:**")
        if len(a) > 300:
            st.sidebar.markdown(a[:300] + "…")
        else:
            st.sidebar.markdown(a)
        st.sidebar.markdown("---")
