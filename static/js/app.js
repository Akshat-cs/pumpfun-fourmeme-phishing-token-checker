const checkButton = document.getElementById('checkButton');
const tokenAddressInput = document.getElementById('tokenAddress');
const bondingCurveInput = document.getElementById('bondingCurve');
const bondingCurveLabel = document.getElementById('bondingCurveLabel');
const resultSection = document.getElementById('resultSection');
const resultContent = document.getElementById('resultContent');
const cancelButton = document.getElementById('cancelButton');
const btnProgress = document.getElementById('btnProgress');

let abortController = null;
let progressInterval = null;
let isChecking = false; // Guard to prevent duplicate calls

checkButton.addEventListener('click', handleCheck);
cancelButton.addEventListener('click', handleCancel);

tokenAddressInput.addEventListener('input', handleTokenAddressChange);
tokenAddressInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        handleCheck();
    }
});

bondingCurveInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        handleCheck();
    }
});

function handleTokenAddressChange() {
    const tokenAddress = tokenAddressInput.value.trim();
    const bondingCurveContainer = document.getElementById('bondingCurveContainer');
    
    // Check if it's a Solana address (Pump.fun)
    // Solana addresses: 32-44 characters, don't start with 0x
    const isSolana = !tokenAddress.startsWith('0x') && tokenAddress.length >= 32 && tokenAddress.length <= 44;
    
    if (isSolana && tokenAddress.length > 0) {
        // Show bonding curve field for Pump.fun
        bondingCurveContainer.style.display = 'block';
        bondingCurveInput.required = true;
    } else {
        // Hide bonding curve field for BSC or empty
        bondingCurveContainer.style.display = 'none';
        bondingCurveInput.required = false;
        bondingCurveInput.value = '';
    }
}

function handleCancel() {
    if (abortController) {
        abortController.abort();
    }
    resetUI();
}

async function handleCheck() {
    // Prevent duplicate calls
    if (isChecking) {
        console.log('Already checking, ignoring duplicate call');
        return;
    }
    
    const tokenAddress = tokenAddressInput.value.trim();
    const bondingCurve = bondingCurveInput.value.trim();
    
    if (!tokenAddress) {
        showError('Please enter a token address');
        return;
    }
    
    // Validate address format (basic check)
    // BSC addresses: 0x + 40 hex chars = 42 total
    // Solana addresses: 32-44 base58 characters
    const isBSC = tokenAddress.startsWith('0x') && tokenAddress.length === 42;
    const isSolana = !tokenAddress.startsWith('0x') && tokenAddress.length >= 32 && tokenAddress.length <= 44;
    
    if (!isBSC && !isSolana) {
        showError('Invalid token address format. BSC addresses should start with 0x and be 42 characters. Solana addresses should be 32-44 characters.');
        return;
    }
    
    // For Solana/Pump.fun, bonding curve is required
    if (isSolana && !bondingCurve) {
        showError('Bonding curve address is required for Pump.fun tokens');
        return;
    }
    
    isChecking = true;
    setLoading(true);
    resultSection.style.display = 'none';
    
    // Create abort controller for cancellation
    abortController = new AbortController();
    
    // Start progress animation
    startProgress();
    
    try {
        const payload = {
            token_address: tokenAddress
        };
        
        // Add bonding curve for Pump.fun tokens
        if (isSolana) {
            payload.bonding_curve = bondingCurve;
        }
        
        const response = await fetch('/api/check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
            signal: abortController.signal
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'An error occurred');
        }
        
        // Complete progress
        setProgress(100);
        setTimeout(() => {
            displayResults(data);
            resetUI();
        }, 300);
        
    } catch (error) {
        if (error.name === 'AbortError') {
            showError('Check cancelled by user');
        } else {
            showError(error.message || 'Failed to check token. Please try again.');
        }
        resetUI();
    } finally {
        isChecking = false;
    }
}

function startProgress() {
    let progress = 0;
    let firstQueryDone = false;
    
    // Simulate first query completion at 50%
    setTimeout(() => {
        firstQueryDone = true;
        setProgress(50);
    }, 2000); // After 2 seconds, first query "completes"
    
    // Continue progress from 50% to 100% uniformly
    progressInterval = setInterval(() => {
        if (firstQueryDone && progress < 95) {
            progress += 0.5; // Increment slowly
            setProgress(50 + (progress * 0.5)); // Scale from 50% to 100%
        }
    }, 100);
}

function setProgress(percent) {
    btnProgress.style.width = `${Math.min(100, Math.max(0, percent))}%`;
}

function resetUI() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
    setLoading(false);
    setProgress(0);
    abortController = null;
    isChecking = false;
}

