import os
import google.generativeai as genai
from PIL import Image
import base64
import io
import json

class GeminiService:
    def __init__(self, api_key):
        if not api_key:
            raise ValueError("Gemini API key is required")
        print(f"Initializing Gemini service with API key: {'*' * len(api_key)}")
        genai.configure(api_key=api_key)
        try:
            self.model = genai.GenerativeModel('gemini-pro-vision')
        except Exception as e:
            raise ValueError(f"Failed to initialize Gemini model: {str(e)}")
        self.approved_apparels = [
            't-shirt', 'tshirt', 't shirt', 'shirt', 'shoes', 'shorts', 'jeans',
            'sweatshirt', 'hoodie', 'sweater', 'jacket', 'pullover'
        ]
        self.gender_options = ['boy', 'girl', 'man', 'woman']

    def analyze_image(self, image_data):
        try:
            print("Starting image analysis...")
            
            # Validate image data
            if not image_data:
                raise ValueError("Image data is empty")
            
            print("Decoding base64 image...")
            try:
                # Remove data URL prefix if present
                if ',' in image_data:
                    image_data = image_data.split(',')[1]
                image_bytes = base64.b64decode(image_data)
            except Exception as e:
                print(f"Base64 decoding error: {str(e)}")
                raise ValueError(f"Invalid base64 image data: {str(e)}")

            print("Opening image with PIL...")
            try:
                image = Image.open(io.BytesIO(image_bytes))
                print(f"Image opened successfully. Size: {image.size}, Mode: {image.mode}")
                
                # Convert RGBA to RGB if needed
                if image.mode == 'RGBA':
                    image = image.convert('RGB')
                    print("Converted image from RGBA to RGB")
                
                # Ensure reasonable image size
                max_size = 1024
                if max(image.size) > max_size:
                    ratio = max_size / max(image.size)
                    new_size = tuple(int(dim * ratio) for dim in image.size)
                    image = image.resize(new_size, Image.Resampling.LANCZOS)
                    print(f"Resized image to {new_size}")
                
            except Exception as e:
                print(f"PIL image error: {str(e)}")
                raise ValueError(f"Failed to process image: {str(e)}")

            print("Preparing Gemini prompt...")
            prompt = """
            You are a fashion apparel analyzer. Look at this image carefully and identify:
            1. The main apparel item visible (focus on: t-shirt, shirt, sweatshirt, hoodie, sweater, jacket, shoes, shorts, or jeans)
            2. The primary color of the apparel
            3. The likely target gender category (boy, girl, man, woman)
            4. Your confidence in the gender prediction (high/medium/low)

            Important: The image shows a person wearing clothing. Focus on identifying the main visible garment.
            Be specific about the type of top - distinguish between t-shirts, shirts, sweatshirts, hoodies, and sweaters.

            Respond ONLY with a JSON object in this exact format:
            {
                "apparel_type": "string (one of: t-shirt, shirt, sweatshirt, hoodie, sweater, jacket, shoes, shorts, jeans)",
                "color": "string (primary color)",
                "gender": "string (one of: boy, girl, man, woman)",
                "gender_confidence": "string (high/medium/low)"
            }
            """

            print("Calling Gemini API...")
            try:
                response = self.model.generate_content([prompt, image])
                print(f"Raw Gemini response: {response.text}")
                
                if not response.text:
                    raise ValueError("Empty response from Gemini API")
                    
            except Exception as e:
                print(f"Gemini API error: {str(e)}")
                raise ValueError(f"Gemini API error: {str(e)}")
            
            # Extract the JSON from the response
            response_text = response.text
            print(f"Processing response text: {response_text}")
            
            # Remove any markdown formatting if present
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0]
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0]
            
            # Clean the response text
            response_text = response_text.strip()
            if not response_text:
                raise ValueError("Empty response text after cleaning")
            
            # Parse the JSON response
            try:
                result = json.loads(response_text)
                print(f"Parsed result: {result}")
            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {str(e)}")
                print(f"Failed to parse text: {response_text}")
                raise ValueError(f"Invalid JSON response from Gemini: {str(e)}")
            
            # Validate required fields
            required_fields = ['apparel_type', 'color', 'gender', 'gender_confidence']
            missing_fields = [field for field in required_fields if field not in result]
            if missing_fields:
                raise ValueError(f"Missing required fields in response: {missing_fields}")
            
            # Normalize apparel type
            apparel_type = result['apparel_type'].lower().strip()
            result['apparel_type'] = apparel_type
            print(f"Normalized apparel type: {apparel_type}")

            # Validate apparel type
            result['is_valid_apparel'] = any(
                apparel in result['apparel_type'].lower()
                for apparel in self.approved_apparels
            )
            print(f"Is valid apparel: {result['is_valid_apparel']}")

            # Normalize common variations
            if any(term in apparel_type for term in ['sweatshirt', 'hoodie', 'sweater', 'pullover']):
                result['apparel_type'] = 'sweatshirt'
                result['is_valid_apparel'] = True

            return result

        except Exception as e:
            print(f"Error in analyze_image: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return {
                'error': 'Failed to analyze image',
                'is_valid_apparel': False,
                'details': str(e)
            } 