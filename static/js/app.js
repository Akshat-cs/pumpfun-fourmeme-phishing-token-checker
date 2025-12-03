const checkButton = document.getElementById('checkButton');
const tokenAddressInput = document.getElementById('tokenAddress');
const resultSection = document.getElementById('resultSection');
const resultContent = document.getElementById('resultContent');
const cancelButton = document.getElementById('cancelButton');
const btnProgress = document.getElementById('btnProgress');

// Helper function to create address with link and copy functionality
function formatAddressWithLink(address, isSolana = false) {
    const shortAddress = `${address.slice(0, 6)}...${address.slice(-4)}`;
    const fullAddress = address;
    const addressId = `addr-${address.replace(/[^a-zA-Z0-9]/g, '-')}`;
    
    // Create dexrabbit link for Solana addresses
    const dexrabbitLink = isSolana ? `https://dexrabbit.com/solana/trader/${address}` : null;
    
    if (dexrabbitLink) {
        return `
            <span style="display: inline-flex; align-items: center; gap: 6px;">
                <a href="${dexrabbitLink}" target="_blank" rel="noopener noreferrer" 
                   style="color: var(--accent-primary); text-decoration: none; font-weight: 500;"
                   onmouseover="this.style.textDecoration='underline'" 
                   onmouseout="this.style.textDecoration='none'"
                   title="View on DEXrabbit: ${fullAddress}">
                    ${shortAddress}
                </a>
                <button class="copy-address-btn" 
                        data-address="${fullAddress.replace(/"/g, '&quot;')}"
                        style="background: transparent; border: 1px solid var(--border); border-radius: 4px; padding: 2px 6px; cursor: pointer; color: var(--text-secondary); font-size: 0.75rem; transition: all 0.2s;"
                        title="Copy full address"
                        onmouseover="this.style.borderColor='var(--accent-primary)'"
                        onmouseout="this.style.borderColor='var(--border)'">
                    📋
                </button>
            </span>
        `;
    } else {
        // For BSC or other addresses, just show with copy button
        return `
            <span style="display: inline-flex; align-items: center; gap: 6px;">
                <span style="font-weight: 500;">${shortAddress}</span>
                <button class="copy-address-btn" 
                        data-address="${fullAddress.replace(/"/g, '&quot;')}"
                        style="background: transparent; border: 1px solid var(--border); border-radius: 4px; padding: 2px 6px; cursor: pointer; color: var(--text-secondary); font-size: 0.75rem; transition: all 0.2s;"
                        title="Copy full address"
                        onmouseover="this.style.borderColor='var(--accent-primary)'"
                        onmouseout="this.style.borderColor='var(--border)'">
                    📋
                </button>
            </span>
        `;
    }
}

// Add event delegation for copy buttons
document.addEventListener('click', function(e) {
    if (e.target.closest('.copy-address-btn')) {
        e.preventDefault();
        e.stopPropagation();
        const btn = e.target.closest('.copy-address-btn');
        const address = btn.getAttribute('data-address');
        if (address) {
            navigator.clipboard.writeText(address).then(() => {
                const originalText = btn.innerHTML;
                btn.innerHTML = '✓';
                btn.style.color = 'var(--accent-primary)';
                btn.style.borderColor = 'var(--accent-primary)';
                setTimeout(() => {
                    btn.innerHTML = originalText;
                    btn.style.color = '';
                    btn.style.borderColor = '';
                }, 1000);
            }).catch(err => {
                console.error('Failed to copy:', err);
            });
        }
    }
});

let abortController = null;
let progressInterval = null;
let isChecking = false; // Guard to prevent duplicate calls

checkButton.addEventListener('click', handleCheck);
cancelButton.addEventListener('click', handleCancel);

tokenAddressInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        handleCheck();
    }
});

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
    
    isChecking = true;
    setLoading(true);
    resultSection.style.display = 'none';
    
    // Create abort controller for cancellation
    abortController = new AbortController();
    
    // Start progress animation
    startProgress();
    
    try {
        const response = await fetch('/api/check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                token_address: tokenAddress
            }),
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
    const { top_holders, bonding_curve } = data.data || {};
    
    // Top holders section for Pump.fun tokens
    let topHoldersHTML = '';
    if (data.token_type === 'pumpfun' && top_holders && top_holders.length > 0) {
        topHoldersHTML = `
            <div class="top-holders-section" style="margin-top: 30px; padding-top: 30px; border-top: 1px solid var(--border);">
                <h3 style="margin-bottom: 20px; color: var(--accent-primary);">🏆 Top 10 Holders</h3>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="border-bottom: 2px solid var(--border);">
                                <th style="text-align: left; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">#</th>
                                <th style="text-align: left; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">Address</th>
                                <th style="text-align: right; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">Total Pump.Fun tokens held</th>
                                <th style="text-align: right; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">Total trades (last 6h)</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${top_holders.map((holder, index) => {
                                const isBondingCurve = bonding_curve && holder.address === bonding_curve;
                                return `
                                    <tr style="border-bottom: 1px solid var(--border);">
                                        <td style="padding: 12px; color: var(--text-primary); font-weight: 600;">#${index + 1}</td>
                                        <td style="padding: 12px; color: var(--text-primary);">
                                            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                                                ${formatAddressWithLink(holder.address, true)}
                                                ${isBondingCurve ? '<span style="background: var(--accent-primary); color: var(--bg-primary); padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">Bonding Curve</span>' : ''}
                                            </div>
                                        </td>
                                        <td style="padding: 12px; text-align: right; color: var(--text-primary);">${holder.pump_tokens_count || 0}</td>
                                        <td style="padding: 12px; text-align: right; color: var(--text-primary);">${holder.trades_6h || 0}</td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }
    
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
        ${topHoldersHTML}
    `;
    // Refresh recent phishy list
    setTimeout(loadRecentPhishy, 500);
}

function displayPhishyResult(data) {
    const { phishy_addresses, totals, top_holders } = data.data;
    
    let phishyListHTML = '';
    
    if (phishy_addresses.length > 0) {
        phishyListHTML = '<div class="phishy-list"><h3 style="margin-bottom: 20px; color: var(--danger);">⚠️ Suspicious Addresses</h3>';
        
        phishy_addresses.forEach((addr, index) => {
            const transferred = formatNumber(addr.total_transferred || 0, data.token_type);
            const bought = formatNumber(addr.total_bought || 0, data.token_type);
            const withoutBuy = formatNumber(addr.transferred_without_buy || 0, data.token_type);
            
            const isSolanaAddr = !addr.address.startsWith('0x') && addr.address.length >= 32;
            phishyListHTML += `
                <div class="phishy-item">
                    <div class="phishy-item-header">
                        <span style="color: var(--danger); font-weight: 700;">#${index + 1}</span>
                        <span class="address">${formatAddressWithLink(addr.address, isSolanaAddr)}</span>
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
    
    // Top holders section for Pump.fun tokens
    let topHoldersHTML = '';
    if (data.token_type === 'pumpfun' && top_holders && top_holders.length > 0) {
        const { bonding_curve } = data.data || {};
        topHoldersHTML = `
            <div class="top-holders-section" style="margin-top: 30px; padding-top: 30px; border-top: 1px solid var(--border);">
                <h3 style="margin-bottom: 20px; color: var(--accent-primary);">🏆 Top 10 Holders</h3>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="border-bottom: 2px solid var(--border);">
                                <th style="text-align: left; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">#</th>
                                <th style="text-align: left; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">Address</th>
                                <th style="text-align: right; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">Total Pump.Fun tokens held</th>
                                <th style="text-align: right; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">Total trades (last 6h)</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${top_holders.map((holder, index) => {
                                const isBondingCurve = bonding_curve && holder.address === bonding_curve;
                                return `
                                    <tr style="border-bottom: 1px solid var(--border);">
                                        <td style="padding: 12px; color: var(--text-primary); font-weight: 600;">#${index + 1}</td>
                                        <td style="padding: 12px; color: var(--text-primary);">
                                            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                                                ${formatAddressWithLink(holder.address, true)}
                                                ${isBondingCurve ? '<span style="background: var(--accent-primary); color: var(--bg-primary); padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">Bonding Curve</span>' : ''}
                                            </div>
                                        </td>
                                        <td style="padding: 12px; text-align: right; color: var(--text-primary);">${holder.pump_tokens_count || 0}</td>
                                        <td style="padding: 12px; text-align: right; color: var(--text-primary);">${holder.trades_6h || 0}</td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
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
                        <div class="summary-value">${formatNumber(totals.total_transferred, data.token_type)}</div>
                        <div class="summary-label">Total Transferred</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-value">${formatNumber(totals.total_bought, data.token_type)}</div>
                        <div class="summary-label">Total Bought</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-value" style="color: var(--danger);">${formatNumber(totals.total_without_buy, data.token_type)}</div>
                        <div class="summary-label">⚠️ Transferred Without Purchase</div>
                    </div>
                </div>
            </div>
        ` : ''}
        ${phishyListHTML}
        ${topHoldersHTML}
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

