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
    get_bonding_curve_address, get_top_holders_pumpfun, get_pump_tokens_count, get_trades_count_last_6h
)
from collections import deque
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Get API key from environment
API_KEY = os.getenv("BITQUERY_API_KEY")

# Cache for last 100 phishy tokens (memory efficient - only stores phishy ones)
# Each entry: {token_address, phishy_count, timestamp, totals}
phishy_tokens_cache = deque(maxlen=100)


@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


@app.route('/api/recent-phishy', methods=['GET'])
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


@app.route('/api/check', methods=['POST'])
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
        if not bonding_curve:
            bonding_curve = get_bonding_curve_address(token_address, API_KEY)
            if not bonding_curve:
                return jsonify({
                    'success': False,
                    'error': 'We only support tokens created in the last 8 hours',
                    'error_type': 'info'
                }), 400
            
        # Get top 10 holders with their stats
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
                    'bonding_curve': bonding_curve
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
                'bonding_curve': bonding_curve
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

