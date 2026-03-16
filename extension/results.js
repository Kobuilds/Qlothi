// Qlothi Results Logic

document.addEventListener('DOMContentLoaded', () => {
    // 1. Parse URL Parameters
    const urlParams = new URLSearchParams(window.location.search);
    const itemName = urlParams.get('item') || 'Fashion Item';
    const sourceImg = urlParams.get('img') || '';

    // 2. Update UI with search context
    document.getElementById('item-query').textContent = itemName;
    if (sourceImg) {
        document.getElementById('source-image').src = decodeURIComponent(sourceImg);
    }

    // Set External Search Links
    document.getElementById('google-link').href = `https://www.google.com/search?tbm=shop&q=${encodeURIComponent(itemName)}`;
    document.getElementById('pinterest-link').href = `https://www.pinterest.com/search/pins/?q=${encodeURIComponent(itemName)}`;

    // 3. Mock Data Generation for Premium UX
    // In a real app, this would be an API call to a shopping engine
    const generateResults = (query) => {
        const categories = ['budget', 'style', 'luxury'];
        const results = [];
        
        // Generate 12 items
        for (let i = 1; i <= 12; i++) {
            const cat = categories[i % 3];
            const price = Math.floor(Math.random() * 4000 + 800); // INR pricing between 800 and 4800
            const rating = (Math.random() * 1.5 + 3.5).toFixed(1); // 3.5 to 5.0
            const reviewsCount = Math.floor(Math.random() * 500 + 10);
            
            results.push({
                id: i,
                name: `Similar ${query} - Option ${i}`,
                category: cat,
                price: price,
                rating: rating,
                reviews: reviewsCount,
                image: `https://picsum.photos/seed/${query}-${i}/400/600`, // Using seed for consistent "similar" looks
                store: cat === 'budget' ? 'Myntra' : cat === 'style' ? 'Zara' : 'H&M'
            });
        }
        return results;
    };

    const allItems = generateResults(itemName);
    const grid = document.getElementById('results-grid');

    const renderItems = (filter = 'all') => {
        grid.innerHTML = '';
        
        const filtered = filter === 'all' ? allItems : allItems.filter(item => item.category === filter);
        
        filtered.forEach((item, index) => {
            const card = document.createElement('div');
            card.className = 'product-card';
            
            // Create star rating HTML
            const fullStars = Math.floor(item.rating);
            let starsHtml = '';
            for(let j=0; j<5; j++) {
                if(j < fullStars) starsHtml += '★';
                else starsHtml += '☆';
            }
            
            card.innerHTML = `
                <div class="p-img-box">
                    <img src="${item.image}" alt="${item.name}">
                </div>
                <div class="p-info">
                    <div class="p-brand">${item.store}</div>
                    <h2 class="p-name">${item.name}</h2>
                    <div class="p-rating">
                        <span class="stars">${starsHtml}</span>
                        <span class="rating-val">${item.rating}</span>
                        <span class="reviews">(${item.reviews})</span>
                    </div>
                    <div class="p-price-row">
                        <span class="p-price">₹${item.price.toLocaleString('en-IN')}</span>
                        <a href="https://www.google.com/search?tbm=shop&q=${encodeURIComponent(item.name + ' ' + item.store)}" target="_blank" class="shop-now">Buy Now</a>
                    </div>
                </div>
            `;
            
            grid.appendChild(card);
            
            // Staggered reveal animation
            setTimeout(() => {
                card.classList.add('reveal');
            }, index * 100);
        });
    };

    // 4. Initial Render
    setTimeout(() => {
        renderItems();
    }, 1500); // Artificial delay to show loading state

    // 5. Filter Logic
    const filterBtns = document.querySelectorAll('.filter-btn');
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Update active state
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // Render filtered items
            renderItems(btn.dataset.filter);
        });
    });
});
