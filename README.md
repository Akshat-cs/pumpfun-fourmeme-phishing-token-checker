# Four.Meme Phishy Token Checker

This script checks if a Four Meme token on BSC (Binance Smart Chain) is potentially phishy by analyzing the relationship between token transfers and purchases.

## Quick Start

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Get Your Bitquery API Key

1. Go to [Bitquery GraphQL IDE](https://ide.bitquery.io/)
2. Sign up or log in to your account
3. Navigate to your account settings or API keys section
4. generate a Access Token and that is your API_KEY

### Step 3: Set Up Your API Key

Create a `.env` file with your API key:

```bash
cp .env.sample .env
```

Then edit `.env` and replace `your_api_key_here` with your actual API key:

```
BITQUERY_API_KEY=BQ_your_actual_api_key_here
```

### Step 4: Run the Analysis

You can use the script in two ways:

**Option 1: Web UI (Recommended)**

```bash
python app.py
```

Then open your browser and go to `http://localhost:5000`

**Option 2: Command Line**

```bash
python check_phishy_token.py 0x35a7bb282d8caafe71617c9d52ee30f1adfe4444
```

## How It Works

The script uses two Bitquery Four.meme APIs :

1. **First Query**: Gets the first transfers of a token to addresses, including total transferred amounts
2. **Second Query**: Checks if those addresses ever bought the token, when, and how much they bought

The analysis flags a token as phishy if:

- An address received a transfer but never bought the token
- An address's first transfer happened before their first buy

This pattern indicates that tokens were sent to addresses (often to influencers/KOLs) before they purchased, which is a common phishing/scam tactic to make the token look like a good buy.

The script also calculates **how much was transferred without being purchased** by subtracting `total_transferred - total_bought` for each suspicious address.

## Output

The script will output:

- Total number of addresses that received transfers
- Number of addresses with phishy behavior
- Number of addresses with normal behavior
- Detailed list of phishy addresses with:
  - Transfer and buy timestamps
  - Total amount transferred
  - Total amount bought
  - **Amount transferred without purchase** (key indicator)
- Summary of total amounts across all phishy addresses

### Example Output

`0x35a7bb282d8caafe71617c9d52ee30f1adfe4444` this token is not phishy, we have just shown what the terminal log will look like if the token would have been a phishy token.

```
============================================================
Checking token: 0x35a7bb282d8caafe71617c9d52ee30f1adfe4444
============================================================

Fetching first transfers for token: 0x35a7bb282d8caafe71617c9d52ee30f1adfe4444
Found 150 addresses that received transfers

Fetching first buys for 150 addresses...
Found buy records for 45 addresses

============================================================
RESULTS
============================================================

Total addresses that received transfers: 150
Addresses with phishy behavior: 105
Addresses with normal behavior: 45

⚠️  TOKEN IS PHISHY! ⚠️

Found 105 address(es) with suspicious behavior:

1. Address: 0x1234...
   First Transfer: 2024-01-15 10:30:00 UTC
   First Buy: N/A
   Total Transferred: 1,000,000.00
   Total Bought: 0
   ⚠️  Transferred Without Buy: 1,000,000.00 (This amount was sent but never purchased)
   Reason: Never bought the token

------------------------------------------------------------
SUMMARY OF PHISHY BEHAVIOR:
------------------------------------------------------------
Total Amount Transferred to Phishy Addresses: 5,000,000.00
Total Amount Bought by Phishy Addresses: 500,000.00
⚠️  Total Amount Transferred WITHOUT Purchase: 4,500,000.00
------------------------------------------------------------
```

## Troubleshooting

- **"Error: Bitquery API key is required"**: Make sure you've set up your `.env` file or provided the API key via command line
- **"No transfers found"**: The token might not have any transfers yet, or the address might be incorrect
- **API errors**: Check that your API key is valid and you have sufficient credits on Bitquery
- **Slow queries**: The queries can take 10-60+ seconds depending on data size. This is normal for complex blockchain queries

## Web UI

The project includes a modern web3-styled web interface for easy token checking:

1. Start the web server:

   ```bash
   python app.py
   ```

2. Open your browser and navigate to `http://localhost:8080` (or the port shown in the terminal)

3. Enter a token address and optionally your API key (if not in .env)

4. Click "Check Token" to analyze

The web UI features:

- Modern web3 design with dark theme
- Real-time analysis results
- Detailed breakdown of phishy addresses
- Summary statistics
- Responsive design for mobile and desktop

## Notes

- The script checks up to 1000 addresses (limit in Query 1)
- Requires network connection to access Bitquery API
- **API key is required** - Bitquery API requires authentication
- The script focuses on BSC network and FourMeme protocol trades
- The `.env` file is gitignored and won't be committed to the repository
- Queries may take some time to execute (10-60+ seconds) - this is normal for blockchain data queries
- The web UI runs on port 8080 by default (set PORT environment variable to change, e.g., `PORT=3000 python app.py`)