function setLoading(loading) {
    checkButton.disabled = loading;
    const btnText = checkButton.querySelector('.btn-text');
    const btnLoader = checkButton.querySelector('.btn-loader');
    
    if (loading) {
        btnText.style.display = 'none';
        btnLoader.style.display = 'flex';
        cancelButton.style.display = 'block';
    } else {
        btnText.style.display = 'inline';
        btnLoader.style.display = 'none';
        cancelButton.style.display = 'none';
    }
}

function displayResults(data) {
    resultSection.style.display = 'block';
    
    // Set token type for formatting
    currentTokenType = data.token_type || 'fourmeme';
    
    if (!data.phishy) {
        displaySafeResult(data);
    } else {
        displayPhishyResult(data);
    }
}

function displaySafeResult(data) {
    const tokenTypeLabel = data.token_type === 'pumpfun' ? 'Pump.fun' : 'Four.Meme';
    resultContent.innerHTML = `
        <div class="result-header safe">
            <span class="result-icon">✅</span>
            <div>
                <div class="result-title">Token Appears Safe</div>
                <div style="color: var(--text-secondary); margin-top: 4px;">
                    No phishy behavior detected (${tokenTypeLabel})
                </div>
            </div>
        </div>
    `;
    // Refresh recent phishy list
    setTimeout(loadRecentPhishy, 500);
}

function displayPhishyResult(data) {
    const { phishy_addresses, totals } = data.data;
    
    let phishyListHTML = '';
    
    if (phishy_addresses.length > 0) {
        phishyListHTML = '<div class="phishy-list"><h3 style="margin-bottom: 20px; color: var(--danger);">⚠️ Suspicious Addresses</h3>';
        
        phishy_addresses.forEach((addr, index) => {
            const transferred = formatNumber(addr.total_transferred || 0);
            const bought = formatNumber(addr.total_bought || 0);
            const withoutBuy = formatNumber(addr.transferred_without_buy || 0);
            
            phishyListHTML += `
                <div class="phishy-item">
                    <div class="phishy-item-header">
                        <span style="color: var(--danger); font-weight: 700;">#${index + 1}</span>
                        <span class="address">${addr.address}</span>
                    </div>
                    <div class="phishy-details">
                        <div class="detail-item">
                            <span class="detail-label">First Transfer</span>
                            <span class="detail-value">${formatTimestamp(addr.first_transfer_time)}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">First Buy</span>
                            <span class="detail-value">${formatTimestamp(addr.first_buy_time) || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Total Transferred</span>
                            <span class="detail-value">${transferred}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Total Bought</span>
                            <span class="detail-value">${bought}</span>
                        </div>
                    </div>
                    ${withoutBuy > 0 ? `<div class="warning-badge">⚠️ Transferred Without Buy: ${withoutBuy}</div>` : ''}
                    <div style="margin-top: 12px; color: var(--text-secondary); font-size: 0.9rem;">
                        <strong>Reason:</strong> ${addr.reason}
                    </div>
                </div>
            `;
        });
        
        phishyListHTML += '</div>';
    }
    
    const tokenTypeLabel = data.token_type === 'pumpfun' ? 'Pump.fun' : 'Four.Meme';
    resultContent.innerHTML = `
        <div class="result-header phishy">
            <span class="result-icon">⚠️</span>
            <div>
                <div class="result-title">TOKEN IS PHISHY!</div>
                <div style="color: var(--text-secondary); margin-top: 4px;">
                    Found ${data.data.phishy_count} suspicious address(es) (${tokenTypeLabel})
                </div>
            </div>
        </div>
        ${totals ? `
            <div class="summary-section">
                <div class="summary-title">📊 Summary of Phishy Behavior</div>
                ${data.token_type === 'fourmeme' ? `
                    <div style="color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 16px; font-style: italic;">
                        Note: Amounts shown are in tokens (converted from smallest unit, assuming 18 decimals)
                    </div>
                ` : `
                    <div style="color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 16px; font-style: italic;">
                        Note: Amounts are already decimal-adjusted for Pump.fun tokens
                    </div>
                `}
                <div class="summary-grid">
                    <div class="summary-item">
                        <div class="summary-value">${formatNumber(totals.total_transferred)}</div>
                        <div class="summary-label">Total Transferred</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-value">${formatNumber(totals.total_bought)}</div>
                        <div class="summary-label">Total Bought</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-value" style="color: var(--danger);">${formatNumber(totals.total_without_buy)}</div>
                        <div class="summary-label">⚠️ Transferred Without Purchase</div>
                    </div>
                </div>
            </div>
        ` : ''}
        ${phishyListHTML}
    `;
    // Refresh recent phishy list after showing results
    setTimeout(loadRecentPhishy, 500);
}

function showError(message) {
    resultSection.style.display = 'block';
    resultContent.innerHTML = `
        <div class="error-message">
            <strong>Error:</strong> ${message}
        </div>
    `;
}

