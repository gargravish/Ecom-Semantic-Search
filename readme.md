# Product Semantic Search Application

## Overview

This application provides a semantic search interface for products using a combination of text and image inputs. It leverages Google Cloud services, including Vertex AI for embedding generation and feature storage, BigQuery for data retrieval, and Flask for the backend with a modern HTML/JS frontend.

## Features

- **Text Search**: Search products using natural language descriptions
- **Image Search**: Upload images to find visually similar products
- **Drag & Drop**: Easy image upload with drag and drop support
- **Real-time Preview**: Instant preview of uploaded images
- **Clear Functionality**: Remove uploaded images with one click
- **Smart Webcam Search**: AI-powered image analysis using Gemini to generate detailed product descriptions
- **Responsive Design**: Works seamlessly on all devices
- **Loading States**: Visual feedback during search operations
- **Error Handling**: Clear error messages for better user experience
- **Product Details**: Modal view for detailed product information

## Program Flow

1. **User Input:**
   - Text search: User enters a text description
   - Image search: User uploads an image (drag & drop or click to upload)
   - Smart webcam search: User takes a photo, Gemini analyzes it and generates a detailed description
   - Combined search: Text and image/webcam can be used together

2. **Embedding Generation:**
   - Text: Uses Vertex AI MultiModal Embedding Model for text embeddings
   - Image: Uses Vertex AI MultiModal Embedding Model for image embeddings
   - Combined: Generates unified embeddings when both inputs are provided

3. **Feature Store Search:**
   - Queries Vertex AI Feature Online Store
   - Finds nearest neighbor products based on embeddings
   - Returns product IDs and image URIs

4. **Data Retrieval:**
   - Gets signed URLs for product images from BigQuery
   - Retrieves aisle information for products
   - Processes and formats results for display

5. **Display Results:**
   - Shows product images in a responsive grid
   - Displays product details including aisle information
   - Provides loading states and error feedback

## Technical Stack

- **Frontend:**
  - HTML5
  - Tailwind CSS for styling
  - Vanilla JavaScript for interactivity
  - Responsive design principles

- **Backend:**
  - Flask (Python)
  - RESTful API architecture
  - Blueprint-based routing
  - CORS support for development

- **Cloud Services:**
  - Vertex AI for embeddings
  - BigQuery for data storage
  - Feature Store for semantic search
  - Gemini for image analysis

## Setup and Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your Google Cloud credentials
   ```
4. Run the application:
   ```bash
   python run.py
   ```

## Development

- Follow the coding patterns in `coding-patterns.mdc`
- Use the technical stack specified in `tech-stack.mdc`
- Follow the workflow patterns in `workflow-patterns.mdc`

## Testing

- Run tests using Python's unittest framework
- Test both frontend and backend components
- Ensure proper error handling and edge cases

## Future Enhancements

See `project_plan.md` for detailed roadmap and future features.

## Changelog

See `CHANGELOG.md` for a detailed history of changes.

## Image Analysis (for webcam/images):
   - Uses Gemini-2.0-Flash AI to analyze image content
   - Generates detailed product descriptions
   - Extracts key features like color, style, and design elements
   - Identifies specific patterns (striped, checkered, floral, etc.)
   - Recognizes distinctive garment features (collar type, sleeve length, etc.)
   - Detects visible brands and logos when present
   - Converts visual information into comprehensive search queries