from flask import Blueprint, jsonify, request, current_app
from ..services.gemini_service import GeminiService
from ..services.vertex_ai_service import VertexAIService
from ..services.bigquery_service import BigQueryService
from google.cloud import bigquery
from google.cloud import aiplatform
from google.cloud.aiplatform_v1beta1 import (
    FeatureOnlineStoreAdminServiceClient,
    FeatureOnlineStoreServiceClient
)
from google.cloud.aiplatform_v1beta1.types import NearestNeighborQuery
from google.cloud.aiplatform_v1beta1.types import feature_online_store_service as feature_online_store_service_pb2
import vertexai
import vertexai.vision_models as vision_models
from vertexai.vision_models import MultiModalEmbeddingModel, Image
import re
import time
import base64
from io import BytesIO
from PIL import Image as PILImage

bp = Blueprint('api', __name__)

def get_gemini_service():
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in application config")
    return GeminiService(api_key=api_key)

def get_vertex_service():
    project_id = current_app.config.get('GOOGLE_CLOUD_PROJECT')
    location = current_app.config.get('VERTEX_AI_LOCATION')
    return VertexAIService(project_id, location)

def get_bigquery_service():
    project_id = current_app.config.get('GOOGLE_CLOUD_PROJECT')
    dataset = current_app.config.get('BIGQUERY_DATASET')
    return BigQueryService(project_id, dataset)

def get_image_embeddings(project_id, location, image_data=None, contextual_text=None):
    vertexai.init(project=project_id, location=location)
    model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding")

    if image_data:
        try:
            # Create a temporary file to store the image
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                temp_file.write(base64.b64decode(image_data))
                temp_file_path = temp_file.name

            # Load image from the temporary file
            image = vision_models.Image.load_from_file(temp_file_path)
            
            # Clean up the temporary file
            try:
                os.unlink(temp_file_path)
            except:
                pass
        except Exception as e:
            raise Exception(f"Failed to process image: {str(e)}")
    else:
        image = None

    embeddings = model.get_embeddings(
        image=image,
        contextual_text=contextual_text,
    )

    embedding_value = embeddings.image_embedding or embeddings.text_embedding
    embedding = [v for v in embedding_value]
    return embedding

def online_store_search(project_id, region, n_cnt, prompt=None, image_data=None):
    """ Initialize Google Cloud clients """
    GCS_IMAGE_BUCKET = "raves_us"
    BQ_DATASET_ID = "raves_us"
    BQ_TABLE_ID = "product_feature_store"
    BQ_TABLE_ID_FQN = "raves-altostrat.raves_us.product_feature_store"
    DATA_SOURCE = f"bq://{BQ_TABLE_ID_FQN}"
    
    # Initialize AI Platform clients
    aiplatform.init(project=project_id, location=region)
    FEATURE_ONLINE_STORE_ID = "products_online_feature_store"
    API_ENDPOINT = f"{region}-aiplatform.googleapis.com"
    admin_client = FeatureOnlineStoreAdminServiceClient(
        client_options={"api_endpoint": API_ENDPOINT}
    )
    FEATURE_VIEW_ID = "products_feature_view"
    DIMENSIONS = 1408
    EMBEDDING_COLUMN = "embedding"

    feature_online_store_instance = admin_client.get_feature_online_store(
        name=f"projects/{project_id}/locations/{region}/featureOnlineStores/{FEATURE_ONLINE_STORE_ID}"
    )

    PUBLIC_ENDPOINT = feature_online_store_instance.dedicated_serving_endpoint.public_endpoint_domain_name
    data_client = FeatureOnlineStoreServiceClient(client_options={"api_endpoint": PUBLIC_ENDPOINT})

    # Get embeddings using the same function as Product_Semantic_Search.py
    EMBEDDINGS = get_image_embeddings(
        project_id=project_id,
        location=region,
        image_data=image_data,
        contextual_text=prompt
    )

    output = data_client.search_nearest_entities(
        request=feature_online_store_service_pb2.SearchNearestEntitiesRequest(
            feature_view=f"projects/{project_id}/locations/{region}/featureOnlineStores/{FEATURE_ONLINE_STORE_ID}/featureViews/{FEATURE_VIEW_ID}",
            query=NearestNeighborQuery(
                embedding=NearestNeighborQuery.Embedding(value=EMBEDDINGS),
                neighbor_count=n_cnt,
            ),
            return_full_entity=True,
        )
    )

    gcs_uri_list = []
    productid_list = []
    for i in range(n_cnt):
        product_id = output.nearest_neighbors.neighbors[i].entity_key_values.key_values.features[8].value
        productid_list.append(str(product_id))
        gcs_uri = output.nearest_neighbors.neighbors[i].entity_key_values.key_values.features[9].value
        gcs_uri_list.append(str(gcs_uri))

    return gcs_uri_list, productid_list

def get_signed_urls(project_id, urls):
    bq_client = bigquery.Client(project=project_id)
    uris = [re.search(r'"(gs://[^"]+)"', item).group(1) for item in urls]
    uri_string = ", ".join([f"'{uri}'" for uri in uris])

    query = f"""
    SELECT signed_url
    FROM EXTERNAL_OBJECT_TRANSFORM(TABLE `raves-altostrat.raves_us.product_images`, ['SIGNED_URL'])
    WHERE uri IN ({uri_string})
    """

    query_job = bq_client.query(query)
    results = query_job.result()
    signed_url_list = [row.signed_url for row in results]
    return signed_url_list

