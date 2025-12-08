const checkButton = document.getElementById("checkButton");
const tokenAddressInput = document.getElementById("tokenAddress");
const resultSection = document.getElementById("resultSection");
const resultContent = document.getElementById("resultContent");
const cancelButton = document.getElementById("cancelButton");
const btnProgress = document.getElementById("btnProgress");

// Helper function to create address with link and copy functionality
function formatAddressWithLink(address) {
  const shortAddress = `${address.slice(0, 6)}...${address.slice(-4)}`;
  const fullAddress = address;
  const dexrabbitLink = `https://dexrabbit.com/solana/trader/${address}`;

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
                    data-address="${fullAddress.replace(/"/g, "&quot;")}"
                    style="background: transparent; border: 1px solid var(--border); border-radius: 4px; padding: 2px 6px; cursor: pointer; color: var(--text-secondary); font-size: 0.75rem; transition: all 0.2s;"
                    title="Copy full address"
                    onmouseover="this.style.borderColor='var(--accent-primary)'"
                    onmouseout="this.style.borderColor='var(--border)'">
                📋
            </button>
        </span>
    `;
}

// Add event delegation for copy buttons
document.addEventListener("click", function (e) {
  if (e.target.closest(".copy-address-btn")) {
    e.preventDefault();
    e.stopPropagation();
    const btn = e.target.closest(".copy-address-btn");
    const address = btn.getAttribute("data-address");
    if (address) {
      navigator.clipboard
        .writeText(address)
        .then(() => {
          const originalText = btn.innerHTML;
          btn.innerHTML = "✓";
          btn.style.color = "var(--accent-primary)";
          btn.style.borderColor = "var(--accent-primary)";
          setTimeout(() => {
            btn.innerHTML = originalText;
            btn.style.color = "";
            btn.style.borderColor = "";
          }, 1000);
        })
        .catch((err) => {
          console.error("Failed to copy:", err);
        });
    }
  }
});

let abortController = null;
let progressInterval = null;
let isChecking = false; // Guard to prevent duplicate calls

checkButton.addEventListener("click", handleCheck);
cancelButton.addEventListener("click", handleCancel);

tokenAddressInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") {
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
    console.log("Already checking, ignoring duplicate call");
    return;
  }

  const tokenAddress = tokenAddressInput.value.trim();

  if (!tokenAddress) {
    showError("Please enter a token address");
    return;
  }

  // Validate Solana address format
  const isSolana =
    !tokenAddress.startsWith("0x") &&
    tokenAddress.length >= 32 &&
    tokenAddress.length <= 44;

  if (!isSolana) {
    showError(
      "Invalid Pump.fun token address format. Solana addresses should be 32-44 characters and not start with 0x."
    );
    return;
  }

  isChecking = true;
  setLoading(true);
  resultSection.style.display = "none";

  // Create abort controller for cancellation
  abortController = new AbortController();

  // Start progress animation
  startProgress();

  try {
    const response = await fetch("/api/check", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        token_address: tokenAddress,
      }),
      signal: abortController.signal,
    });

    const data = await response.json();

    if (!response.ok) {
      // Check if it's an info message (not a real error)
      if (data.error_type === "info") {
        showInfoMessage(data.error || "An error occurred");
        resetUI();
        return;
      }
      throw new Error(data.error || "An error occurred");
    }

    // Complete progress
    setProgress(100);
    setTimeout(() => {
      try {
        displayResults(data);
      } catch (error) {
        console.error("Error displaying results:", error);
        showError("Error displaying results: " + error.message);
      } finally {
        resetUI();
      }
    }, 300);
  } catch (error) {
    if (error.name === "AbortError") {
      showError("Check cancelled by user");
    } else {
      showError(error.message || "Failed to check token. Please try again.");
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
      setProgress(50 + progress * 0.5); // Scale from 50% to 100%
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
  const btnText = checkButton.querySelector(".btn-text");
  const btnLoader = checkButton.querySelector(".btn-loader");

  if (loading) {
    btnText.style.display = "none";
    btnLoader.style.display = "flex";
    cancelButton.style.display = "block";
  } else {
    btnText.style.display = "inline";
    btnLoader.style.display = "none";
    cancelButton.style.display = "none";
  }
}

function displayResults(data) {
  console.log("Displaying results:", data);
  resultSection.style.display = "block";

  // Set token type for formatting
  currentTokenType = "pumpfun";

  try {
    if (!data.phishy) {
      displaySafeResult(data);
    } else {
      displayPhishyResult(data);
    }
  } catch (error) {
    console.error("Error in displayResults:", error);
    throw error;
  }
}

function calculateScore(liquidity_sol, phishy_count, holder_analysis) {
  let failedMetrics = 0;

  // Check liquidity (metric 1)
  if (liquidity_sol !== null && liquidity_sol !== undefined) {
    const isAdequate = liquidity_sol >= 10.0;
    if (!isAdequate) {
      failedMetrics++;
    }
  }

  // Check insider analysis (metric 2)
  if (phishy_count > 0) {
    failedMetrics++;
  }

  // Check holder analysis metrics (3, 4, 5)
  if (holder_analysis) {
    if (!holder_analysis.creator_check_passed) {
      failedMetrics++;
    }
    if (!holder_analysis.other_holders_check_passed) {
      failedMetrics++;
    }
    if (!holder_analysis.top10_check_passed) {
      failedMetrics++;
    }
  }

  // Calculate score: 100 - (failed_metrics * 20)
  // Math.max(0, ...) ensures score never goes below 0, even if all metrics fail
  const score = Math.max(0, 100 - failedMetrics * 20);
  return { score, failedMetrics };
}

function displayScore(score, failedMetrics) {
  return `
    <div style="margin-top: 30px; padding-top: 30px; border-top: 1px solid var(--border);">
      <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px;">
        <span style="color: var(--text-primary); font-size: 1.5rem; font-weight: 700;">Score:</span>
        <span style="color: #ff6b35; font-size: 1.5rem; font-weight: 700;">${score}/100</span>
      </div>
      <div style="background: var(--bg-secondary); border-radius: 8px; padding: 16px; border: 1px solid var(--border);">
        <div style="color: var(--text-secondary); font-size: 0.9rem; line-height: 1.6;">
          The audit score is a measure of how well the token meets the criteria for safety. Automated scanners like this one are not always completely accurate. 
          <strong style="color: var(--text-primary);">A token with a high score may still have hidden malicious code.</strong> 
          The score is not advice and should be considered along with other factors. Always do your own research and consult multiple sources of information.
        </div>
      </div>
    </div>
  `;
}

function displayLiquidityAnalysis(liquidity_sol) {
  if (liquidity_sol === null || liquidity_sol === undefined) {
    return "";
  }

  // Consider liquidity adequate if >= 10 SOL
  const isAdequate = liquidity_sol >= 10.0;
  const formattedLiquidity = liquidity_sol.toFixed(2);

  return `
    <div style="margin-top: 30px; padding-top: 30px; border-top: 1px solid var(--border);">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <h3 style="margin: 0; color: var(--accent-primary);">Liquidity Analysis</h3>
        <a href="https://ide.bitquery.io/Latest-liquidity-in-the-curve" target="_blank" rel="noopener noreferrer" 
           style="background: transparent; border: 1px solid #d1d5db; border-radius: 8px; padding: 8px 16px; color: var(--text-primary); text-decoration: none; font-size: 0.9rem; font-weight: 500; transition: all 0.2s ease; display: inline-block;"
           onmouseover="this.style.borderColor='var(--accent-primary)'; this.style.color='var(--accent-primary)'" 
           onmouseout="this.style.borderColor='#d1d5db'; this.style.color='var(--text-primary)'">
          Get API
        </a>
      </div>
      
      <div style="display: flex; flex-direction: column; gap: 16px;">
        <div style="display: flex; align-items: flex-start; gap: 12px; padding: 12px; background: var(--bg-secondary); border-radius: 8px; border: 1px solid var(--border);">
          <div style="font-size: 1.2rem; flex-shrink: 0;">
            ${isAdequate ? "✅" : "❌"}
          </div>
          <div style="flex: 1;">
            <div style="color: var(--text-primary); font-weight: 500; margin-bottom: 4px;">
              ${
                isAdequate
                  ? "Adequate current liquidity"
                  : "Inadequate current liquidity"
              }
            </div>
            <div style="color: var(--text-secondary); font-size: 0.9rem; margin-top: 8px;">
              ${formattedLiquidity} SOL in Pumpfun
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

