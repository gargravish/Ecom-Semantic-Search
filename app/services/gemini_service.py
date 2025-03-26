import os
import google.generativeai as genai
from PIL import Image
import base64
import io
import json

class GeminiService:
    def __init__(self, api_key):
        self.api_key = api_key
        genai.configure(api_key=api_key)
        # Use Gemini-2.0-Flash
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        self.approved_apparels = ['t-shirt', 'shirt', 'sweatshirt', 'hoodie', 'sweater', 'jacket', 'shoes', 'shorts', 'jeans']

    def analyze_image(self, image_data):
        try:
            print("Starting image analysis with Gemini-2.0-Flash...")
            
            # Validate image data
            if not image_data:
                raise ValueError("Image data is empty")
            
            print("Processing image data...")
            # Remove data URL prefix if present
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            image_bytes = base64.b64decode(image_data)
            
            # Process image with PIL
            try:
                pil_image = Image.open(io.BytesIO(image_bytes))
                # Convert RGBA to RGB if needed
                if pil_image.mode == 'RGBA':
                    pil_image = pil_image.convert('RGB')
                
                # Resize if too large
                max_size = 1024
                if max(pil_image.size) > max_size:
                    ratio = max_size / max(pil_image.size)
                    new_size = tuple(int(dim * ratio) for dim in pil_image.size)
                    pil_image = pil_image.resize(new_size, Image.Resampling.LANCZOS)
            except Exception as e:
                print(f"PIL processing error: {str(e)}")
                raise ValueError(f"Failed to process image: {str(e)}")
            
            # Convert PIL image back to bytes for Gemini
            buffered = io.BytesIO()
            pil_image.save(buffered, format="JPEG")
            image_bytes = buffered.getvalue()
            
            # Prepare the prompt for Gemini
            prompt = """
            Look at this image carefully and analyze the clothing in detail:
            1. What is the main type of clothing shown? (e.g., t-shirt, shirt, sweatshirt, hoodie, sweater, jacket, shoes, shorts, jeans)
            2. What is the primary color of the clothing?
            3. Is the clothing for a man, woman, boy, or girl?
            4. Describe any patterns or designs (e.g., striped, checkered, floral, graphic)
            5. Note any distinctive features (e.g., collar type, sleeve length, buttons, zippers)
            6. Identify any visible logos or brands if present
            
            IMPORTANT: For any field where the information is not visible, not applicable, or unknown, simply leave it as an empty string ("") rather than writing phrases like "none", "none visible", "unknown", or "not applicable".
            
            Respond ONLY with a JSON object in this format:
            {
                "apparel_type": "type of clothing",
                "color": "primary color",
                "gender": "man/woman/boy/girl",
                "gender_confidence": "high/medium/low",
                "pattern": "description of any pattern or empty string if none/unknown",
                "features": "notable features like collar type, sleeve length, etc. or empty string if none/unknown",
                "brand": "visible brand or logo or empty string if none/unknown"
            }
            """
            
            print("Calling Gemini API...")
            try:
                response = self.model.generate_content(
                    contents=[
                        {
                            "parts": [
                                {"text": prompt},
                                {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(image_bytes).decode('utf-8')}}
                            ]
                        }
                    ],
                    generation_config={
                        "temperature": 0.2,  # Lower temperature for more consistent results
                        "top_p": 0.95,
                        "top_k": 40
                    },
                    safety_settings=[
                        {
                            "category": "HARM_CATEGORY_HARASSMENT",
                            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                        },
                        {
                            "category": "HARM_CATEGORY_HATE_SPEECH",
                            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                        },
                        {
                            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                        },
                        {
                            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                        }
                    ]
                )
                print(f"Received response from Gemini: {response.text}")
            except Exception as e:
                print(f"Gemini API call failed: {str(e)}")
                raise ValueError(f"Gemini API call failed: {str(e)}")
            
            # Process the response
            response_text = response.text.strip()
            print(f"Raw response text: {response_text}")
            
            # Extract JSON from the response
            json_match = None
            
            # Try different patterns to extract JSON
            if '```json' in response_text:
                json_match = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                json_match = response_text.split('```')[1].split('```')[0].strip()
            elif '{' in response_text and '}' in response_text:
                # Try to extract just the JSON object
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                json_match = response_text[start:end].strip()
            
            if not json_match:
                print("Failed to extract JSON from response")
                json_match = response_text  # Try with the whole text as fallback
            
            try:
                result = json.loads(json_match)
                print(f"Parsed result: {result}")
                
                # Normalize apparel type
                if 'apparel_type' in result:
                    result['apparel_type'] = result['apparel_type'].lower().strip()
                else:
                    result['apparel_type'] = 'unknown'
                    
                # Normalize gender
                if 'gender' in result:
                    result['gender'] = result['gender'].lower().strip()
                else:
                    result['gender'] = 'unknown'
                    
                # Normalize color
                if 'color' in result:
                    result['color'] = result['color'].lower().strip()
                else:
                    result['color'] = 'unknown'
                
                # Normalize pattern
                if 'pattern' in result:
                    result['pattern'] = result['pattern'].lower().strip()
                    if result['pattern'] in ['none', 'solid', 'n/a', 'none visible', 'not visible', 'not applicable']:
                        result['pattern'] = ''
                else:
                    result['pattern'] = ''
                
                # Normalize features
                if 'features' in result:
                    result['features'] = result['features'].lower().strip()
                    if result['features'] in ['none', 'n/a', 'none visible', 'not visible', 'not applicable']:
                        result['features'] = ''
                else:
                    result['features'] = ''
                
                # Normalize brand
                if 'brand' in result:
                    result['brand'] = result['brand'].lower().strip()
                    if result['brand'] in ['none', 'not visible', 'n/a', 'none visible', 'unknown', 'not applicable']:
                        result['brand'] = ''
                else:
                    result['brand'] = ''
                
                return result
                
            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {str(e)}, text: {json_match}")
                raise ValueError(f"Invalid JSON response from Gemini: {str(e)}")
            
        except Exception as e:
            print(f"Error in analyze_image: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return {
                'error': 'Failed to analyze image',
                'details': str(e)
            } 