def search_aisle_info(project_id, region, productid_list):
    bq_client = bigquery.Client()

    pattern = r'string_value: "([^"]+)"'
    product_list = [re.search(pattern, item).group(1) for item in productid_list]
    product_id_list = [int(file_name.split('.')[0]) for file_name in product_list]

    query = f"""
    SELECT productid, aisle
    FROM `raves-altostrat.raves_us.product_qty`
    WHERE productid IN ({','.join(map(str, product_id_list))})
    """

    query_job = bq_client.query(query)
    results = query_job.result()
    
    aisle_info = []
    for row in results:
        aisle_info.append({
            'productid': row.productid,
            'aisle': row.aisle
        })
    
    return aisle_info

@bp.route('/analyze-image', methods=['POST'])
def analyze_image():
    try:
        print("Starting /analyze-image endpoint...")
        data = request.get_json()
        
        if not data:
            print("No JSON data received")
            return jsonify({'error': 'No JSON data provided'}), 400
            
        if 'image_data' not in data:
            print("No image_data in request")
            return jsonify({'error': 'No image data provided'}), 400

        print("Getting Gemini service...")
        try:
            gemini_service = get_gemini_service()
        except Exception as e:
            print(f"Failed to initialize Gemini service: {str(e)}")
            return jsonify({
                'error': 'Service configuration error',
                'details': 'Failed to initialize image analysis service'
            }), 500
        
        print("Calling Gemini service analyze_image...")
        result = gemini_service.analyze_image(data['image_data'])
        print(f"Gemini service result: {result}")
        
        if 'error' in result:
            error_msg = f"Gemini analysis error: {result.get('details', 'Unknown error')}"
            print(error_msg)
            return jsonify(result), 500
            
        return jsonify(result)

    except Exception as e:
        import traceback
        error_msg = f"Error in analyze_image: {str(e)}\nTraceback: {traceback.format_exc()}"
        print(error_msg)
        return jsonify({
            'error': 'Failed to analyze image',
            'details': str(e)
        }), 500

@bp.route('/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No search data provided'}), 400
            
        query = data.get('query')
        image_data = data.get('image_data')
        neighbor_count = data.get('neighbor_count', 10)
        
        if not query and not image_data:
            return jsonify({'error': 'Either query or image_data must be provided'}), 400
            
        project_id = current_app.config.get('GOOGLE_CLOUD_PROJECT')
        if not project_id:
            return jsonify({'error': 'GOOGLE_CLOUD_PROJECT not configured'}), 500
            
        region = current_app.config.get('VERTEX_AI_LOCATION')
        if not region:
            return jsonify({'error': 'VERTEX_AI_LOCATION not configured'}), 500
        
        start_time = time.time()
        
        try:
            # Perform feature store search
            gcs_uri_list, productid_list = online_store_search(
                project_id=project_id,
                region=region,
                n_cnt=neighbor_count,
                prompt=query,
                image_data=image_data
            )
            
            # Get signed URLs for images
            try:
                signed_urls = get_signed_urls(project_id, gcs_uri_list)
            except Exception as e:
                current_app.logger.error(f"Failed to get signed URLs: {str(e)}")
                return jsonify({'error': 'Failed to get image URLs', 'details': str(e)}), 500
            
            # Get aisle information
            try:
                aisle_info = search_aisle_info(project_id, region, productid_list)
            except Exception as e:
                current_app.logger.error(f"Failed to get aisle info: {str(e)}")
                return jsonify({'error': 'Failed to get aisle information', 'details': str(e)}), 500
            
            # Combine results
            results = []
            for i, (product_id, signed_url) in enumerate(zip(productid_list, signed_urls)):
                product_info = next((info for info in aisle_info if str(info['productid']) == re.search(r'"([^"]+)"', product_id).group(1).split('.')[0]), None)
                results.append({
                    'id': re.search(r'"([^"]+)"', product_id).group(1).split('.')[0],
                    'image_url': signed_url,
                    'aisle': product_info['aisle'] if product_info else 'Unknown'
                })
            
            elapsed_time = time.time() - start_time
            
            return jsonify({
                'results': results,
                'elapsed_time': elapsed_time
            })
            
        except Exception as e:
            current_app.logger.error(f"Search operation failed: {str(e)}")
            return jsonify({
                'error': 'Search operation failed',
                'details': str(e)
            }), 500
        
    except Exception as e:
        current_app.logger.error(f"Error in search endpoint: {str(e)}")
        return jsonify({
            'error': 'Search failed',
            'details': str(e)
        }), 500

@bp.route('/analyze-webcam', methods=['POST'])
def analyze_webcam():
    try:
        data = request.get_json()
        if not data or 'image_data' not in data:
            return jsonify({'error': 'No image data provided'}), 400

        gemini_service = get_gemini_service()
        vertex_service = get_vertex_service()
        bigquery_service = get_bigquery_service()
        
        # First analyze with Gemini
        features = gemini_service.analyze_image(data['image_data'])
        if 'error' in features:
            return jsonify(features), 500
            
        # Then search with features
        image_embedding = vertex_service.get_image_embedding(data['image_data'])
        results = bigquery_service.search_products_with_filters(
            embedding=image_embedding,
            apparel_type=features.get('apparel_type'),
            color=features.get('color'),
            gender=features.get('gender')
        )
        
        return jsonify({
            'results': results,
            'features': features,
            'elapsed_time': 0.5
        })

    except Exception as e:
        import traceback
        print(f"Webcam analysis error: {str(e)}\nTraceback: {traceback.format_exc()}")
        return jsonify({
            'error': 'Failed to analyze webcam image',
            'details': str(e)
        }), 500

@bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}) 