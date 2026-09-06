import os
import json
import re

import pandas as pd
import streamlit as st
import snowflake.connector

from google import genai
from google.genai import types
from dotenv import load_dotenv


load_dotenv()

MODEL = "gemini-3.6-flash"

FORBIDDEN_WORDS = [
    "drop",
    "delete",
    "truncate",
    "alter",
    "update",
    "insert",
    "create",
    "replace",
    "grant",
    "revoke"
]

EXAMPLE_QUESTIONS = [
    "Top 10 cities by GMV",
    "Which cuisine has the most orders?",
    "Average delivery time by city, worst first",
    "Cancel rate by payment method"
]


# Gemini client
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


# Database schema given to Gemini
SCHEMA = """
Tables available (Snowflake). Use bare table names, no database or schema prefix.

FCT_ORDERS(
    order_id,
    order_date,
    customer_id,
    restaurant_id,
    city,
    cuisine,
    payment_method,
    order_status,
    is_delivered,
    sales_amount,
    discount,
    delivery_fee,
    gst,
    customer_rating,
    delivery_time_min
)

DIM_RESTAURANT(
    restaurant_id,
    restaurant_name,
    city,
    cuisine,
    rating,
    cost_for_two
)

DIM_CUSTOMER(
    customer_id,
    customer_name,
    age,
    age_segment,
    gender,
    city
)

MART_DAILY_CITY_REVENUE(
    order_date,
    city,
    orders,
    cancel_rate,
    gmv,
    aov
)

MART_RESTAURANT_PERFORMANCE(
    restaurant_id,
    restaurant_name,
    city,
    cuisine,
    orders,
    revenue,
    avg_customer_rating,
    cancel_rate
)

MART_DELIVERY_SLA(
    city,
    order_hour,
    delivered_orders,
    p50_delivery_min,
    late_rate
)

Note:
- gmv means delivered revenue.
- Prefer the MART_ tables when they fit the question.
"""


SYSTEM_PROMPT = f"""
You are a Snowflake SQL expert.

Write ONE SELECT query that answers the user's question.

Rules:
- SELECT queries only.
- Never modify data.
- Use bare table names.
- Do not use database or schema prefixes.
- Add a LIMIT of 100 or less, unless the question asks for a single total.
- Return the result as JSON in this exact format:
  {{"sql": "SELECT ..."}}

{SCHEMA}
"""


# Snowflake connection
@st.cache_resource
def get_connection():

    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema="MARTS",
        role="DBT_ROLE"
    )


# Generate SQL using Gemini
def generate_sql(question):

    try:

        response = client.models.generate_content(
            model=MODEL,
            contents=f"""
{SYSTEM_PROMPT}

User question:
{question}
""",
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json"
            )
        )

        answer = response.text.strip()

        # Remove markdown code fences if Gemini adds them
        answer = re.sub(
            r"```json\s*|\s*```",
            "",
            answer
        ).strip()

        # Convert JSON string to Python dictionary
        data = json.loads(answer)

        # Extract SQL
        sql = data.get("sql")

        if not sql:
            raise ValueError(
                "No SQL query was returned by Gemini."
            )

        return sql.strip()

    except json.JSONDecodeError:

        st.error(
            "Gemini returned an invalid JSON response."
        )

        return None

    except Exception as e:

        st.error(
            f"Error generating SQL: {e}"
        )

        return None


# Check SQL safety
def is_safe(sql):

    lowered = sql.lower().strip()

    # Only SELECT or WITH queries are allowed
    if not (
        lowered.startswith("select")
        or lowered.startswith("with")
    ):
        return False

    # Block dangerous SQL keywords
    for word in FORBIDDEN_WORDS:

        if word in lowered:
            return False

    return True


# Execute SQL in Snowflake
def run_query(sql):

    conn = get_connection()

    cursor = conn.cursor()

    try:

        df = cursor.execute(sql).fetch_pandas_all()

        return df

    finally:

        cursor.close()


# -----------------------------
# Streamlit UI
# -----------------------------

st.title("Chat with your Zomato Data")

st.caption(
    f"Ask in English, {MODEL} writes the SQL, "
    "Snowflake runs it"
)


# Sidebar
with st.sidebar:

    st.header("Example Questions")

    for q in EXAMPLE_QUESTIONS:

        st.markdown(f"- {q}")


# User question
question = st.text_input(
    "Enter your question here",
    placeholder=(
        "e.g. Top 10 restaurants by revenue in Bangalore"
    )
)


# Main execution
if question:

    sql = generate_sql(question)

    if sql:

        # Show generated SQL
        st.code(
            sql,
            language="sql"
        )

        # Safety check
        if not is_safe(sql):

            st.error(
                "The generated SQL is not safe to run. "
                "Please modify your question."
            )

        else:

            try:

                # Execute query
                df = run_query(sql)

                # Show result
                st.success(
                    f"{len(df)} rows returned"
                )

                st.dataframe(
                    df,
                    hide_index=True
                )

                # Show chart when appropriate
                if (
                    len(df.columns) == 2
                    and pd.api.types.is_numeric_dtype(
                        df.iloc[:, 1]
                    )
                ):

                    st.bar_chart(
                        df,
                        x=df.columns[0],
                        y=df.columns[1]
                    )

            except Exception as e:

                st.error(
                    f"Error running query: {e}"
                )