// Store current token type for formatting
let currentTokenType = 'fourmeme';

function formatNumber(num) {
    if (!num || num === 0) return '0';
    const n = typeof num === 'string' ? parseFloat(num) : num;
    
    // Pump.fun amounts are already decimal-adjusted, BSC amounts need conversion
    if (currentTokenType === 'pumpfun') {
        // Pump.fun: amounts are already in tokens, just format
        if (n >= 1000000000) {
            return (n / 1000000000).toFixed(2) + 'B';
        } else if (n >= 1000000) {
            return (n / 1000000).toFixed(2) + 'M';
        } else if (n >= 1000) {
            return (n / 1000).toFixed(2) + 'K';
        } else {
            return n.toLocaleString('en-US', { maximumFractionDigits: 4 });
        }
    } else {
        // BSC/Four.Meme: amounts are in smallest unit (18 decimals)
        const DECIMALS = 18;
        const divisor = Math.pow(10, DECIMALS);
        
        if (n >= divisor) {
            const inTokens = n / divisor;
            
            // Format in tokens
            if (inTokens >= 1000000000) {
                return (inTokens / 1000000000).toFixed(2) + 'B';
            } else if (inTokens >= 1000000) {
                return (inTokens / 1000000).toFixed(2) + 'M';
            } else if (inTokens >= 1000) {
                return (inTokens / 1000).toFixed(2) + 'K';
            } else {
                return inTokens.toLocaleString('en-US', { maximumFractionDigits: 4 });
            }
        } else {
            // Very small amount, show in smallest unit
            if (n >= 1000000) {
                return (n / 1000000).toFixed(2) + 'M (raw)';
            } else if (n >= 1000) {
                return (n / 1000).toFixed(2) + 'K (raw)';
            }
            return n.toLocaleString('en-US', { maximumFractionDigits: 2 });
        }
    }
}

function formatTimestamp(ts) {
    if (!ts) return 'N/A';
    try {
        const date = new Date(ts);
        return date.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch {
        return ts;
    }
}

async function loadRecentPhishy() {
    try {
        const response = await fetch('/api/recent-phishy');
        const data = await response.json();
        
        if (data.success && data.tokens.length > 0) {
            displayRecentPhishy(data.tokens);
        }
    } catch (error) {
        console.error('Failed to load recent phishy tokens:', error);
    }
}

function displayRecentPhishy(tokens) {
    const container = document.getElementById('recentTokensContainer');
    if (!container) return;
    
    if (tokens.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; color: var(--text-secondary); padding: 20px; grid-column: 1 / -1;">
                No phishy tokens found yet. Search for tokens to see results here.
            </div>
        `;
        return;
    }
    
    let recentHTML = '';
    
    tokens.slice(0, 10).forEach((token) => {
        const timeAgo = getTimeAgo(token.timestamp);
        const tokenType = token.token_type === 'pumpfun' ? 'Pump.fun' : 'Four.Meme';
        // Set token type for formatting
        const prevTokenType = currentTokenType;
        currentTokenType = token.token_type || 'fourmeme';
        
        recentHTML += `
            <div class="recent-token-card" onclick="checkToken('${token.token_address}')" style="cursor: pointer;">
                <div class="recent-token-header">
                    <span class="address" style="font-size: 0.85rem;">${token.token_address}</span>
                    <span style="color: var(--danger); font-weight: 700; font-size: 0.9rem;">⚠️ ${token.phishy_count} Phishy</span>
                </div>
                <div style="color: var(--accent-primary); font-size: 0.75rem; margin-bottom: 4px;">
                    ${tokenType}
                </div>
                ${token.totals ? `
                    <div class="recent-token-details">
                        <div style="color: var(--text-secondary); font-size: 0.85rem;">
                            Without Buy: <span style="color: var(--danger); font-weight: 600;">${formatNumber(token.totals.total_without_buy)}</span>
                        </div>
                    </div>
                ` : ''}
                <div style="color: var(--text-secondary); font-size: 0.75rem; margin-top: 8px;">
                    ${timeAgo}
                </div>
            </div>
        `;
        
        // Restore previous token type
        currentTokenType = prevTokenType;
    });
    
    container.innerHTML = recentHTML;
    
    // Update count in header
    const header = document.querySelector('#recentPhishySection h3 span:last-child');
    if (header) {
        header.textContent = `Recently Searched Phishy Tokens (${tokens.length})`;
    }
}

function checkToken(address) {
    // Prevent if already checking
    if (isChecking) {
        return;
    }
    tokenAddressInput.value = address;
    handleCheck();
}

function getTimeAgo(timestamp) {
    try {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
    } catch {
        return 'Unknown';
    }
}

// Load recent phishy tokens on page load
document.addEventListener('DOMContentLoaded', () => {
    loadRecentPhishy();
});

