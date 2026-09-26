document.addEventListener('DOMContentLoaded', () => {
    // Dynamic Row Adder for Operations (Receipts, Deliveries, Transfers)
    const addLineBtn = document.getElementById('btn-add-line');
    const linesContainer = document.getElementById('operation-lines-container');

    if (addLineBtn && linesContainer) {
        addLineBtn.addEventListener('click', () => {
            const firstRow = linesContainer.querySelector('.operation-line-row');
            if (firstRow) {
                const newRow = firstRow.cloneNode(true);
                // Reset inputs in new row
                newRow.querySelectorAll('input').forEach(input => input.value = '');
                newRow.querySelectorAll('select').forEach(select => select.selectedIndex = 0);
                
                // Show remove button
                const removeBtn = newRow.querySelector('.btn-remove-line');
                if (removeBtn) {
                    removeBtn.style.display = 'inline-block';
                    removeBtn.addEventListener('click', (e) => {
                        newRow.remove();
                    });
                }
                linesContainer.appendChild(newRow);
            }
        });

        // Setup existing remove buttons
        linesContainer.querySelectorAll('.btn-remove-line').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const rows = linesContainer.querySelectorAll('.operation-line-row');
                if (rows.length > 1) {
                    btn.closest('.operation-line-row').remove();
                } else {
                    alert('You must have at least one product line.');
                }
            });
        });
    }

    // Auto-fetch System Stock Quantity in Inventory Adjustment Form
    const adjLocationSelect = document.getElementById('adj_location_id');
    const adjProductSelect = document.getElementById('adj_product_id');
    const adjSystemQtyInput = document.getElementById('adj_system_qty');
    const adjCountedQtyInput = document.getElementById('adj_counted_qty');
    const adjDiffDisplay = document.getElementById('adj_difference_display');

    function updateAdjustmentDifference() {
        if (adjSystemQtyInput && adjCountedQtyInput && adjDiffDisplay) {
            const sys = parseFloat(adjSystemQtyInput.value) || 0;
            const counted = parseFloat(adjCountedQtyInput.value);
            if (!isNaN(counted)) {
                const diff = (counted - sys).toFixed(2);
                adjDiffDisplay.textContent = (diff > 0 ? `+${diff}` : `${diff}`);
                adjDiffDisplay.className = diff >= 0 ? 'badge bg-success' : 'badge bg-danger';
            } else {
                adjDiffDisplay.textContent = '0';
                adjDiffDisplay.className = 'badge bg-secondary';
            }
        }
    }

    function fetchSystemQty() {
        if (adjLocationSelect && adjProductSelect && adjSystemQtyInput) {
            const locId = adjLocationSelect.value;
            const prodId = adjProductSelect.value;

            if (locId && prodId) {
                fetch(`/adjustments/api/get-system-qty?location_id=${locId}&product_id=${prodId}`)
                    .then(res => res.json())
                    .then(data => {
                        adjSystemQtyInput.value = data.system_qty;
                        updateAdjustmentDifference();
                    })
                    .catch(err => console.error("Error fetching system quantity:", err));
            }
        }
    }

    if (adjLocationSelect && adjProductSelect) {
        adjLocationSelect.addEventListener('change', fetchSystemQty);
        adjProductSelect.addEventListener('change', fetchSystemQty);
    }

    if (adjCountedQtyInput) {
        adjCountedQtyInput.addEventListener('input', updateAdjustmentDifference);
    }
});
