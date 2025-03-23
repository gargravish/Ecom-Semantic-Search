document.addEventListener('DOMContentLoaded', () => {
    // Basic search elements
    const textQuery = document.getElementById('textQuery');
    const searchBtn = document.getElementById('searchBtn');
    const fileInput = document.getElementById('fileInput');
    const imagePreview = document.getElementById('imagePreview');
    const dropZone = document.getElementById('dropZone');
    const results = document.getElementById('results');

    // Modal elements
    const modal = document.getElementById('productModal');
    const modalImage = document.getElementById('modalImage');
    const modalTitle = document.getElementById('modalTitle');
    const modalAisle = document.getElementById('modalAisle');
    const modalPrice = document.getElementById('modalPrice');
    const closeModalBtn = document.getElementById('closeModalBtn');

    // Loading elements
    const loadingSpinner = document.getElementById('loadingSpinner');
    const errorMessage = document.getElementById('errorMessage');

    // Event Listeners
    if (searchBtn && textQuery) {
        searchBtn.addEventListener('click', () => {
            const query = textQuery.value.trim();
            if (query) performTextSearch(query);
        });

        // Add enter key handler for text search
        textQuery.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const query = textQuery.value.trim();
                if (query) performTextSearch(query);
            }
        });
    }

    fileInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (file) handleImageFile(file);
    });

    dropZone.addEventListener('dragover', handleDragOver);
    dropZone.addEventListener('dragleave', handleDragLeave);
    dropZone.addEventListener('drop', handleDrop);

    // Initialize upload functionality
    if (dropZone && fileInput) {
        dropZone.addEventListener('click', () => fileInput.click());

        fileInput.addEventListener('change', (event) => {
            const file = event.target.files[0];
            if (file) handleImageFile(file);
        });

        // Drag and drop handlers
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        dropZone.addEventListener('dragenter', () => dropZone.classList.add('dragover'));
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
        dropZone.addEventListener('drop', (e) => {
            dropZone.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) {
                handleImageFile(file);
            }
        });
    }

    // Search functions
    async function performTextSearch(query) {
        try {
            showLoading();
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    query: query,
                    image_data: null
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || errorData.details || 'Search failed');
            }

            const data = await response.json();
            displayResults(data.results);
            
            // Update search time
            if (data.elapsed_time) {
                const searchTimeElement = document.createElement('div');
                searchTimeElement.textContent = `Search completed in ${data.elapsed_time.toFixed(2)} seconds`;
                searchTimeElement.classList.add('text-sm', 'text-gray-500', 'mt-2', 'mb-4');
                document.querySelector('#results').insertBefore(searchTimeElement, document.querySelector('#results-grid'));
            }

        } catch (error) {
            console.error('Search error:', error);
            showError(error.message);
        } finally {
            hideLoading();
        }
    }

    async function performImageSearch(imageData) {
        if (!results) {
            console.error('Results container not found');
            return;
        }
        
        showLoading();

        try {
            // Extract base64 data from the data URL
            const base64Data = imageData.split(',')[1];
            
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({
                    query: null,
                    image_data: base64Data,
                    neighbor_count: 10
                })
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ error: 'Unknown error occurred' }));
                throw new Error(errorData.error || errorData.details || `Search failed: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (!data.results) {
                throw new Error('No results returned from search');
            }
            
            displayResults(data.results);
            
            // Update search time
            if (data.elapsed_time) {
                const searchTimeElement = document.createElement('div');
                searchTimeElement.textContent = `Search completed in ${data.elapsed_time.toFixed(2)} seconds`;
                searchTimeElement.classList.add('text-sm', 'text-gray-500', 'mt-2', 'mb-4');
                const resultsGrid = document.querySelector('#results-grid');
                if (resultsGrid) {
                    resultsGrid.parentElement.insertBefore(searchTimeElement, resultsGrid);
                }
            }
            
        } catch (error) {
            console.error('Search error:', error);
            showError(error.message || 'Failed to perform image search');
        } finally {
            hideLoading();
        }
    }

    // Results display function
    function generateRandomPrice() {
        const price = (Math.random() * (49.99 - 15.99) + 15.99).toFixed(2);
        return `£${price}`;
    }

    function displayResults(results) {
        const resultsGrid = document.querySelector('#results-grid');
        resultsGrid.innerHTML = ''; // Clear existing results

        if (!results || results.length === 0) {
            const noResults = document.createElement('div');
            noResults.textContent = 'No results found';
            noResults.classList.add('col-span-full', 'text-center', 'py-4');
            resultsGrid.appendChild(noResults);
            return;
        }

        results.forEach(result => {
            const card = document.createElement('div');
            card.classList.add('bg-white', 'rounded-lg', 'shadow', 'overflow-hidden');
            
            // Generate a random price between £10 and £100
            const price = (Math.random() * 90 + 10).toFixed(2);
            
            card.innerHTML = `
                <div class="aspect-w-1 aspect-h-1">
                    <img src="${result.image_url}" alt="Product ${result.id}" 
                         class="w-full h-full object-cover"
                         onerror="this.src='/static/images/no-image.png'">
                </div>
                <div class="p-4">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="text-sm text-gray-500">ID: ${result.id}</p>
                            <p class="text-sm text-blue-600">Aisle: ${result.aisle}</p>
                        </div>
                        <p class="text-lg font-bold text-green-600">£${price}</p>
                    </div>
                </div>
            `;
            
            resultsGrid.appendChild(card);
        });
    }

    function showLoading() {
        const spinner = document.getElementById('loadingSpinner');
        if (spinner) {
            spinner.classList.remove('hidden');
        }
    }

    function hideLoading() {
        const spinner = document.getElementById('loadingSpinner');
        if (spinner) {
            spinner.classList.add('hidden');
        }
    }

    function showError(message) {
        const errorDiv = document.getElementById('error-message');
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.classList.remove('hidden');
            setTimeout(() => {
                errorDiv.classList.add('hidden');
            }, 5000);
        } else {
            console.error('Error:', message);
        }
    }

    // Modal functions
    function showProductDetails(product) {
        if (!product || !modal) return;
        
        modalImage.src = product.product_image_url || '/static/images/placeholder.png';
        modalImage.onerror = () => modalImage.src = '/static/images/placeholder.png';
        modalTitle.textContent = `Product ${product.product_id}`;
        modalAisle.textContent = `Aisle: ${product.aisle_location}`;
        modalPrice.textContent = product.price;
        
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
    }

    // Modal event listeners
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            closeModal();
        });
    }

    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal?.classList.contains('active')) {
            closeModal();
        }
    });

    function handleDragOver(event) {
        event.preventDefault();
        dropZone.classList.add('dragover');
    }

    function handleDragLeave(event) {
        event.preventDefault();
        dropZone.classList.remove('dragover');
    }

    async function handleDrop(event) {
        event.preventDefault();
        dropZone.classList.remove('dragover');
        
        const file = event.dataTransfer.files[0];
        if (file && file.type.startsWith('image/')) {
            await handleImageFile(file);
        }
    }

    // Handle image file upload
    function handleImageFile(file) {
        if (!file.type.startsWith('image/')) {
            showError('Please upload an image file');
            return;
        }

        const reader = new FileReader();
        reader.onload = async (e) => {
            try {
                // Set image preview
                const img = imagePreview.querySelector('img');
                if (!img) {
                    const newImg = document.createElement('img');
                    newImg.classList.add('w-full', 'h-full', 'object-contain');
                    imagePreview.innerHTML = '';
                    imagePreview.appendChild(newImg);
                }
                const previewImg = imagePreview.querySelector('img');
                previewImg.src = e.target.result;
                imagePreview.classList.remove('hidden');

                // Perform search
                await performImageSearch(e.target.result);
            } catch (error) {
                console.error('Error handling image:', error);
                showError('Failed to process image');
            }
        };
        reader.onerror = () => {
            showError('Error reading the image file');
        };
        reader.readAsDataURL(file);
    }
}); 