function displayInsiderAnalysis(phishy_count, phishy_addresses) {
  // Check if suspect trading groups detected (phishy addresses found)
  const noSuspectTradingGroups = phishy_count === 0;

  return `
    <div style="margin-top: 30px; padding-top: 30px; border-top: 1px solid var(--border);">
      <h3 style="margin: 0; margin-bottom: 20px; color: var(--accent-primary);">Insider Analysis</h3>
      
      <div style="display: flex; flex-direction: column; gap: 16px;">
        <!-- Check 1: No suspect trading groups detected -->
        <div style="display: flex; align-items: flex-start; gap: 12px; padding: 12px; background: var(--bg-secondary); border-radius: 8px; border: 1px solid var(--border);">
          <div style="font-size: 1.2rem; flex-shrink: 0;">
            ${noSuspectTradingGroups ? "✅" : "❌"}
          </div>
          <div style="flex: 1;">
            <div style="color: var(--text-primary); font-weight: 500;">
              No suspect trading groups detected
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

function displayHolderAnalysis(holder_analysis, top_holders) {
  if (!holder_analysis) return "";

  const {
    creator_percent,
    creator_check_passed,
    other_holders_check_passed,
    top10_percent,
    top10_check_passed,
    failed_holder,
  } = holder_analysis;

  // Create "View Holders" link - scroll to top holders section
  const viewHoldersLink =
    top_holders && top_holders.length > 0
      ? `<a href="#top-holders" onclick="document.getElementById('top-holders')?.scrollIntoView({behavior: 'smooth', block: 'start'}); return false;" style="color: var(--accent-primary); text-decoration: none; font-size: 0.9rem; font-weight: 500;" onmouseover="this.style.textDecoration='underline'" onmouseout="this.style.textDecoration='none'">View Holders</a>`
      : "";

  return `
    <div style="margin-top: 30px; padding-top: 30px; border-top: 1px solid var(--border);">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <h3 style="margin: 0; color: var(--accent-primary);">Holder Analysis</h3>
        ${viewHoldersLink}
      </div>
      
      <div style="display: flex; flex-direction: column; gap: 16px;">
        <!-- Check 1: Creator holds less than 5% -->
        <div style="display: flex; align-items: flex-start; gap: 12px; padding: 12px; background: var(--bg-secondary); border-radius: 8px; border: 1px solid var(--border);">
          <div style="font-size: 1.2rem; flex-shrink: 0;">
            ${creator_check_passed ? "✅" : "❌"}
          </div>
          <div style="flex: 1;">
            <div style="color: var(--text-primary); font-weight: 500; margin-bottom: 4px;">
              Creator holds less than 5% of circulating token supply (${creator_percent}%)
            </div>
          </div>
        </div>
        
        <!-- Check 2: All other holders possess less than 5% -->
        <div style="display: flex; align-items: flex-start; gap: 12px; padding: 12px; background: var(--bg-secondary); border-radius: 8px; border: 1px solid var(--border);">
          <div style="font-size: 1.2rem; flex-shrink: 0;">
            ${other_holders_check_passed ? "✅" : "❌"}
          </div>
          <div style="flex: 1;">
            <div style="color: var(--text-primary); font-weight: 500; margin-bottom: 4px;">
              All other holders possess less than 5% of circulating token supply
            </div>
            ${
              !other_holders_check_passed
                ? `
              <div style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 8px; font-style: italic;">
                A wallet contains a substantial amount of tokens (circulating supply is total supply minus burned amount) which could have a large impact on the token price if sold.
              </div>
            `
                : ""
            }
          </div>
        </div>
        
        <!-- Check 3: Top 10 holders possess less than 70% -->
        <div style="display: flex; align-items: flex-start; gap: 12px; padding: 12px; background: var(--bg-secondary); border-radius: 8px; border: 1px solid var(--border);">
          <div style="font-size: 1.2rem; flex-shrink: 0;">
            ${top10_check_passed ? "✅" : "❌"}
          </div>
          <div style="flex: 1;">
            <div style="color: var(--text-primary); font-weight: 500; margin-bottom: 4px;">
              Top 10 token holders possess less than 70% of circulating token supply (${top10_percent}%)
            </div>
            ${
              !top10_check_passed
                ? `
              <div style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 8px; font-style: italic;">
                The top 10 holders possess a substantial amount of tokens (circulating supply is total supply minus burned amount) which could have a large impact on the token price if sold.
              </div>
            `
                : ""
            }
          </div>
        </div>
      </div>
    </div>
  `;
}

function displayTokenMetadata(token_metadata) {
  if (!token_metadata || (!token_metadata.name && !token_metadata.symbol)) {
    return "";
  }

  const {
    name,
    symbol,
    is_mayhem_mode,
    image,
    twitter,
    website,
    telegram,
    description,
  } = token_metadata;

  return `
    <div style="margin-top: 20px; padding: 20px; background: var(--bg-secondary); border-radius: 8px; border: 1px solid var(--border);">
      <div style="display: flex; gap: 20px; align-items: flex-start; flex-wrap: wrap;">
        ${
          image
            ? `
          <div style="flex-shrink: 0;">
            <img src="${image}" alt="${name || symbol || "Token"}" 
                 style="width: 120px; height: 120px; border-radius: 8px; object-fit: cover; border: 1px solid var(--border);" 
                 onerror="this.style.display='none'">
          </div>
        `
            : ""
        }
        <div style="flex: 1; min-width: 200px;">
          ${
            name
              ? `<div style="font-size: 1.5rem; font-weight: 700; color: var(--text-primary); margin-bottom: 8px;">${name}</div>`
              : ""
          }
          ${
            symbol
              ? `<div style="font-size: 1.1rem; color: var(--text-secondary); margin-bottom: 12px;">${symbol}${
                  description ? ` | ${description}` : ""
                }</div>`
              : description
              ? `<div style="font-size: 1.1rem; color: var(--text-secondary); margin-bottom: 12px;">${description}</div>`
              : ""
          }
          <div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-bottom: 12px;">
            ${
              is_mayhem_mode
                ? `
              <span style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 4px 12px; border-radius: 6px; font-size: 0.85rem; font-weight: 600;">
                Mayhem Mode Token
              </span>
            `
                : `
              <span style="background: var(--bg-primary); color: var(--text-secondary); padding: 4px 12px; border-radius: 6px; font-size: 0.85rem; font-weight: 500; border: 1px solid var(--border);">
                No Mayhem Mode
              </span>
            `
            }
          </div>
          <div style="display: flex; gap: 16px; flex-wrap: wrap; margin-top: 12px;">
            ${
              twitter
                ? `
              <a href="${twitter}" target="_blank" rel="noopener noreferrer" 
                 style="color: var(--accent-primary); text-decoration: none; font-size: 0.9rem; font-weight: 500; display: inline-flex; align-items: center; gap: 6px;"
                 onmouseover="this.style.textDecoration='underline'" 
                 onmouseout="this.style.textDecoration='none'">
                🐦 Twitter
              </a>
            `
                : ""
            }
            ${
              website
                ? `
              <a href="${website}" target="_blank" rel="noopener noreferrer" 
                 style="color: var(--accent-primary); text-decoration: none; font-size: 0.9rem; font-weight: 500; display: inline-flex; align-items: center; gap: 6px;"
                 onmouseover="this.style.textDecoration='underline'" 
                 onmouseout="this.style.textDecoration='none'">
                🌐 Website
              </a>
            `
                : ""
            }
            ${
              telegram
                ? `
              <a href="${telegram}" target="_blank" rel="noopener noreferrer" 
                 style="color: var(--accent-primary); text-decoration: none; font-size: 0.9rem; font-weight: 500; display: inline-flex; align-items: center; gap: 6px;"
                 onmouseover="this.style.textDecoration='underline'" 
                 onmouseout="this.style.textDecoration='none'">
                💬 Telegram
              </a>
            `
                : ""
            }
          </div>
        </div>
      </div>
    </div>
  `;
}

function displaySafeResult(data) {
  const {
    top_holders,
    bonding_curve,
    mayhem_ai_agent,
    token_creation,
    holder_analysis,
    token_metadata,
    liquidity_sol,
  } = data.data || {};

  // Token metadata section
  const tokenMetadataHTML = displayTokenMetadata(token_metadata);

  // Token creation info section
  let tokenCreationHTML = "";
  if (
    token_creation &&
    (token_creation.transaction_signature || token_creation.creator_address)
  ) {
    const txSignature = token_creation.transaction_signature;
    const creatorAddress = token_creation.creator_address;
    const creationTime = token_creation.creation_time
      ? formatTimestampWithRelative(token_creation.creation_time)
      : "N/A";

    const txLink = txSignature
      ? `https://explorer.bitquery.io/solana/tx/${txSignature}`
      : "";
    const creatorLink = creatorAddress
      ? `https://dexrabbit.com/solana/trader/${creatorAddress}`
      : "";

    tokenCreationHTML = `
            <div style="margin-top: 20px; padding: 16px; background: var(--bg-secondary); border-radius: 8px; border: 1px solid var(--border);">
                <div style="margin-bottom: 12px; color: var(--text-secondary); font-size: 0.85rem; font-weight: 600;">Deployed at</div>
                <div style="margin-bottom: 8px; color: var(--text-primary); font-size: 0.9rem;">${creationTime}</div>
                <div style="display: flex; gap: 16px; flex-wrap: wrap; margin-top: 8px;">
                    ${
                      txLink
                        ? `
                        <a href="${txLink}" target="_blank" rel="noopener noreferrer" 
                           style="color: var(--text-secondary); font-size: 0.85rem; text-decoration: underline; cursor: pointer;"
                           onmouseover="this.style.color='var(--accent-primary)'" 
                           onmouseout="this.style.color='var(--text-secondary)'">
                            Transaction
                        </a>
                    `
                        : ""
                    }
                    ${
                      creatorLink
                        ? `
                        <a href="${creatorLink}" target="_blank" rel="noopener noreferrer" 
                           style="color: var(--text-secondary); font-size: 0.85rem; text-decoration: underline; cursor: pointer;"
                           onmouseover="this.style.color='var(--accent-primary)'" 
                           onmouseout="this.style.color='var(--text-secondary)'">
                            Creator
                        </a>
                    `
                        : ""
                    }
                </div>
            </div>
        `;
  }

  // Top holders section
  let topHoldersHTML = "";
  if (top_holders && top_holders.length > 0) {
    const { mayhem_ai_agent } = data.data || {};
    topHoldersHTML = `
            <div id="top-holders" class="top-holders-section" style="margin-top: 30px; padding-top: 30px; border-top: 1px solid var(--border);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <h3 style="margin: 0; color: var(--accent-primary);">🏆 Top 10 Holders</h3>
                    <a href="https://ide.bitquery.io/top-10-holders-of-a-pumpfun-token" target="_blank" rel="noopener noreferrer" 
                       style="background: transparent; border: 1px solid #d1d5db; border-radius: 8px; padding: 8px 16px; color: var(--text-primary); text-decoration: none; font-size: 0.9rem; font-weight: 500; transition: all 0.2s ease; display: inline-block;"
                       onmouseover="this.style.borderColor='var(--accent-primary)'; this.style.color='var(--accent-primary)'" 
                       onmouseout="this.style.borderColor='#d1d5db'; this.style.color='var(--text-primary)'">
                        Get API
                    </a>
                </div>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="border-bottom: 2px solid var(--border);">
                                <th style="text-align: left; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">#</th>
                                <th style="text-align: left; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">Address</th>
                                <th style="text-align: right; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">Holding Percentage</th>
                                <th style="text-align: right; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">Total Pump.Fun tokens held</th>
                                <th style="text-align: right; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">Total trades (last 6h)</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${top_holders
                              .map((holder, index) => {
                                const isBondingCurve =
                                  bonding_curve &&
                                  holder.address === bonding_curve;
                                const isMayhemAI =
                                  mayhem_ai_agent &&
                                  holder.address === mayhem_ai_agent;
                                return `
                                    <tr style="border-bottom: 1px solid var(--border);">
                                        <td style="padding: 12px; color: var(--text-primary); font-weight: 600;">#${
                                          index + 1
                                        }</td>
                                        <td style="padding: 12px; color: var(--text-primary);">
                                            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                                                ${formatAddressWithLink(
                                                  holder.address
                                                )}
                                                ${
                                                  isBondingCurve
                                                    ? '<span style="background: var(--accent-primary); color: var(--bg-primary); padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">Bonding Curve</span>'
                                                    : ""
                                                }
                                                ${
                                                  isMayhemAI
                                                    ? '<span style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">Mayhem mode AI agent</span>'
                                                    : ""
                                                }
                                            </div>
                                        </td>
                                        <td style="padding: 12px; text-align: right; color: var(--text-primary);">${
                                          holder.percent_holding !== undefined
                                            ? `${holder.percent_holding.toFixed(
                                                2
                                              )}%`
                                            : "N/A"
                                        }</td>
                                        <td style="padding: 12px; text-align: right; color: var(--text-primary);">${
                                          holder.pump_tokens_count || 0
                                        }</td>
                                        <td style="padding: 12px; text-align: right; color: var(--text-primary);">${
                                          holder.trades_6h || 0
                                        }</td>
                                    </tr>
                                `;
                              })
                              .join("")}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
  }

  // Calculate score
  const { score, failedMetrics } = calculateScore(
    liquidity_sol,
    0,
    holder_analysis
  );

  resultContent.innerHTML = `
        ${tokenMetadataHTML}
        ${tokenCreationHTML}
        ${displayScore(score, failedMetrics)}
        ${displayLiquidityAnalysis(liquidity_sol)}
        ${displayInsiderAnalysis(0, [])}
        ${displayHolderAnalysis(holder_analysis, top_holders)}
        ${topHoldersHTML}
    `;
}

function displayPhishyResult(data) {
  const {
    phishy_addresses,
    totals,
    top_holders,
    token_creation,
    holder_analysis,
    token_metadata,
    liquidity_sol,
  } = data.data;

  // Token metadata section
  const tokenMetadataHTML = displayTokenMetadata(token_metadata);

  // Token creation info section
  let tokenCreationHTML = "";
  if (
    token_creation &&
    (token_creation.transaction_signature || token_creation.creator_address)
  ) {
    const txSignature = token_creation.transaction_signature;
    const creatorAddress = token_creation.creator_address;
    const creationTime = token_creation.creation_time
      ? formatTimestampWithRelative(token_creation.creation_time)
      : "N/A";

    const txLink = txSignature
      ? `https://explorer.bitquery.io/solana/tx/${txSignature}`
      : "";
    const creatorLink = creatorAddress
      ? `https://dexrabbit.com/solana/trader/${creatorAddress}`
      : "";

    tokenCreationHTML = `
            <div style="margin-top: 20px; padding: 16px; background: var(--bg-secondary); border-radius: 8px; border: 1px solid var(--border);">
                <div style="margin-bottom: 12px; color: var(--text-secondary); font-size: 0.85rem; font-weight: 600;">Deployed at</div>
                <div style="margin-bottom: 8px; color: var(--text-primary); font-size: 0.9rem;">${creationTime}</div>
                <div style="display: flex; gap: 16px; flex-wrap: wrap; margin-top: 8px;">
                    ${
                      txLink
                        ? `
                        <a href="${txLink}" target="_blank" rel="noopener noreferrer" 
                           style="color: var(--text-secondary); font-size: 0.85rem; text-decoration: underline; cursor: pointer;"
                           onmouseover="this.style.color='var(--accent-primary)'" 
                           onmouseout="this.style.color='var(--text-secondary)'">
                            Transaction
                        </a>
                    `
                        : ""
                    }
                    ${
                      creatorLink
                        ? `
                        <a href="${creatorLink}" target="_blank" rel="noopener noreferrer" 
                           style="color: var(--text-secondary); font-size: 0.85rem; text-decoration: underline; cursor: pointer;"
                           onmouseover="this.style.color='var(--accent-primary)'" 
                           onmouseout="this.style.color='var(--text-secondary)'">
                            Creator
                        </a>
                    `
                        : ""
                    }
                    </div>
                </div>
            `;
  }

  // Top holders section
  let topHoldersHTML = "";
  if (top_holders && top_holders.length > 0) {
    const { bonding_curve, mayhem_ai_agent } = data.data || {};
    topHoldersHTML = `
            <div id="top-holders" class="top-holders-section" style="margin-top: 30px; padding-top: 30px; border-top: 1px solid var(--border);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <h3 style="margin: 0; color: var(--accent-primary);">🏆 Top 10 Holders</h3>
                    <a href="https://placeholder-link.com/holders-api" target="_blank" rel="noopener noreferrer" 
                       style="background: transparent; border: 1px solid #d1d5db; border-radius: 8px; padding: 8px 16px; color: var(--text-primary); text-decoration: none; font-size: 0.9rem; font-weight: 500; transition: all 0.2s ease; display: inline-block;"
                       onmouseover="this.style.borderColor='var(--accent-primary)'; this.style.color='var(--accent-primary)'" 
                       onmouseout="this.style.borderColor='#d1d5db'; this.style.color='var(--text-primary)'">
                        Get API
                    </a>
                </div>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="border-bottom: 2px solid var(--border);">
                                <th style="text-align: left; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">#</th>
                                <th style="text-align: left; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">Address</th>
                                <th style="text-align: right; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">Holding Percentage</th>
                                <th style="text-align: right; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">Total Pump.Fun tokens held</th>
                                <th style="text-align: right; padding: 12px; color: var(--text-secondary); font-weight: 600; font-size: 0.9rem;">Total trades (last 6h)</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${top_holders
                              .map((holder, index) => {
                                const isBondingCurve =
                                  bonding_curve &&
                                  holder.address === bonding_curve;
                                const isMayhemAI =
                                  mayhem_ai_agent &&
                                  holder.address === mayhem_ai_agent;
                                return `
                                    <tr style="border-bottom: 1px solid var(--border);">
                                        <td style="padding: 12px; color: var(--text-primary); font-weight: 600;">#${
                                          index + 1
                                        }</td>
                                        <td style="padding: 12px; color: var(--text-primary);">
                                            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                                                ${formatAddressWithLink(
                                                  holder.address
                                                )}
                                                ${
                                                  isBondingCurve
                                                    ? '<span style="background: var(--accent-primary); color: var(--bg-primary); padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">Bonding Curve</span>'
                                                    : ""
                                                }
                                                ${
                                                  isMayhemAI
                                                    ? '<span style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">Mayhem mode AI agent</span>'
                                                    : ""
                                                }
                                            </div>
                                        </td>
                                        <td style="padding: 12px; text-align: right; color: var(--text-primary);">${
                                          holder.percent_holding !== undefined
                                            ? `${holder.percent_holding.toFixed(
                                                2
                                              )}%`
                                            : "N/A"
                                        }</td>
                                        <td style="padding: 12px; text-align: right; color: var(--text-primary);">${
                                          holder.pump_tokens_count || 0
                                        }</td>
                                        <td style="padding: 12px; text-align: right; color: var(--text-primary);">${
                                          holder.trades_6h || 0
                                        }</td>
                                    </tr>
                                `;
                              })
                              .join("")}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
  }

  // Calculate score
  const { score, failedMetrics } = calculateScore(
    liquidity_sol,
    data.data.phishy_count || 0,
    holder_analysis
  );

  const tokenTypeLabel = "Pump.fun";
  resultContent.innerHTML = `
        ${tokenMetadataHTML}
        ${tokenCreationHTML}
        ${displayScore(score, failedMetrics)}
        ${displayLiquidityAnalysis(liquidity_sol)}
        ${displayInsiderAnalysis(
          data.data.phishy_count || 0,
          phishy_addresses || []
        )}
        ${displayHolderAnalysis(holder_analysis, top_holders)}
        ${topHoldersHTML}
    `;
}

function showError(message) {
  resultSection.style.display = "block";
  resultContent.innerHTML = `
        <div class="error-message">
            <strong>Error:</strong> ${message}
        </div>
    `;
}

function showInfoMessage(message) {
  resultSection.style.display = "block";
  resultContent.innerHTML = `
        <div style="background: var(--bg-secondary); border: 1px solid var(--accent-primary); border-radius: 8px; padding: 20px; text-align: center;">
            <div style="color: var(--accent-primary); font-size: 1.2rem; margin-bottom: 8px;">ℹ️</div>
            <div style="color: var(--text-primary); font-size: 1rem; font-weight: 500;">${message}</div>
        </div>
    `;
}

// Store current token type for formatting
let currentTokenType = "pumpfun";

function formatNumber(num) {
  if (!num || num === 0) return "0";
  const n = typeof num === "string" ? parseFloat(num) : num;

  // Pump.fun amounts are already decimal-adjusted
  if (currentTokenType === "pumpfun") {
    // Pump.fun: amounts are already in tokens, just format
    if (n >= 1000000000) {
      return (n / 1000000000).toFixed(2) + "B";
    } else if (n >= 1000000) {
      return (n / 1000000).toFixed(2) + "M";
    } else if (n >= 1000) {
      return (n / 1000).toFixed(2) + "K";
    } else {
      return n.toLocaleString("en-US", { maximumFractionDigits: 4 });
    }
  } else {
    // Pump.fun amounts are already decimal-adjusted
    const DECIMALS = 18;
    const divisor = Math.pow(10, DECIMALS);

    if (n >= divisor) {
      const inTokens = n / divisor;

      // Format in tokens
      if (inTokens >= 1000000000) {
        return (inTokens / 1000000000).toFixed(2) + "B";
      } else if (inTokens >= 1000000) {
        return (inTokens / 1000000).toFixed(2) + "M";
      } else if (inTokens >= 1000) {
        return (inTokens / 1000).toFixed(2) + "K";
      } else {
        return inTokens.toLocaleString("en-US", { maximumFractionDigits: 4 });
      }
    } else {
      // Very small amount, show in smallest unit
      if (n >= 1000000) {
        return (n / 1000000).toFixed(2) + "M (raw)";
      } else if (n >= 1000) {
        return (n / 1000).toFixed(2) + "K (raw)";
      }
      return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
    }
  }
}

function formatTimestamp(ts) {
  if (!ts) return "N/A";
  try {
    const date = new Date(ts);
    return date.toLocaleString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

function formatTimestampWithRelative(ts) {
  if (!ts) return "N/A";
  try {
    const date = new Date(ts);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    let relativeTime = "";
    if (diffDay > 0) {
      relativeTime = `${diffDay} ${diffDay === 1 ? "day" : "days"} ago`;
    } else if (diffHour > 0) {
      relativeTime = `${diffHour} ${diffHour === 1 ? "hour" : "hours"} ago`;
    } else if (diffMin > 0) {
      relativeTime = `${diffMin} ${diffMin === 1 ? "minute" : "minutes"} ago`;
    } else {
      relativeTime = "just now";
    }

    // Format: "03 Dec 2025 14:39:45 GMT (17 hours ago)"
    const day = String(date.getUTCDate()).padStart(2, "0");
    const months = [
      "Jan",
      "Feb",
      "Mar",
      "Apr",
      "May",
      "Jun",
      "Jul",
      "Aug",
      "Sep",
      "Oct",
      "Nov",
      "Dec",
    ];
    const month = months[date.getUTCMonth()];
    const year = date.getUTCFullYear();
    const hours = String(date.getUTCHours()).padStart(2, "0");
    const minutes = String(date.getUTCMinutes()).padStart(2, "0");
    const seconds = String(date.getUTCSeconds()).padStart(2, "0");

    const formattedDate = `${day} ${month} ${year} ${hours}:${minutes}:${seconds} GMT`;

    return `${formattedDate} (${relativeTime})`;
  } catch {
    return ts;
  }
}

function formatTransactionLink(signature) {
  if (!signature) return "N/A";
  const shortSig = `${signature.slice(0, 6)}...${signature.slice(-4)}`;
  const bitqueryLink = `https://explorer.bitquery.io/solana/tx/${signature}`;
  return `
        <a href="${bitqueryLink}" target="_blank" rel="noopener noreferrer" 
           style="color: var(--accent-primary); text-decoration: none; font-weight: 500;"
           onmouseover="this.style.textDecoration='underline'" 
           onmouseout="this.style.textDecoration='none'"
           title="View transaction on Bitquery: ${signature}">
            ${shortSig}
        </a>
    `;
}

function formatCreatorLink(address) {
  if (!address) return "N/A";
  return formatAddressWithLink(address);
}
