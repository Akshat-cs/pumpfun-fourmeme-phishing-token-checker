#!/usr/bin/env python3
"""
Flask web application for checking phishy tokens.
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from check_phishy_token import (
    get_first_transfers_pumpfun, get_first_buys_pumpfun, analyze_phishy_behavior_pumpfun,
    get_bonding_curve_address, get_top_holders_pumpfun, get_pump_tokens_count, get_trades_count_last_6h,
    analyze_holder_distribution, fetch_ipfs_metadata, MAYHEM_AI_AGENT_ADDRESS, get_liquidity_for_pool,
    check_token_graduated
)
from collections import deque
from datetime import datetime

# Load environment variables
load_dotenv()

# Application root path for subpath deployment
APPLICATION_ROOT = '/pumpfun-token-sniffer'

app = Flask(__name__)
CORS(app)

# Configure application root for subpath deployment
app.config['APPLICATION_ROOT'] = APPLICATION_ROOT

# Get API key from environment
API_KEY = os.getenv("BITQUERY_API_KEY")

# Cache for last 100 phishy tokens (memory efficient - only stores phishy ones)
# Each entry: {token_address, phishy_count, timestamp, totals}
phishy_tokens_cache = deque(maxlen=100)


@app.route('/')
@app.route(f'{APPLICATION_ROOT}/')
def index():
    """Serve the main page."""
    return render_template('index.html', base_path=APPLICATION_ROOT)


@app.route(f'{APPLICATION_ROOT}/api/recent-phishy', methods=['GET'])
def get_recent_phishy():
    """Get recent phishy tokens from cache."""
    # Convert deque to list (most recent first)
    recent = list(phishy_tokens_cache)
    recent.reverse()  # Most recent first
    return jsonify({
        'success': True,
        'tokens': recent,
        'count': len(recent)
    })


def validate_solana_address(token_address: str) -> bool:
    """Validate if address is a valid Solana address format."""
    # Solana addresses are base58 encoded, typically 32-44 characters, don't start with 0x
    return not token_address.startswith('0x') and len(token_address) >= 32 and len(token_address) <= 44


@app.route(f'{APPLICATION_ROOT}/api/check', methods=['POST'])
def check_token():
    """API endpoint to check if a token is phishy."""
    try:
        data = request.get_json()
        token_address = data.get('token_address', '').strip()
        bonding_curve = data.get('bonding_curve', '').strip()  # For Pump.fun tokens
        token_type = data.get('token_type', '').strip().lower()  # Allow manual override
        
        if not token_address:
            return jsonify({
                'success': False,
                'error': 'Token address is required'
            }), 400
        
        if not API_KEY:
            return jsonify({
                'success': False,
                'error': 'Server configuration error: API key not found. Please contact the administrator.'
            }), 500
        
        # Validate Solana address format
        if not validate_solana_address(token_address):
            return jsonify({
                'success': False,
                'error': 'Invalid Pump.fun token address. Solana addresses should be 32-44 characters and not start with 0x.',
                'error_type': 'info'
            }), 400
        
        # All tokens are Pump.fun (Solana)
        # Pump.fun token - automatically find bonding curve
        bonding_curve_data = None
        if not bonding_curve:
            bonding_curve_data = get_bonding_curve_address(token_address, API_KEY)
            if not bonding_curve_data:
                return jsonify({
                    'success': False,
                    'error': 'App provides analysis only on recent tokens',
                    'error_type': 'info'
                }), 400
            
            # Extract bonding curve from the returned dict
            if isinstance(bonding_curve_data, dict):
                bonding_curve = bonding_curve_data.get("bonding_curve")
            else:
                bonding_curve = bonding_curve_data
        
        # Check if token has graduated to PumpSwap
        if bonding_curve:
            has_graduated = check_token_graduated(token_address, API_KEY)
            if has_graduated:
                return jsonify({
                    'success': False,
                    'error': 'This Pump.fun token has graduated to PumpSwap. We only support token which are trading on pump fun currently.',
                    'error_type': 'info'
                }), 400
        
        # Initialize liquidity_sol early
        liquidity_sol = None
        
        # Get top 10 holders with their stats
        top_holders = get_top_holders_pumpfun(token_address, API_KEY)
        
        # Get is_mayhem_mode from bonding_curve_data if available
        is_mayhem_mode = False
        if bonding_curve_data and isinstance(bonding_curve_data, dict):
            is_mayhem_mode = bonding_curve_data.get('is_mayhem_mode', False)
        
        # Calculate total supply based on Mayhem mode
        total_supply = 2_000_000_000 if is_mayhem_mode else 1_000_000_000
        
        holders_with_stats = []
        for holder in top_holders:
            address = holder["address"]
            pump_tokens = get_pump_tokens_count(address, API_KEY)
            trades_6h = get_trades_count_last_6h(address, API_KEY)
            
            # Calculate percentage holding
            holding = float(holder.get("holding", 0) or 0)
            percent_holding = (holding / total_supply) * 100 if total_supply > 0 else 0
            
            holders_with_stats.append({
                "address": address,
                "holding": holder["holding"],
                "percent_holding": round(percent_holding, 2),
                "pump_tokens_count": pump_tokens,
                "trades_6h": trades_6h
            })
        
        # Print top 10 holders after calculation
        print("\n" + "="*80)
        print("TOP 10 HOLDERS (After Calculation):")
        print("="*80)
        for i, holder_stat in enumerate(holders_with_stats, 1):
            print(f"#{i} Address: {holder_stat['address']}")
            print(f"   Holding: {holder_stat.get('holding', 0)}")
            print(f"   Pump.Fun tokens held: {holder_stat['pump_tokens_count']}")
            print(f"   Trades (last 6h): {holder_stat['trades_6h']}")
            print()
        print("="*80 + "\n")
        
        transfers = get_first_transfers_pumpfun(token_address, bonding_curve, API_KEY)
        
        # Extract token creation info and metadata from bonding_curve_data
        token_creation_info = {}
        token_metadata = {}
        creator_address = None
        if bonding_curve_data and isinstance(bonding_curve_data, dict):
            token_creation_info = {
                'transaction_signature': bonding_curve_data.get('transaction_signature'),
                'creator_address': bonding_curve_data.get('creator_address'),
                'creation_time': bonding_curve_data.get('creation_time')
            }
            creator_address = bonding_curve_data.get('creator_address')
            
            # Extract token metadata
            token_uri = bonding_curve_data.get('token_uri')
            token_metadata = {
                'name': bonding_curve_data.get('token_name'),
                'symbol': bonding_curve_data.get('token_symbol'),
                'is_mayhem_mode': bonding_curve_data.get('is_mayhem_mode', False),
                'uri': token_uri
            }
            
            # Fetch IPFS metadata if URI is available
            if token_uri:
                ipfs_metadata = fetch_ipfs_metadata(token_uri)
                if ipfs_metadata:
                    token_metadata['image'] = ipfs_metadata.get('image')
                    token_metadata['twitter'] = ipfs_metadata.get('twitter')
                    token_metadata['website'] = ipfs_metadata.get('website')
                    token_metadata['description'] = ipfs_metadata.get('description', '')
                    token_metadata['telegram'] = ipfs_metadata.get('telegram')
        
        # Get liquidity for the pool (if not already fetched)
        if bonding_curve and liquidity_sol is None:
            liquidity_sol = get_liquidity_for_pool(bonding_curve, API_KEY)
        
        # Get holder analysis
        holder_analysis = analyze_holder_distribution(
            token_address, creator_address, bonding_curve, is_mayhem_mode, API_KEY
        )
        
        if not transfers:
            return jsonify({
                'success': True,
                'phishy': False,
                'token_type': 'pumpfun',
                'message': 'No transfers found for this token',
                'data': {
                    'total_addresses': 0,
                    'phishy_count': 0,
                    'phishy_addresses': [],
                    'top_holders': holders_with_stats,
                    'bonding_curve': bonding_curve,
                    'mayhem_ai_agent': MAYHEM_AI_AGENT_ADDRESS,
                    'token_creation': token_creation_info,
                    'token_metadata': token_metadata,
                    'holder_analysis': holder_analysis,
                    'liquidity_sol': liquidity_sol
                }
            })
        
        # Extract addresses from Solana structure
        addresses = [t["Transfer"]["Receiver"]["Token"]["Owner"] for t in transfers]
        buy_data = get_first_buys_pumpfun(token_address, addresses, API_KEY)
        phishy_count, phishy_addresses = analyze_phishy_behavior_pumpfun(transfers, buy_data)
        
        # Ensure top holders are fetched (they should already be, but just in case)
        if not holders_with_stats:
            top_holders = get_top_holders_pumpfun(token_address, API_KEY)
            holders_with_stats = []
            for holder in top_holders:
                address = holder["address"]
                pump_tokens = get_pump_tokens_count(address, API_KEY)
                trades_6h = get_trades_count_last_6h(address, API_KEY)
                holders_with_stats.append({
                    "address": address,
                    "holding": holder["holding"],
                    "pump_tokens_count": pump_tokens,
                    "trades_6h": trades_6h
                })
        
        # Format response
        result = {
            'success': True,
            'phishy': phishy_count > 0,
            'token_address': token_address,
            'token_type': 'pumpfun',
            'data': {
                'total_addresses': len(transfers),
                'phishy_count': phishy_count,
                'normal_count': len(transfers) - phishy_count,
                'phishy_addresses': phishy_addresses,
                'top_holders': holders_with_stats,
                'bonding_curve': bonding_curve,
                'mayhem_ai_agent': MAYHEM_AI_AGENT_ADDRESS,
                'token_creation': token_creation_info,
                'token_metadata': token_metadata,
                'holder_analysis': holder_analysis,
                'liquidity_sol': liquidity_sol
            }
        }
        
        # Calculate totals
        if phishy_count > 0:
            total_transferred = sum(
                float(addr.get('total_transferred', 0) or 0) 
                for addr in phishy_addresses
            )
            total_bought = sum(
                float(addr.get('total_bought', 0) or 0) 
                for addr in phishy_addresses
            )
            total_without_buy = sum(
                float(addr.get('transferred_without_buy', 0) or 0) 
                for addr in phishy_addresses
            )
            
            result['data']['totals'] = {
                'total_transferred': total_transferred,
                'total_bought': total_bought,
                'total_without_buy': total_without_buy
            }
            
            # Store in cache (only phishy tokens)
            phishy_tokens_cache.append({
                'token_address': token_address,
                'token_type': 'pumpfun',
                'phishy_count': phishy_count,
                'timestamp': datetime.now().isoformat(),
                'totals': result['data']['totals']
            })
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"\n🚀 Server starting on http://localhost:{port}")
    print(f"📱 Open your browser and navigate to the URL above\n")
    app.run(host='0.0.0.0', port=port, debug=True)

