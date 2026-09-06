import os
import numpy as np
import pandas as pd
import streamlit as st
from google import genai
from dotenv import load_dotenv

load_dotenv()

EMBEDDING_MODEL = "gemini-embedding-001"
CHAT_MODEL = "gemini-3.6-flash"
TOP_K = 5

DATA_DIR = "../data"

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


@st.cache_data
def load_reviews():
    reviews_path = os.path.join(DATA_DIR, "reviews.csv")
    embeddings_path = os.path.join(DATA_DIR, "embeddings.npy")

    df = pd.read_csv(reviews_path)
    embeddings = np.load(embeddings_path)

    return df, embeddings


def embed(text):
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text
    )

    return np.array(
        response.embeddings[0].values,
        dtype=np.float32
    )


def find_similar_reviews(question, df, embeddings):
    question_vector = embed(question)

    # Normalize vectors
    question_norm = question_vector / np.linalg.norm(question_vector)

    embedding_norms = np.linalg.norm(
        embeddings,
        axis=1,
        keepdims=True
    )

    normalized_embeddings = embeddings / embedding_norms

    # Calculate similarity with every review
    scores = normalized_embeddings @ question_norm

    result = df.copy()
    result["score"] = scores

    return result.nlargest(TOP_K, "score")


def ask_llm(question, top_reviews):
    context = ""

    for _, row in top_reviews.iterrows():
        context += (
            f"({row['city']}, {row['rating']} stars) "
            f"{row['comment']}\n"
        )

    system_prompt = (
        "Answer only using the customer reviews provided. "
        "Be concise. "
        "If the reviews do not contain enough information to answer "
        "the question, say so."
    )

    user_prompt = f"""
Question:
{question}

Reviews:
{context}
"""

    response = client.models.generate_content(
        model=CHAT_MODEL,
        contents=f"{system_prompt}\n\n{user_prompt}"
    )

    return response.text


st.title("Chat with your Zomato Reviews")

st.caption(
    f"Searching local review embeddings • Top {TOP_K} reviews"
)


review_df, review_embeddings = load_reviews()


question = st.text_input(
    "Ask a question about your reviews:",
    placeholder="e.g. What are the most common complaints about delivery?"
)


if question:

    top_reviews = find_similar_reviews(
        question,
        review_df,
        review_embeddings
    )

    answer = ask_llm(
        question,
        top_reviews
    )

    st.markdown("**Answer:**")
    st.write(answer)

    with st.expander("Reviews used to build this answer"):

        st.dataframe(
            top_reviews[
                ["city", "rating", "comment"]
            ],
            hide_index=True
        )