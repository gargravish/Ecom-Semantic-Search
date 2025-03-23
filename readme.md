# Product Semantic Search Application

## Overview

This application provides a semantic search interface for products using a combination of text and image inputs. It leverages Google Cloud services, including Vertex AI for embedding generation and feature storage, BigQuery for data retrieval, and Streamlit for the user interface.

## Program Flow

1.  **User Input:** The user provides a text prompt and/or uploads an image through the Streamlit interface.
2.  **Embedding Generation:**
    * If text is provided, the application uses the Vertex AI MultiModal Embedding Model to generate a text embedding.
    * If an image is uploaded, the application uses the Vertex AI MultiModal Embedding Model to generate an image embedding.
    * If both are provided, the model generates combined embeddings.
3.  **Feature Store Search:** The application queries the Vertex AI Feature Online Store using the generated embedding to find the nearest neighbor products.
4.  **Data Retrieval:**
    * The application retrieves product image URIs and product IDs from the Feature Store response.
    * The application uses BigQuery to get the signed URLs for the product images.
    * The application uses BigQuery and Gemini to get the aisle information for the products.
5.  **Display Results:** The application displays the retrieved product images and aisle information using Streamlit.

## Project Plan

### Current Architecture

* **Frontend:** Streamlit
* **Backend:** Python
* **Embedding Model:** Vertex AI MultiModal Embedding Model
* **Feature Store:** Vertex AI Feature Online Store
* **Database:** BigQuery

### Dependencies

* `streamlit`
* `google-cloud-aiplatform`
* `google-cloud-bigquery`
* `Pillow`
* `requests`
* `vertexai`

(For a complete list, refer to `requirements.txt`) [cite: 1, 2]

### Future Refactoring Plan

See the "Refactoring to Flask Project Plan" below.