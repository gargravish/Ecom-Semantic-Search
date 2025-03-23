import streamlit as st
from google.cloud import bigquery
from google.cloud import aiplatform
from google.cloud.aiplatform_v1beta1 import (FeatureOnlineStoreAdminServiceClient, FeatureOnlineStoreServiceClient)
from google.cloud.aiplatform_v1beta1.types import NearestNeighborQuery
from google.cloud.aiplatform_v1beta1.types import feature_online_store_service as feature_online_store_service_pb2
import tempfile
import os
import re
import requests
import time
from typing import Optional
import vertexai
import vertexai.vision_models as vision_models
from vertexai.vision_models import (
    MultiModalEmbeddingModel,
    Image,
    MultiModalEmbeddingResponse,
)
from vertexai.preview.generative_models import (
    Content,
    FunctionDeclaration,
    GenerativeModel,
    GenerationConfig,
    Part,
    Tool,
)
#from vertexai.preview.generative_models import ToolConfig
from PIL import Image

st.set_page_config(page_title='BQ Product Viewer', layout='wide')

def authenticate_gcp():
    """ Placeholder for GCP authentication; in production, ensure appropriate credentials are used """
    pass

def get_image_embeddings(
    project_id: str,
    location: str,
    IMAGE: str = None,
    contextual_text: Optional[str] = None,
  ) -> MultiModalEmbeddingResponse:

    vertexai.init(project=project_id, location=location)

    model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding")

    if IMAGE:
      image = vision_models.Image.load_from_file(IMAGE)
    else:
      image = None

    embeddings = model.get_embeddings(
        image=image,
        contextual_text=contextual_text,
    )

    #print(f"Image Embedding: {embeddings.image_embedding}")
    #print(f"Text Embedding: {embeddings.text_embedding}")
    embedding_value = embeddings.image_embedding or embeddings.text_embedding
    embedding = [v for v in embedding_value]
    return embedding

def online_store_search(PROJECT_ID, REGION,n_cnt,PROMPT,IMAGE):
    """ Initialize Google Cloud clients """
    GCS_IMAGE_BUCKET = "raves_us"
    BQ_DATASET_ID = "raves_us"
    BQ_TABLE_ID = "product_feature_store"
    BQ_TABLE_ID_FQN = "raves-altostrat.raves_us.product_feature_store"
    DATA_SOURCE = f"bq://{BQ_TABLE_ID_FQN}"
    # Initialize AI Platform clients
    aiplatform.init(project=PROJECT_ID, location=REGION)
    FEATURE_ONLINE_STORE_ID = "products_online_feature_store"
    API_ENDPOINT = f"{REGION}-aiplatform.googleapis.com"
    admin_client = FeatureOnlineStoreAdminServiceClient(
        client_options={"api_endpoint": API_ENDPOINT}
    )
    FEATURE_VIEW_ID = "products_feature_view"
    DIMENSIONS = 1408
    EMBEDDING_COLUMN = "embedding"

    feature_online_store_instance = admin_client.get_feature_online_store(
        name=f"projects/{PROJECT_ID}/locations/{REGION}/featureOnlineStores/{FEATURE_ONLINE_STORE_ID}"
    )

    PUBLIC_ENDPOINT = (
        feature_online_store_instance.dedicated_serving_endpoint.public_endpoint_domain_name
    )

    print(f"PUBLIC_ENDPOINT for online serving: {PUBLIC_ENDPOINT}")

    data_client = FeatureOnlineStoreServiceClient(client_options={"api_endpoint": PUBLIC_ENDPOINT})

    start = time.time()
    #TEXT_EMBEDDINGS = encode_to_embeddings(text=PROMPT)
    EMBEDDINGS = get_image_embeddings(
        project_id = PROJECT_ID,
        location = REGION,
        IMAGE = IMAGE,
        contextual_text = PROMPT
    )
    output = data_client.search_nearest_entities(
        request = feature_online_store_service_pb2.SearchNearestEntitiesRequest(
            feature_view=f"projects/{PROJECT_ID}/locations/{REGION}/featureOnlineStores/{FEATURE_ONLINE_STORE_ID}/featureViews/{FEATURE_VIEW_ID}",
            query=NearestNeighborQuery(
                embedding = NearestNeighborQuery.Embedding(value=EMBEDDINGS),
                neighbor_count=n_cnt,
            ),
            return_full_entity = True,
        )
    )
    end = time.time()
    print(type(output))
    gcs_uri_list = []
    productid_list = []
    for i in range(n_cnt):
        product_id = output.nearest_neighbors.neighbors[i].entity_key_values.key_values.features[8].value
        productid_list.append(str(product_id))
        gcs_uri = output.nearest_neighbors.neighbors[i].entity_key_values.key_values.features[9].value
        gcs_uri_list.append(str(gcs_uri))

    #print(productid_list)
    print(gcs_uri_list)
    elapsed_time = end - start
    print(f"Elapsed Time: {end-start}")
    return gcs_uri_list,productid_list,elapsed_time

