// --- Modal Handling ---

function openSmartBookingModal(btn) {
    // 1. Get data from data-attributes
    const id = btn.getAttribute('data-id');
    const name = btn.getAttribute('data-name');
    const price = btn.getAttribute('data-price');
    const imgUrl = btn.getAttribute('data-image');

    // ... Rest of your existing logic ...
    
    // UI Setup
    const modal = document.getElementById('smartModal');
    modal.style.display = 'flex';
    
    document.getElementById('modalTitle').innerText = name;
    document.getElementById('modalPrice').innerText = price;
    document.getElementById('modalImg').src = imgUrl;
    document.getElementById('formEqId').value = id;
    
    // ... (Keep the rest of your fetch/logic the same)
}

function closeBookingModal() {
    document.getElementById('bookingModal').style.display = 'none';
}

function openAddModal() {
    const modal = document.getElementById('addModal');
    if(modal) modal.style.display = 'flex';
}

function closeAddModal() {
    const modal = document.getElementById('addModal');
    if(modal) modal.style.display = 'none';
}

// Close modals when clicking outside
window.onclick = function(event) {
    const bModal = document.getElementById('bookingModal');
    const aModal = document.getElementById('addModal');
    if (event.target == bModal) bModal.style.display = "none";
    if (event.target == aModal) aModal.style.display = "none";
}

// --- Price Calculation ---

function calculateTotal() {
    const startInput = document.getElementById('startDate').value;
    const endInput = document.getElementById('endDate').value;
    const pricePerDay = parseFloat(document.getElementById('modalPricePerDay').value);
    const display = document.getElementById('totalPriceDisplay');

    if (startInput && endInput) {
        const start = new Date(startInput);
        const end = new Date(endInput);

        // Calculate difference in time
        const diffTime = end - start;
        // Calculate difference in days (min 1 day)
        let diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        
        if (diffDays <= 0) diffDays = 1; // Minimum charge logic
        
        if(end >= start) {
            const total = (diffDays * pricePerDay).toFixed(2);
            display.innerText = `$${total}`;
        } else {
            display.innerText = "Invalid Dates";
        }
    }
}

// --- Frontend Search Filter ---

function filterEquipment() {

    const input = document.getElementById('searchInput').value.toLowerCase();
    const category = document.getElementById('categoryFilter').value.toLowerCase();
    const location = document.getElementById('locationFilter').value.toLowerCase();

    let visibleCount = 0;

    document.querySelectorAll('.equipment-card').forEach(item => {

        const name = item.getAttribute('data-name');
        const cat = item.getAttribute('data-category').toLowerCase();
        const loc = item.getAttribute('data-location');

        const matchName = name.includes(input);
        const matchCategory = (category === 'all' || cat === category);
        const matchLocation = (location === 'all' || loc === location);

        if (matchName && matchCategory && matchLocation) {
            item.style.display = "flex";
            visibleCount++;
        } else {
            item.style.display = "none";
        }
    });

    document.getElementById('noResults').style.display =
        visibleCount === 0 ? 'block' : 'none';
}
// Auto-hide Flash Messages after 4 seconds
document.addEventListener("DOMContentLoaded", function() {
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            alert.style.opacity = '0';
            setTimeout(() => alert.style.display = 'none', 500);
        });
    }, 4000);
});