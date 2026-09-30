# InsightFlow

### Modular Data Analytics Pipeline with AI-Powered Insights

InsightFlow is an data analytics project that combines cloud storage, data warehousing, dbt transformations and AI-powered analysis.

The project uses a Zomato dataset and takes the data through:

**S3 → Snowflake → dbt → Analytics → AI**

The AI layer adds three capabilities on top of the processed data:

- LLM-based review enrichment
- Retrieval-Augmented Generation (RAG)
- Natural Language to SQL

The project started from an end-to-end data engineering tutorial and was used as a hands-on implementation and learning project. I worked through the infrastructure, dbt models, Docker environment, AI components and integration, while adapting the project around my own setup.

---
