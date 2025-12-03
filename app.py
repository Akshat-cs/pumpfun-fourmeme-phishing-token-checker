#!/usr/bin/env python3
"""
Flask web application for checking phishy tokens.
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from check_phishy_token import (
    get_first_transfers, get_first_buys, analyze_phishy_behavior,
    get_first_transfers_pumpfun, get_first_buys_pumpfun, analyze_phishy_behavior_pumpfun
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


def detect_token_type(token_address: str) -> str:
    """Detect if token is BSC (Four.Meme) or Solana (Pump.fun) based on address format."""
    # Solana addresses are base58 encoded, typically 32-44 characters
    # BSC addresses are hex, start with 0x and are 42 characters
    if token_address.startswith('0x') and len(token_address) == 42:
        return 'bsc'
    # Solana addresses are longer and don't start with 0x
    elif len(token_address) >= 32 and len(token_address) <= 44:
        return 'solana'
    else:
        # Default to BSC for unknown format
        return 'bsc'


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
        
        # Detect token type if not provided
        if not token_type:
            token_type = detect_token_type(token_address)
        
        # Route to appropriate functions based on token type
        if token_type == 'solana' or token_type == 'pumpfun':
            # Pump.fun (Solana) token - requires bonding curve address
            if not bonding_curve:
                return jsonify({
                    'success': False,
                    'error': 'Bonding curve address is required for Pump.fun tokens'
                }), 400
            
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
                        'phishy_addresses': []
                    }
                })
            
            # Extract addresses from Solana structure
            addresses = [t["Transfer"]["Receiver"]["Token"]["Owner"] for t in transfers]
            buy_data = get_first_buys_pumpfun(token_address, addresses, API_KEY)
            phishy_count, phishy_addresses = analyze_phishy_behavior_pumpfun(transfers, buy_data)
        else:
            # Four.Meme (BSC) token
            transfers = get_first_transfers(token_address, API_KEY)
            
            if not transfers:
                return jsonify({
                    'success': True,
                    'phishy': False,
                    'token_type': 'fourmeme',
                    'message': 'No transfers found for this token',
                    'data': {
                        'total_addresses': 0,
                        'phishy_count': 0,
                        'phishy_addresses': []
                    }
                })
            
            addresses = [t["Transfer"]["Receiver"] for t in transfers]
            buy_data = get_first_buys(token_address, addresses, API_KEY)
            phishy_count, phishy_addresses = analyze_phishy_behavior(transfers, buy_data)
        
        # Format response
        result = {
            'success': True,
            'phishy': phishy_count > 0,
            'token_address': token_address,
            'token_type': 'pumpfun' if (token_type == 'solana' or token_type == 'pumpfun') else 'fourmeme',
            'data': {
                'total_addresses': len(transfers),
                'phishy_count': phishy_count,
                'normal_count': len(transfers) - phishy_count,
                'phishy_addresses': phishy_addresses
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
                'token_type': result.get('token_type', 'fourmeme'),
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