def get_signed_urls(bq_client, urls):
    # Convert the list of URIs into a string for the IN clause
    uris = [re.search(r'"(gs://[^"]+)"', item).group(1) for item in urls]
    uri_string = ", ".join([f"'{uri}'" for uri in uris])  # Ensure single quotes around URIs
    print(uri_string)
    query = f"""
    SELECT signed_url
    FROM EXTERNAL_OBJECT_TRANSFORM(TABLE `raves-altostrat.raves_us.product_images`, ['SIGNED_URL'])
    WHERE uri IN ({uri_string})
    """

    query_job = bq_client.query(query)
    results = query_job.result()

    signed_url_list = [row.signed_url for row in results]
    return signed_url_list

def search_aisle_info(PROJECT_ID, REGION,productid_list):
    vertexai.init(project=PROJECT_ID, location=REGION)
    
    BQ_DATASET_ID = "raves_us"
    BQ_TABLE_ID = "product_qty"
    # Specify a function declaration and parameters for an API request

    get_table_func = FunctionDeclaration(
        name="get_table",
        description="Get information about a table, including the description, schema, and number of rows that will help answer the user's question. Always use the fully qualified dataset and table names.",
        parameters={
            "type": "object",
            "properties": {
                "table_id": {
                    "type": "string",
                    "description": "Fully qualified ID of the table to get information about",
                }
            },
            "required": [
                "table_id",
            ],
        },
    )

    sql_query_func = FunctionDeclaration(
        name="sql_query",
        description="Get information from data in BigQuery using SQL queries",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": f"SQL query on a single line that will help give quantitative answers to the user's question when run on a BigQuery dataset {BQ_DATASET_ID} and table {BQ_TABLE_ID}. In the SQL query, always use the fully qualified dataset and table names.",
                }
            },
            "required": [
                "query",
            ],
        },
    )

    sql_query_tool = Tool(
    function_declarations=[get_table_func,sql_query_func,],
    )

    model = GenerativeModel(
    "gemini-1.5-pro-preview-0514",
    generation_config=GenerationConfig(temperature=0),
    tools=[sql_query_tool]
    )
    chat = model.start_chat()
    client = bigquery.Client()

    pattern = r'string_value: "([^"]+)"'
    product_list = [re.search(pattern, item).group(1) for item in productid_list]
    product_id_list = [int(file_name.split('.')[0]) for file_name in product_list]
    print("\n\n\n\n")
    print(type(product_id_list))
    print(product_id_list)

    prompt = f"""
        Provide the value of aisle for the given productid where the information in your response is
        coming from in the database. Only use information that you learn
        from BigQuery, do not make up information.
        Here is the list of productid:
        {product_id_list}
        Always provide the output in JSON format like:
        ['productid':1234,'aisle':'TB090']
        """
    response = chat.send_message(prompt)
    response = response.candidates[0].content.parts[0]

    #print(response.candidates[0].function_calls)
    function_calling_in_process = True
    api_requests_and_responses = []
    while function_calling_in_process:
        try:
            params = {}
            for key,value in response.function_call.args.items():
                params[key]=value
            print(response.function_call.name)
            print(params)

            if response.function_call.name == "get_table":
                api_response = BQ_DATASET_ID
                api_requests_and_responses.append([response.function_call.name, params, api_response])
                api_response = BQ_TABLE_ID
                api_requests_and_responses.append([response.function_call.name, params, api_response])                
                api_response = client.get_table(params["table_id"])
                api_response = api_response.to_api_repr()
                api_requests_and_responses.append(
                    [
                        response.function_call.name,
                        params,
                        [
                            str(api_response.get("description", "")),
                            str(
                                [
                                    column["name"]
                                    for column in api_response["schema"]["fields"]
                                ]
                            ),
                        ],
                    ]
                )
                api_response = str(api_response)

            if response.function_call.name == "sql_query":
                job_config = bigquery.QueryJobConfig(
                            maximum_bytes_billed=100000000
                        )  # Data limit per query job
                try:
                    cleaned_query = (
                        params["query"]
                        .replace("\\n", " ")
                        .replace("\n", "")
                        .replace("\\", "")
                    )
                    query_job = client.query(cleaned_query, job_config=job_config)
                    api_response = query_job.result()
                    api_response = str([dict(row) for row in api_response])
                    api_response = api_response.replace("\\", "").replace("\n", "")
                    api_requests_and_responses.append(
                        [response.function_call.name, params, api_response]
                    )
                except Exception as e:
                    api_response = f"{str(e)}"
                    api_requests_and_responses.append(
                        [response.function_call.name, params, api_response]
                    )
            print(api_response)
            response = chat.send_message(
                Part.from_function_response(
                    name=response.function_call.name,
                    response={
                        "content": api_response,
                    },
                ),
            )
            response = response.candidates[0].content.parts[0]

        except AttributeError:
            function_calling_in_process = False
    print(response.text)
    response_content = response.text
    return response_content

