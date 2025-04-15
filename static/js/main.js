// Main JavaScript for Biryani Management System

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Handle SOP Calculator
    setupSOPCalculator();

    // Handle refill status updates
    setupRefillStatusUpdates();

    // Handle SOP ingredient form
    setupSOPIngredientForm();

    // Setup sales calculation
    setupSalesCalculation();

    // Setup feedback action form
    setupFeedbackActionForm();
});

function setupSOPCalculator() {
    const calculator = document.getElementById('sop-calculator');
    if (!calculator) return;

    const sopSelect = document.getElementById('sop-select');
    const quantityInput = document.getElementById('quantity-input');
    const calculateBtn = document.getElementById('calculate-btn');
    const resultDiv = document.getElementById('calculation-result');

    if (calculateBtn) {
        calculateBtn.addEventListener('click', function() {
            const sopId = sopSelect.value;
            const quantity = parseFloat(quantityInput.value);

            if (!sopId || isNaN(quantity) || quantity <= 0) {
                resultDiv.innerHTML = '<div class="alert alert-danger">Please select a recipe and enter a valid quantity.</div>';
                return;
            }

            // Fetch the calculated ingredients
            fetch(`/api/calculate_sop/${sopId}/${quantity}`)
                .then(response => response.json())
                .then(data => {
                    let html = `
                        <div class="card mt-3">
                            <div class="card-header bg-primary text-white">
                                <h5 class="mb-0">${data.sop_name} (${data.requested_quantity} kg)</h5>
                            </div>
                            <div class="card-body">
                                <p>Original quantity: ${data.original_quantity} kg</p>
                                <p>Scale factor: ${data.scale_factor.toFixed(2)}</p>
                                
                                <table class="table table-striped">
                                    <thead>
                                        <tr>
                                            <th>Ingredient</th>
                                            <th>Original Quantity</th>
                                            <th>Needed Quantity</th>
                                            <th>Unit</th>
                                            <th>Note</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                    `;

                    data.ingredients.forEach(ingredient => {
                        html += `
                            <tr>
                                <td>${ingredient.name}</td>
                                <td>${ingredient.original_quantity}</td>
                                <td><strong>${ingredient.scaled_quantity.toFixed(2)}</strong></td>
                                <td>${ingredient.unit}</td>
                                <td>${ingredient.note || ''}</td>
                            </tr>
                        `;
                    });

                    html += `
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    `;

                    resultDiv.innerHTML = html;
                })
                .catch(error => {
                    console.error('Error calculating SOP:', error);
                    resultDiv.innerHTML = '<div class="alert alert-danger">An error occurred while calculating ingredients.</div>';
                });
        });
    }
}

function setupRefillStatusUpdates() {
    const refillStatusForms = document.querySelectorAll('.refill-status-form');
    refillStatusForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const refillId = this.querySelector('input[name="refill_id"]').value;
            const action = this.querySelector('input[name="action"]').value;
            
            // You could add confirmation for certain actions
            if (action === 'prepare') {
                if (!confirm('This will deduct ingredients from inventory based on SOP. Continue?')) {
                    e.preventDefault();
                }
            }
        });
    });
}

function setupSOPIngredientForm() {
    const sopIngredientForm = document.getElementById('sop-ingredient-form');
    if (!sopIngredientForm) return;

    const sopDisplay = document.getElementById('selected-sop');
    const sopIdInput = document.getElementById('sop-id-input');
    const sopSelects = document.querySelectorAll('.sop-select');

    sopSelects.forEach(select => {
        select.addEventListener('click', function() {
            const sopId = this.getAttribute('data-sop-id');
            const sopName = this.getAttribute('data-sop-name');
            
            sopIdInput.value = sopId;
            sopDisplay.textContent = sopName;
            
            // Show the form
            sopIngredientForm.classList.remove('d-none');
        });
    });
}

function setupSalesCalculation() {
    const salesForm = document.getElementById('sales-form');
    if (!salesForm) return;

    const recipeSelect = document.getElementById('recipe_id');
    const kgUnsoldInput = document.getElementById('kg_unsold');
    const cashCollectedInput = document.getElementById('cash_collected');
    
    const kgTakenDisplay = document.getElementById('kg-taken');
    const kgSoldDisplay = document.getElementById('kg-sold');
    const totalRevenueDisplay = document.getElementById('total-revenue');
    const upiCollectedDisplay = document.getElementById('upi-collected');
    const totalIncentiveDisplay = document.getElementById('total-incentive');

    // Function to update calculations
    function updateCalculations() {
        const recipeId = recipeSelect.value;
        if (!recipeId) return;

        // Find the recipe info from today's refills
        const recipeOption = recipeSelect.querySelector(`option[value="${recipeId}"]`);
        const recipeName = recipeOption ? recipeOption.textContent : 'Unknown';
        
        // Get the refill data from data attributes if available
        let kgTaken = 0;
        const refillData = document.querySelector(`.refill-data[data-recipe-id="${recipeId}"]`);
        if (refillData) {
            kgTaken = parseFloat(refillData.getAttribute('data-quantity')) || 0;
        }

        // Get user inputs
        const kgUnsold = parseFloat(kgUnsoldInput.value) || 0;
        const cashCollected = parseFloat(cashCollectedInput.value) || 0;

        // Calculate
        const kgSold = Math.max(0, kgTaken - kgUnsold);
        
        // Get selling price from data attribute if available
        let sellingPrice = 0;
        if (refillData) {
            sellingPrice = parseFloat(refillData.getAttribute('data-price')) || 0;
        }
        
        const totalRevenue = kgSold * sellingPrice;
        const upiCollected = Math.max(0, totalRevenue - cashCollected);
        
        // Get incentive from data attribute if available
        let incentivePerKg = 0;
        const incentiveData = document.querySelector('#incentive-data');
        if (incentiveData) {
            incentivePerKg = parseFloat(incentiveData.getAttribute('data-incentive')) || 0;
        }
        
        const totalIncentive = kgSold * incentivePerKg;

        // Update displays
        kgTakenDisplay.textContent = kgTaken.toFixed(2);
        kgSoldDisplay.textContent = kgSold.toFixed(2);
        totalRevenueDisplay.textContent = totalRevenue.toFixed(2);
        upiCollectedDisplay.textContent = upiCollected.toFixed(2);
        totalIncentiveDisplay.textContent = totalIncentive.toFixed(2);
    }

    // Add event listeners
    if (recipeSelect) recipeSelect.addEventListener('change', updateCalculations);
    if (kgUnsoldInput) kgUnsoldInput.addEventListener('input', updateCalculations);
    if (cashCollectedInput) cashCollectedInput.addEventListener('input', updateCalculations);

    // Initial calculation
    if (recipeSelect) updateCalculations();
}

function setupFeedbackActionForm() {
    const actionButtons = document.querySelectorAll('.feedback-action-btn');
    const actionForm = document.getElementById('feedback-action-form');
    const feedbackIdInput = document.getElementById('feedback_id');
    const feedbackDetailsDisplay = document.getElementById('feedback-details');

    if (!actionButtons || !actionForm) return;

    actionButtons.forEach(button => {
        button.addEventListener('click', function() {
            const feedbackId = this.getAttribute('data-feedback-id');
            const details = this.getAttribute('data-feedback-details');
            
            feedbackIdInput.value = feedbackId;
            feedbackDetailsDisplay.textContent = details;
            
            // Show the modal
            const modal = new bootstrap.Modal(document.getElementById('feedbackActionModal'));
            modal.show();
        });
    });
}
