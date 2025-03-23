import vertexai
import vertexai.vision_models as vision_models
from vertexai.vision_models import (
    MultiModalEmbeddingModel,
    Image,
    MultiModalEmbeddingResponse,
)
from google.cloud.aiplatform_v1beta1 import (
    FeatureOnlineStoreAdminServiceClient,
    FeatureOnlineStoreServiceClient
)
from google.cloud.aiplatform_v1beta1.types import (
    NearestNeighborQuery,
    feature_online_store_service as feature_online_store_service_pb2
)
import base64
import io
from PIL import Image as PILImage
import tempfile
import os
import re
from vertexai.language_models import TextEmbeddingModel
from io import BytesIO
from google.cloud import aiplatform

class VertexAIService:
    def __init__(self, project_id, location):
        self.project_id = project_id
        self.location = location
        vertexai.init(project=project_id, location=location)
        self.model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding")
        self.text_model = TextEmbeddingModel.from_pretrained("textembedding-gecko@001")

    def _base64_to_image(self, base64_string):
        """Convert base64 string to PIL Image"""
        image_data = base64.b64decode(base64_string)
        image = PILImage.open(io.BytesIO(image_data))
        return image

    def _save_temp_image(self, image):
        """Save PIL Image to temporary file and return path"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            image.save(temp_file.name)
            return temp_file.name

    def get_text_embedding(self, text):
        """Get embeddings for text input."""
        try:
            embeddings = self.text_model.get_embeddings([text])
            if embeddings and embeddings[0].values:
                return embeddings[0].values
            raise ValueError("No embedding values returned from the model")
        except Exception as e:
            print(f"Error getting text embedding: {str(e)}")
            raise

    def get_image_embeddings(self, image_data=None, contextual_text=None):
        if image_data:
            # Convert base64 to PIL Image
            image_bytes = BytesIO(base64.b64decode(image_data))
            pil_image = PILImage.open(image_bytes)
            
            # Save to temporary file
            temp_bytes = BytesIO()
            pil_image.save(temp_bytes, format='PNG')
            temp_bytes.seek(0)
            
            # Create Vertex AI Image
            image = vision_models.Image(temp_bytes)
        else:
            image = None

        embeddings = self.model.get_embeddings(
            image=image,
            contextual_text=contextual_text,
        )

        embedding_value = embeddings.image_embedding or embeddings.text_embedding
        embedding = [v for v in embedding_value]
        return embedding

    def get_image_embedding(self, image_data):
        """Get embeddings for image input."""
        try:
            return self.get_image_embeddings(image_data=image_data)
        except Exception as e:
            print(f"Error getting image embedding: {str(e)}")
            raise

    def generate_embeddings(self, text_query=None, image_data=None):
        """Generate embeddings from text and/or image"""
        image = None
        if image_data:
            # Convert base64 to PIL Image
            pil_image = self._base64_to_image(image_data)
            # Save to temp file for Vertex AI
            temp_path = self._save_temp_image(pil_image)
            image = vision_models.Image.load_from_file(temp_path)
            # Clean up temp file
            os.unlink(temp_path)

        # Get embeddings
        embeddings = self.model.get_embeddings(
            image=image,
            contextual_text=text_query,
        )
        
        # Use image embedding if available, otherwise use text embedding
        embedding_value = embeddings.image_embedding or embeddings.text_embedding
        return [v for v in embedding_value]

    def search_feature_store(self, embedding, neighbor_count=5):
        """Search feature store for similar products"""
        request = feature_online_store_service_pb2.SearchNearestEntitiesRequest(
            feature_view=f"projects/{self.project_id}/locations/{self.location}/featureOnlineStores/{self.feature_store_id}/featureViews/{self.feature_view_id}",
            query=NearestNeighborQuery(
                embedding=NearestNeighborQuery.Embedding(value=embedding),
                neighbor_count=neighbor_count,
            ),
            return_full_entity=True,
        )
        
        response = self.data_client.search_nearest_entities(request=request)
        
        # Extract product IDs and GCS URIs
        results = []
        for i in range(neighbor_count):
            neighbor = response.nearest_neighbors.neighbors[i]
            
            # Extract product ID from the feature value
            product_id_str = str(neighbor.entity_key_values.key_values.features[8].value)
            # Extract the numeric part from the string (e.g., "9952" from 'string_value: "9952.jpg"\n')
            # Try different patterns to match the product ID
            match = None
            patterns = [
                r'"(\d+)"',  # Matches "1234"
                r'string_value: "(\d+)"',  # Matches string_value: "1234"
                r'(\d+)\.jpg',  # Matches 1234.jpg
                r'(\d+)'  # Matches any sequence of digits
            ]
            
            for pattern in patterns:
                match = re.search(pattern, product_id_str)
                if match:
                    break
            
            if not match:
                raise ValueError(f"Could not extract product ID from string: {product_id_str}")
            
            product_id = match.group(1)
            
            # Extract GCS URI
            gcs_uri = str(neighbor.entity_key_values.key_values.features[9].value)
            
            results.append({
                'product_id': product_id,
                'gcs_uri': gcs_uri
            })
            
        return results 