def display_images(urls,aisle_list):
    """ Display images in Streamlit using the signed URLs as cards in two columns """
    # Create two columns
    col1, col2 = st.columns(2)
    pattern = re.compile(r"{'productid': (\d+), 'aisle': '(\w+)'}")
    matches = pattern.findall(aisle_list)
    for i, (url,match) in enumerate(zip(urls,matches)):
        product_id,aisle = match
        image_data = requests.get(url).content
        if i % 2 == 0:
            # Display image in the first column
            with col1:
                #st.markdown(f"Product ID: {product_id} is in Aisle: {aisle}")
                st.markdown(f"""<div style="background-color: #d9edf7; color: #31708f; padding: 10px; border-radius: 5px; font-size: 1.2em; font-weight: bold; border: 1px solid #bce8f1;">Product ID: {product_id} is in Aisle: {aisle}</div>""", unsafe_allow_html=True)
                st.image(image_data, use_column_width=True)
        else:
            # Display image in the second column
            with col2:
                #st.markdown(f"Product ID: {product_id} is in Aisle: {aisle}")
                st.markdown(f"""<div style="background-color: #d9edf7; color: #31708f; padding: 10px; border-radius: 5px; font-size: 1.2em; font-weight: bold; border: 1px solid #bce8f1;">Product ID: {product_id} is in Aisle: {aisle}</div>""", unsafe_allow_html=True)
                st.image(image_data, use_column_width=True)

def main():
    #st.title('Product Semantic Search')
    st.markdown("<h1 style='text-align: center;'>Product Semantic Search</h1>", unsafe_allow_html=True)
    project_id = "raves-altostrat"
    region = "us-central1"
    bq_client = bigquery.Client(project=project_id)
    #txt_prompt = st.text_input("Search",placeholder="A disney t-shirt for a boy which is blue in color.")
    image_path = None
    neighbor_count = st.number_input("Number of Neighbors", 1, 100, 5)
    st.write("\n\n")
    st.write("###### Upload Text and/or Image")
    col1, col2, col3 = st.columns([3, 1, 3])
    with col1:
        txt_prompt = st.text_input("Search",placeholder="A disney t-shirt for a boy which is blue in color.")
    with col2:
        st.write("<div style='text-align: center; font-size: 24px; font-weight: bold;'>OR</div>", unsafe_allow_html=True)
    with col3:
        uploaded_file = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg"])
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", use_column_width=True)
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as temp_file:
                temp_file.write(uploaded_file.getvalue())
                temp_file_path = temp_file.name
            fully_qualified_name = temp_file_path
            image_path = fully_qualified_name
            print(fully_qualified_name)
    st.markdown("""<style> .line {border: none;border-top: 5px solid #FFFF00;margin: 20px 0;width: 100%;}</style><hr class="line">""", unsafe_allow_html=True)
    st.markdown("""<style> .stButton > button {display: block;margin: auto;}</style>""", unsafe_allow_html=True)
    if st.button("Fetch and Display Images"):
        uri_list,productidlist,elapsed_time  = online_store_search(project_id, region,neighbor_count,txt_prompt,image_path)
        signed_list = get_signed_urls(bq_client, uri_list)
        aisle_list = search_aisle_info(project_id, region, productidlist)
        #print(signed_list)
        #print(aisle_list)
        st.write("###### Total Search Time:", elapsed_time, "seconds")
        display_images(signed_list,aisle_list)

if __name__ == "__main__":
    main()
