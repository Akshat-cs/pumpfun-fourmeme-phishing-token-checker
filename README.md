# Pump.fun Phishy Token Checker

This tool checks if a Pump.fun token (Solana) is potentially phishy by analyzing the relationship between token transfers and purchases.

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

Then open your browser and go to `http://localhost:8080`

**Option 2: Command Line**

```bash
python check_phishy_token.py WZrxegwJK4vWFGC149Ajt86vbKA9tsrJxu8mJFdpump
```

Note: Bonding curve is automatically detected.

## How It Works

The tool analyzes token transfers vs purchases using Bitquery APIs:

1. **First Query**: Gets the first transfers of a token to addresses
2. **Second Query**: Checks if those addresses ever bought the token

A token is flagged as phishy if:

- An address received a transfer but never bought the token
- An address's first transfer happened before their first buy

The tool also:

- Automatically finds the bonding curve address
- Shows top 10 holders with their pump token counts and trade activity (last 6h)

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

```
============================================================
Checking Pump.fun token: WZrxegwJK4vWFGC149Ajt86vbKA9tsrJxu8mJFdpump
============================================================

Finding bonding curve address...
Found bonding curve: ABC123...

Found 150 addresses that received transfers

Found buy records for 45 addresses

============================================================
RESULTS
============================================================

Total addresses that received transfers: 150
Addresses with phishy behavior: 105
Addresses with normal behavior: 45

⚠️  TOKEN IS PHISHY! ⚠️

Found 105 address(es) with suspicious behavior:

1. Address: ABC123...
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

3. Enter a Pump.fun token address

4. Click "Check Token" to analyze

The web UI features:

- Modern web3 design with dark theme
- Automatic bonding curve detection
- Top 10 holders table (with pump token counts and trade stats)
- Clickable addresses linking to DEXrabbit
- Copy-to-clipboard functionality for addresses
- Detailed breakdown of phishy addresses
- Summary statistics
- Responsive design

## Notes

- Checks up to 1000 addresses per token
- Only supports Pump.fun tokens (Solana)
- Bonding curve is automatically detected
- Only supports tokens created in the last 8 hours
- API key is required (set in `.env` file)
- Queries may take 10-60+ seconds (normal for blockchain data)
- Web UI runs on port 8080 by default
