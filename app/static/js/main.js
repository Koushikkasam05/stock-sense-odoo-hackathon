/**
 * StockSense - Enterprise IT UI Interactions, Animation Engine & Workflow Enhancements
 */

(function () {
    'use strict';

    // --------------------------------------------------------------------------
    // 1. Toast Notification System
    // --------------------------------------------------------------------------
    window.StockSense = window.StockSense || {};

    window.StockSense.showToast = function (title, message, type = 'info') {
        const container = document.getElementById('stocksense-toast-container');
        if (!container) return;

        const iconMap = {
            success: 'bi-check-circle-fill text-success',
            danger: 'bi-exclamation-octagon-fill text-danger',
            warning: 'bi-exclamation-triangle-fill text-warning',
            info: 'bi-info-circle-fill text-info'
        };
        const icon = iconMap[type] || iconMap.info;

        const toastEl = document.createElement('div');
        toastEl.className = 'toast align-items-center bg-white border shadow-lg show mb-2';
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');
        toastEl.setAttribute('aria-atomic', 'true');
        toastEl.innerHTML = `
            <div class="d-flex p-3 align-items-center">
                <i class="bi ${icon} fs-4 me-3"></i>
                <div class="flex-grow-1">
                    <strong class="d-block text-dark">${title}</strong>
                    <span class="small text-muted">${message}</span>
                </div>
                <button type="button" class="btn-close ms-2" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;

        container.appendChild(toastEl);

        const bsToast = new bootstrap.Toast(toastEl, { delay: 4000 });
        bsToast.show();

        toastEl.addEventListener('hidden.bs.toast', () => {
            toastEl.remove();
        });
    };

    // --------------------------------------------------------------------------
    // 2. Click-to-Copy Helper for SKUs and References
    // --------------------------------------------------------------------------
    function initClickToCopy() {
        document.addEventListener('click', (e) => {
            const target = e.target.closest('.copyable-badge, .copyable, [data-copy]');
            if (!target) return;

            const textToCopy = target.getAttribute('data-copy') || target.textContent.trim();
            if (!textToCopy) return;

            navigator.clipboard.writeText(textToCopy).then(() => {
                window.StockSense.showToast('Copied to Clipboard', `"${textToCopy}" copied successfully!`, 'success');
                
                // Micro-pulse feedback
                target.style.transform = 'scale(1.12)';
                setTimeout(() => {
                    target.style.transform = '';
                }, 180);
            }).catch(() => {
                window.StockSense.showToast('Copy Failed', 'Unable to copy text to clipboard.', 'warning');
            });
        });
    }

    // --------------------------------------------------------------------------
    // 3. Staggered Animations & Enterprise KPI Number Counter
    // --------------------------------------------------------------------------
    function animateCounters() {
        const counters = document.querySelectorAll('.kpi-value, [data-count]');
        counters.forEach((counter) => {
            const targetText = counter.textContent.trim();
            const targetNum = parseFloat(targetText.replace(/[^0-9.-]/g, ''));
            
            if (isNaN(targetNum) || targetNum === 0) return;

            let start = 0;
            const duration = 750; // ms
            const startTime = performance.now();
            const isFloat = targetText.includes('.');

            function updateCounter(currentTime) {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);
                // Ease out quart
                const easeProgress = 1 - Math.pow(1 - progress, 4);
                const currentVal = start + (targetNum - start) * easeProgress;

                counter.textContent = isFloat ? currentVal.toFixed(1) : Math.floor(currentVal).toLocaleString();

                if (progress < 1) {
                    requestAnimationFrame(updateCounter);
                } else {
                    counter.textContent = targetText; // Ensure exact final value
                }
            }

            requestAnimationFrame(updateCounter);
        });
    }

    function initPageAnimations() {
        // Automatically stagger cards, table rows, and alert containers
        const cards = document.querySelectorAll('.kpi-card, .card-theme, .auth-card');
        cards.forEach((card, index) => {
            card.classList.add('animate-fade-up');
            card.style.animationDelay = `${Math.min(index * 0.04, 0.25)}s`;
        });

        const tableRows = document.querySelectorAll('.table-custom tbody tr');
        tableRows.forEach((row, index) => {
            row.style.animation = `fadeInUp 0.35s cubic-bezier(0.16, 1, 0.3, 1) ${Math.min(index * 0.03, 0.35)}s forwards`;
        });
    }

    // --------------------------------------------------------------------------
    // 4. Form Submission Loading States & Double-click Prevention
    // --------------------------------------------------------------------------
    function initFormEnhancements() {
        document.querySelectorAll('form').forEach((form) => {
            if (form.method.toLowerCase() === 'get') return;

            form.addEventListener('submit', function () {
                if (!form.checkValidity()) return;

                const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
                if (submitBtn && !submitBtn.disabled) {
                    const originalText = submitBtn.innerHTML || submitBtn.value;
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = `
                        <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                        <span>Processing...</span>
                    `;
                    setTimeout(() => {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = originalText;
                    }, 10000);
                }
            });
        });
    }

    // --------------------------------------------------------------------------
    // 5. Dynamic Operations Line Items (Receipts, Deliveries, Transfers)
    // --------------------------------------------------------------------------
    function initOperationLines() {
        const addLineBtn = document.getElementById('btn-add-line');
        const linesContainer = document.getElementById('operation-lines-container');

        if (addLineBtn && linesContainer) {
            addLineBtn.addEventListener('click', () => {
                const rows = linesContainer.querySelectorAll('.operation-line-row');
                const firstRow = rows[0];
                if (firstRow) {
                    const newRow = firstRow.cloneNode(true);
                    newRow.querySelectorAll('input').forEach(input => input.value = '');
                    newRow.querySelectorAll('select').forEach(select => select.selectedIndex = 0);

                    const removeBtn = newRow.querySelector('.btn-remove-line');
                    if (removeBtn) {
                        removeBtn.style.display = 'inline-flex';
                        removeBtn.addEventListener('click', () => removeRowWithAnimation(newRow));
                    }

                    newRow.classList.add('operation-line-row');
                    linesContainer.appendChild(newRow);

                    const firstSelect = newRow.querySelector('select');
                    if (firstSelect) firstSelect.focus();
                }
            });

            function removeRowWithAnimation(row) {
                const totalRows = linesContainer.querySelectorAll('.operation-line-row').length;
                if (totalRows <= 1) {
                    window.StockSense.showToast('Validation Warning', 'An operation must include at least one product line.', 'warning');
                    return;
                }

                row.classList.add('removing');
                setTimeout(() => {
                    row.remove();
                }, 220);
            }

            linesContainer.querySelectorAll('.btn-remove-line').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const row = btn.closest('.operation-line-row');
                    if (row) removeRowWithAnimation(row);
                });
            });
        }
    }

    // --------------------------------------------------------------------------
    // 6. Inventory Adjustment Real-time System Stock Fetcher
    // --------------------------------------------------------------------------
    function initAdjustmentCalculator() {
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
                    if (diff > 0) {
                        adjDiffDisplay.textContent = `+${diff} (Inventory Gain)`;
                        adjDiffDisplay.className = 'badge bg-success p-2 fs-6';
                    } else if (diff < 0) {
                        adjDiffDisplay.textContent = `${diff} (Inventory Loss)`;
                        adjDiffDisplay.className = 'badge bg-danger p-2 fs-6';
                    } else {
                        adjDiffDisplay.textContent = '0.00 (Balanced)';
                        adjDiffDisplay.className = 'badge bg-secondary p-2 fs-6';
                    }
                } else {
                    adjDiffDisplay.textContent = '0.00';
                    adjDiffDisplay.className = 'badge bg-secondary p-2 fs-6';
                }
            }
        }

        function fetchSystemQty() {
            if (adjLocationSelect && adjProductSelect && adjSystemQtyInput) {
                const locId = adjLocationSelect.value;
                const prodId = adjProductSelect.value;

                if (locId && prodId) {
                    adjSystemQtyInput.value = '...';
                    fetch(`/adjustments/api/get-system-qty?location_id=${locId}&product_id=${prodId}`)
                        .then(res => res.json())
                        .then(data => {
                            adjSystemQtyInput.value = data.system_qty;
                            updateAdjustmentDifference();
                        })
                        .catch(err => {
                            console.error("Error fetching system quantity:", err);
                            adjSystemQtyInput.value = '0.0';
                        });
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
    }

    // --------------------------------------------------------------------------
    // 7. Enterprise Command Palette (Ctrl + K)
    // --------------------------------------------------------------------------
    function initCommandPalette() {
        const modalEl = document.getElementById('commandPaletteModal');
        const inputEl = document.getElementById('command-palette-input');
        const resultsContainer = document.getElementById('command-palette-results');
        if (!modalEl || !inputEl || !resultsContainer) return;

        const commandModal = new bootstrap.Modal(modalEl);

        document.addEventListener('keydown', (e) => {
            // Ctrl+K or / opens command palette
            if ((e.ctrlKey && e.key === 'k') || (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA')) {
                e.preventDefault();
                commandModal.show();
                setTimeout(() => inputEl.focus(), 150);
            }
        });

        modalEl.addEventListener('shown.bs.modal', () => {
            inputEl.focus();
            inputEl.value = '';
            filterCommands('');
        });

        inputEl.addEventListener('input', () => {
            filterCommands(inputEl.value.toLowerCase().trim());
        });

        function filterCommands(term) {
            const items = resultsContainer.querySelectorAll('.command-item');
            items.forEach(item => {
                const text = item.textContent.toLowerCase();
                item.style.display = text.includes(term) ? 'flex' : 'none';
            });
        }
    }

    // --------------------------------------------------------------------------
    // 8. Back-to-Top Floating Button
    // --------------------------------------------------------------------------
    function initBackToTop() {
        const backBtn = document.getElementById('back-to-top-btn');
        if (!backBtn) return;

        window.addEventListener('scroll', () => {
            if (window.scrollY > 300) {
                backBtn.style.display = 'flex';
                requestAnimationFrame(() => {
                    backBtn.style.opacity = '1';
                });
            } else {
                backBtn.style.opacity = '0';
                setTimeout(() => {
                    if (window.scrollY <= 300) backBtn.style.display = 'none';
                }, 300);
            }
        });

        backBtn.addEventListener('click', () => {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    // --------------------------------------------------------------------------
    // 9. Chart.js Global Enterprise Theme
    // --------------------------------------------------------------------------
    function initChartTheme() {
        if (typeof Chart !== 'undefined') {
            Chart.defaults.font.family = "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif";
            Chart.defaults.color = '#64748b';
            Chart.defaults.plugins.tooltip.backgroundColor = '#0f172a';
            Chart.defaults.plugins.tooltip.titleColor = '#ffffff';
            Chart.defaults.plugins.tooltip.bodyColor = '#e2e8f0';
            Chart.defaults.plugins.tooltip.borderColor = 'rgba(255, 255, 255, 0.1)';
            Chart.defaults.plugins.tooltip.borderWidth = 1;
            Chart.defaults.plugins.tooltip.padding = 10;
            Chart.defaults.plugins.tooltip.cornerRadius = 8;
        }
    }

    // --------------------------------------------------------------------------
    // DOM Ready Initialization
    // --------------------------------------------------------------------------
    document.addEventListener('DOMContentLoaded', () => {
        initChartTheme();
        initPageAnimations();
        animateCounters();
        initClickToCopy();
        initFormEnhancements();
        initOperationLines();
        initAdjustmentCalculator();
        initCommandPalette();
        initBackToTop();
    });

})();
