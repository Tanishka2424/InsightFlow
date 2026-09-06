import os
import numpy as np
import pandas as pd
import snowflake.connector
from google import genai
from dotenv import load_dotenv

load_dotenv()

EMBEDDING_MODEL = "gemini-embedding-001"
NEW_REVIEWS = 50

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def read_reviews_from_snowflake():
    conn = snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
    )

    query = f"""
        SELECT REVIEW_ID, CITY, RATING, COMMENT
        FROM ZOMATO.STAGING.STG_REVIEWS
        SAMPLE ({NEW_REVIEWS} ROWS)
    """

    df = conn.cursor().execute(query).fetch_pandas_all()
    conn.close()

    df.columns = [col.lower() for col in df.columns]

    return df


def embed(texts):
    if isinstance(texts, str):
        texts = [texts]

    all_embeddings = []

    for i in range(0, len(texts), 100):
        batch = texts[i:i + 100]

        print(f"Embedding reviews {i + 1} to {min(i + 100, len(texts))}...")

        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=batch
        )

        all_embeddings.extend(
            [embedding.values for embedding in response.embeddings]
        )

    return np.array(all_embeddings, dtype=np.float32)


print("Loading reviews from Snowflake...")

df = read_reviews_from_snowflake()

print(f"Loaded {len(df)} reviews.")

embeddings = embed(df["comment"].tolist())

os.makedirs("../data", exist_ok=True)

df.to_csv("../data/reviews.csv", index=False)

np.save("../data/embeddings.npy", embeddings)

print("Done!")
print(f"Reviews saved: {len(df)}")
print(f"Embeddings saved: {len(embeddings)}")