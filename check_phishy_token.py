#!/usr/bin/env python3
"""
Script to check if a Four Meme token or Pump.fun token is phishy by analyzing transfers vs purchases.
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Bitquery API endpoint
BITQUERY_API_URL = "https://streaming.bitquery.io/graphql"


def make_graphql_request(query: str, variables: Dict, api_key: str) -> Dict:
    """
    Make a GraphQL request to Bitquery API.
    
    Args:
        query: GraphQL query string
        variables: Variables for the query
        api_key: API key for authentication (required)
    
    Returns:
        Response data as dictionary
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "query": query,
        "variables": variables
    }
    
    try:
        response = requests.post(BITQUERY_API_URL, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        result = response.json()
        
        # Check for GraphQL errors in response
        if "errors" in result:
            print(f"GraphQL Errors: {json.dumps(result['errors'], indent=2)}")
            return result
        
        return result
    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"Error response: {json.dumps(error_data, indent=2)}")
            except:
                print(f"Response text: {e.response.text}")
        sys.exit(1)


def get_first_transfers(token_address: str, api_key: str) -> List[Dict]:
    """
    Query 1: Get the first transfers of a token to addresses.
    
    Args:
        token_address: The token contract address to check
        api_key: API key for authentication (required)
    
    Returns:
        List of dictionaries containing receiver address, first transfer timestamp, and total transferred amount
    """
    query = """
    query MyQuery($token: String) {
      EVM(network: bsc, dataset: realtime) {
        Transfers(
          limit: { count: 1000 }
          orderBy: { ascendingByField: "Block_first_transfer" }
          where: {
            TransactionStatus: { Success: true }
            Transfer: {
              Receiver: { notIn:["0x5c952063c7fc8610ffdb798152d69f0b9550762b","0x757eba15a64468e6535532fcF093Cef90e226F85"] }
              Currency: { SmartContract: { is: $token } }
            }
          }
        ) {
          Transfer {
            Receiver
          }
          Block {
            first_transfer: Time(minimum: Block_Time)
          }
          total_transferred_amount: sum(of: Transfer_Amount)
        }
      }
    }
    """
    
    variables = {
        "token": token_address
    }
    
    print(f"Fetching first transfers for token: {token_address}")
    response = make_graphql_request(query, variables, api_key)
    
    # Extract data from response
    if "data" in response:
        evm_data = response["data"].get("EVM")
        if evm_data:
            # EVM can be a list or a single object
            if isinstance(evm_data, list) and len(evm_data) > 0:
                transfers = evm_data[0].get("Transfers", [])
            elif isinstance(evm_data, dict):
                transfers = evm_data.get("Transfers", [])
            else:
                transfers = []
            
            if transfers:
                return transfers
    
    # If we get here, there was an issue
    if "errors" in response:
        print(f"Query errors: {json.dumps(response['errors'], indent=2)}")
    else:
        print(f"Unexpected response structure: {json.dumps(response, indent=2)}")
    return []


def get_first_buys(token_address: str, buyers_list: List[str], api_key: str) -> Dict[str, Dict]:
    """
    Query 2: Get first buys of an address list for a specific token.
    
    Args:
        token_address: The token contract address
        buyers_list: List of addresses to check
        api_key: API key for authentication (required)
    
    Returns:
        Dictionary mapping address to buy information (timestamp and amount)
    """
    if not buyers_list:
        return {}
    
    query = """
    query MyQuery($token: String!, $buyersList: [String!]) {
      EVM(network: bsc, dataset: realtime) {
        DEXTradeByTokens(
          orderBy: { descendingByField: "Block_first_buy" }
          where: {
            Trade: {
              Currency: { SmartContract: { is: $token } }
              Side: { Type: { is: buy } }
              Buyer: { in: $buyersList }
            }
            TransactionStatus: { Success: true }
          }
        ) {
          Trade {
            Buyer
            Currency {
              Name
              Symbol
              SmartContract
            }
            Side {
              Type
            }
          }
          Block {
            first_buy: Time(minimum: Block_Time)
          }
          total_bought_amount: sum(of: Trade_Amount)
        }
      }
    }
    """
    
    variables = {
        "token": token_address,
        "buyersList": buyers_list
    }
    
    print(f"Fetching first buys for {len(buyers_list)} addresses...")
    response = make_graphql_request(query, variables, api_key)
    
    # Extract data from response and organize by address
    buy_data = {}
    if "data" in response:
        evm_data = response["data"].get("EVM")
        if evm_data:
            # EVM can be a list or a single object
            if isinstance(evm_data, list) and len(evm_data) > 0:
                trades = evm_data[0].get("DEXTradeByTokens", [])
            elif isinstance(evm_data, dict):
                trades = evm_data.get("DEXTradeByTokens", [])
            else:
                trades = []
            
            for trade in trades:
                buyer = trade["Trade"]["Buyer"]
                first_buy_time = trade["Block"].get("first_buy")
                total_amount = trade.get("total_bought_amount", 0)
                
                buy_data[buyer] = {
                    "first_buy_time": first_buy_time,
                    "total_amount": total_amount
                }
    
    return buy_data


def analyze_phishy_behavior(transfers: List[Dict], buy_data: Dict[str, Dict]) -> Tuple[int, List[Dict]]:
    """
    Analyze transfers vs buys to detect phishy behavior.
    
    Args:
        transfers: List of transfer records from Query 1
        buy_data: Dictionary of buy records from Query 2
    
    Returns:
        Tuple of (count of phishy addresses, list of phishy address details)
    """
    phishy_addresses = []
    
    for transfer in transfers:
        receiver = transfer["Transfer"]["Receiver"]
        first_transfer_time = transfer["Block"].get("first_transfer")
        total_transferred = transfer.get("total_transferred_amount", 0)
        
        # Check if address ever bought the token
        buy_info = buy_data.get(receiver)
        
        # Calculate amounts
        total_bought = buy_info.get("total_amount", 0) if buy_info else 0
        
        # Convert to float for calculation
        try:
            transferred_float = float(total_transferred) if total_transferred else 0.0
            bought_float = float(total_bought) if total_bought else 0.0
            transferred_without_buy = transferred_float - bought_float
        except (ValueError, TypeError):
            transferred_float = 0.0
            bought_float = 0.0
            transferred_without_buy = 0.0
        
        if buy_info is None:
            # Address never bought - phishy!
            phishy_addresses.append({
                "address": receiver,
                "first_transfer_time": first_transfer_time,
                "first_buy_time": None,
                "total_transferred": total_transferred,
                "total_bought": 0,
                "transferred_without_buy": transferred_float,
                "reason": "Never bought the token"
            })
        else:
            first_buy_time = buy_info.get("first_buy_time")
            
            if first_buy_time is None:
                # Address has buy record but no timestamp - treat as phishy
                phishy_addresses.append({
                    "address": receiver,
                    "first_transfer_time": first_transfer_time,
                    "first_buy_time": None,
                    "total_transferred": total_transferred,
                    "total_bought": total_bought,
                    "transferred_without_buy": transferred_without_buy,
                    "reason": "Buy record exists but no timestamp"
                })
            else:
                # Compare timestamps
                # Convert to datetime for comparison if they're strings
                try:
                    if isinstance(first_transfer_time, str):
                        transfer_dt = datetime.fromisoformat(first_transfer_time.replace('Z', '+00:00'))
                    else:
                        transfer_dt = first_transfer_time
                    
                    if isinstance(first_buy_time, str):
                        buy_dt = datetime.fromisoformat(first_buy_time.replace('Z', '+00:00'))
                    else:
                        buy_dt = first_buy_time
                    
                    if transfer_dt < buy_dt:
                        # Transfer happened before buy - phishy!
                        phishy_addresses.append({
                            "address": receiver,
                            "first_transfer_time": first_transfer_time,
                            "first_buy_time": first_buy_time,
                            "total_transferred": total_transferred,
                            "total_bought": total_bought,
                            "transferred_without_buy": transferred_without_buy,
                            "reason": f"Transfer before buy (transfer: {first_transfer_time}, buy: {first_buy_time})"
                        })
                except (ValueError, TypeError) as e:
                    # If timestamp parsing fails, do string comparison
                    if first_transfer_time and first_buy_time:
                        if first_transfer_time < first_buy_time:
                            phishy_addresses.append({
                                "address": receiver,
                                "first_transfer_time": first_transfer_time,
                                "first_buy_time": first_buy_time,
                                "total_transferred": total_transferred,
                                "total_bought": total_bought,
                                "transferred_without_buy": transferred_without_buy,
                                "reason": "Transfer before buy (string comparison)"
                            })
    
    return len(phishy_addresses), phishy_addresses


def get_first_transfers_pumpfun(token_address: str, bonding_curve: str, api_key: str) -> List[Dict]:
    """
    Query 1: Get the first transfers of a Pump.fun token to addresses (Solana).
    
    Args:
        token_address: The token mint address to check
        bonding_curve: The bonding curve program address (to exclude from transfers)
        api_key: API key for authentication (required)
    
    Returns:
        List of dictionaries containing receiver address, first transfer timestamp, and total transferred amount
    """
    query = """
    query MyQuery($token: String, $bonding_curve: String) {
      Solana {
        Transfers(
          limit: { count: 1000 }
          orderBy: { ascendingByField: "Block_first_transfer" }
          where: {
            Transfer: {
              Receiver: { Token: { Owner: { not: $bonding_curve notIn:["8psNvWTrdNTiVRNzAgsou9kETXNJm2SXZyaKuJraVRtf","AkTgH1uW6J6j6QHmFNGzZuZwwXaHQsPCpHUriED28tRj"] } } }
              Currency: { MintAddress: { is: $token } }
            }
            Transaction: { Result: { Success: true } }
          }
        ) {
          Transfer {
            Receiver {
              Token {
                Owner
              }
            }
          }
          Block {
            first_transfer: Time(minimum: Block_Time)
          }
          total_transferred_amount: sum(of: Transfer_Amount)
        }
      }
    }
    """
    
    variables = {
        "token": token_address,
        "bonding_curve": bonding_curve
    }
    
    print(f"Fetching first transfers for Pump.fun token: {token_address}")
    print(f"Excluding bonding curve: {bonding_curve}")
    response = make_graphql_request(query, variables, api_key)
    
    # Extract data from response
    if "data" in response:
        solana_data = response["data"].get("Solana")
        if solana_data:
            # Solana can be a list or a single object
            if isinstance(solana_data, list) and len(solana_data) > 0:
                transfers = solana_data[0].get("Transfers", [])
            elif isinstance(solana_data, dict):
                transfers = solana_data.get("Transfers", [])
            else:
                transfers = []
            
            if transfers:
                return transfers
    
    # If we get here, there was an issue
    if "errors" in response:
        print(f"Query errors: {json.dumps(response['errors'], indent=2)}")
    else:
        print(f"Unexpected response structure: {json.dumps(response, indent=2)}")
    return []


def get_first_buys_pumpfun(token_address: str, buyers_list: List[str], api_key: str) -> Dict[str, Dict]:
    """
    Query 2: Get first buys of an address list for a specific Pump.fun token (Solana).
    
    Args:
        token_address: The token mint address
        buyers_list: List of addresses to check
        api_key: API key for authentication (required)
    
    Returns:
        Dictionary mapping address to buy information (timestamp and amount)
    """
    if not buyers_list:
        return {}
    
    query = """
    query MyQuery($token: String!, $buyersList: [String!]) {
      Solana {
        DEXTradeByTokens(
          orderBy: { ascendingByField: "Block_first_buy" }
          where: {
            Trade: {
              Account: { Token: { Owner: { in: $buyersList } } }
              Currency: { MintAddress: { is: $token } }
              Side: { Type: { is: buy } }
            }
            Transaction: { Result: { Success: true } }
          }
        ) {
          Trade {
            Account {
              Token {
                Owner
              }
            }
            Currency {
              Name
              Symbol
              MintAddress
            }
            Side {
              Type
            }
          }
          Block {
            first_buy: Time(minimum: Block_Time)
          }
          total_bought_amount: sum(of: Trade_Amount)
        }
      }
    }
    """
    
    variables = {
        "token": token_address,
        "buyersList": buyers_list
    }
    
    print(f"Fetching first buys for {len(buyers_list)} addresses (Pump.fun)...")
    response = make_graphql_request(query, variables, api_key)
    
    # Extract data from response and organize by address
    buy_data = {}
    if "data" in response:
        solana_data = response["data"].get("Solana")
        if solana_data:
            # Solana can be a list or a single object
            if isinstance(solana_data, list) and len(solana_data) > 0:
                trades = solana_data[0].get("DEXTradeByTokens", [])
            elif isinstance(solana_data, dict):
                trades = solana_data.get("DEXTradeByTokens", [])
            else:
                trades = []
            
            for trade in trades:
                buyer = trade["Trade"]["Account"]["Token"]["Owner"]
                first_buy_time = trade["Block"].get("first_buy")
                total_amount = trade.get("total_bought_amount", 0)
                
                buy_data[buyer] = {
                    "first_buy_time": first_buy_time,
                    "total_amount": total_amount
                }
    
    return buy_data


def analyze_phishy_behavior_pumpfun(transfers: List[Dict], buy_data: Dict[str, Dict]) -> Tuple[int, List[Dict]]:
    """
    Analyze transfers vs buys to detect phishy behavior for Pump.fun tokens.
    
    Args:
        transfers: List of transfer records from Query 1
        buy_data: Dictionary of buy records from Query 2
    
    Returns:
        Tuple of (count of phishy addresses, list of phishy address details)
    """
    phishy_addresses = []
    
    for transfer in transfers:
        # Extract receiver from Solana structure
        receiver = transfer["Transfer"]["Receiver"]["Token"]["Owner"]
        first_transfer_time = transfer["Block"].get("first_transfer")
        total_transferred = transfer.get("total_transferred_amount", 0)
        
        # Check if address ever bought the token
        buy_info = buy_data.get(receiver)
        
        # Calculate amounts
        total_bought = buy_info.get("total_amount", 0) if buy_info else 0
        
        # Convert to float for calculation (amounts are already decimal-adjusted for Solana)
        try:
            transferred_float = float(total_transferred) if total_transferred else 0.0
            bought_float = float(total_bought) if total_bought else 0.0
            transferred_without_buy = transferred_float - bought_float
        except (ValueError, TypeError):
            transferred_float = 0.0
            bought_float = 0.0
            transferred_without_buy = 0.0
        
        if buy_info is None:
            # Address never bought - phishy!
            phishy_addresses.append({
                "address": receiver,
                "first_transfer_time": first_transfer_time,
                "first_buy_time": None,
                "total_transferred": total_transferred,
                "total_bought": 0,
                "transferred_without_buy": transferred_float,
                "reason": "Never bought the token"
            })
        else:
            first_buy_time = buy_info.get("first_buy_time")
            
            if first_buy_time is None:
                # Address has buy record but no timestamp - treat as phishy
                phishy_addresses.append({
                    "address": receiver,
                    "first_transfer_time": first_transfer_time,
                    "first_buy_time": None,
                    "total_transferred": total_transferred,
                    "total_bought": total_bought,
                    "transferred_without_buy": transferred_without_buy,
                    "reason": "Buy record exists but no timestamp"
                })
            else:
                # Compare timestamps
                try:
                    if isinstance(first_transfer_time, str):
                        transfer_dt = datetime.fromisoformat(first_transfer_time.replace('Z', '+00:00'))
                    else:
                        transfer_dt = first_transfer_time
                    
                    if isinstance(first_buy_time, str):
                        buy_dt = datetime.fromisoformat(first_buy_time.replace('Z', '+00:00'))
                    else:
                        buy_dt = first_buy_time
                    
                    if transfer_dt < buy_dt:
                        # Transfer happened before buy - phishy!
                        phishy_addresses.append({
                            "address": receiver,
                            "first_transfer_time": first_transfer_time,
                            "first_buy_time": first_buy_time,
                            "total_transferred": total_transferred,
                            "total_bought": total_bought,
                            "transferred_without_buy": transferred_without_buy,
                            "reason": f"Transfer before buy (transfer: {first_transfer_time}, buy: {first_buy_time})"
                        })
                except (ValueError, TypeError) as e:
                    # If timestamp parsing fails, do string comparison
                    if first_transfer_time and first_buy_time:
                        if first_transfer_time < first_buy_time:
                            phishy_addresses.append({
                                "address": receiver,
                                "first_transfer_time": first_transfer_time,
                                "first_buy_time": first_buy_time,
                                "total_transferred": total_transferred,
                                "total_bought": total_bought,
                                "transferred_without_buy": transferred_without_buy,
                                "reason": "Transfer before buy (string comparison)"
                            })
    
    return len(phishy_addresses), phishy_addresses


def format_timestamp(ts: Optional[str]) -> str:
    """Format timestamp for display."""
    if ts is None:
        return "N/A"
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except:
        return str(ts)


def main():
    """Main function to run the phishy token check."""
    # Parse command line arguments
    token_address = None
    bonding_curve = None
    api_key = None
    
    # Check for command line arguments
    # Format: python check_phishy_token.py <token_address> [bonding_curve] [api_key]
    if len(sys.argv) >= 2:
        token_address = sys.argv[1]
    if len(sys.argv) >= 3:
        # Check if arg 2 is bonding curve (Solana) or API key (BSC)
        arg2 = sys.argv[2]
        if not arg2.startswith('0x') and len(arg2) >= 32 and len(arg2) <= 44:
            # Likely a bonding curve address
            bonding_curve = arg2
            if len(sys.argv) >= 4:
                api_key = sys.argv[3]
        else:
            # Likely an API key
            api_key = arg2
    
    # Get token address if not provided
    if not token_address:
        token_address = input("Enter the token address to check: ").strip()
    
    if not token_address:
        print("Error: Token address is required")
        sys.exit(1)
    
    # Detect token type
    if token_address.startswith('0x') and len(token_address) == 42:
        token_type = 'bsc'
        token_type_label = 'Four.Meme (BSC)'
    elif len(token_address) >= 32 and len(token_address) <= 44:
        token_type = 'solana'
        token_type_label = 'Pump.fun (Solana)'
        # For Pump.fun, require bonding curve address
        if not bonding_curve:
            bonding_curve = input("Enter the bonding curve program address: ").strip()
        if not bonding_curve:
            print("Error: Bonding curve address is required for Pump.fun tokens")
            sys.exit(1)
    else:
        print("Error: Invalid token address format")
        print("BSC addresses should start with 0x and be 42 characters")
        print("Solana addresses should be 32-44 characters")
        sys.exit(1)
    
    # Get API key (priority: command line > .env file > environment variable > prompt)
    if not api_key:
        api_key = os.getenv("BITQUERY_API_KEY")
    
    # Prompt for API key if still not found
    if not api_key:
        api_key = input("Enter your Bitquery API key: ").strip()
    
    if not api_key:
        print("Error: Bitquery API key is required")
        print("You can provide it via:")
        print("  1. Command line: python check_phishy_token.py <token_address> [bonding_curve] <api_key>")
        print("  2. .env file: Create a .env file with BITQUERY_API_KEY=your_key_here")
        print("  3. Environment variable: export BITQUERY_API_KEY='your_key_here'")
        print("  4. Interactive prompt (when running the script)")
        print("\nSee .env.sample for an example.")
        sys.exit(1)
    
    print("\n" + "="*60)
    print(f"Checking token: {token_address}")
    print(f"Token Type: {token_type_label}")
    if token_type == 'solana':
        print(f"Bonding Curve: {bonding_curve}")
    print("="*60 + "\n")
    
    # Step 1: Get first transfers
    if token_type == 'solana':
        transfers = get_first_transfers_pumpfun(token_address, bonding_curve, api_key)
    else:
        transfers = get_first_transfers(token_address, api_key)
    
    if not transfers:
        print("No transfers found for this token.")
        return
    
    print(f"Found {len(transfers)} addresses that received transfers\n")
    
    # Extract address list (different structure for Solana vs BSC)
    if token_type == 'solana':
        addresses = [t["Transfer"]["Receiver"]["Token"]["Owner"] for t in transfers]
    else:
        addresses = [t["Transfer"]["Receiver"] for t in transfers]
    
    # Step 2: Get first buys for these addresses
    if token_type == 'solana':
        buy_data = get_first_buys_pumpfun(token_address, addresses, api_key)
    else:
        buy_data = get_first_buys(token_address, addresses, api_key)
    
    print(f"Found buy records for {len(buy_data)} addresses\n")
    
    # Step 3: Analyze for phishy behavior
    if token_type == 'solana':
        phishy_count, phishy_addresses = analyze_phishy_behavior_pumpfun(transfers, buy_data)
    else:
        phishy_count, phishy_addresses = analyze_phishy_behavior(transfers, buy_data)
    
    # Step 4: Output results
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    print(f"\nTotal addresses that received transfers: {len(transfers)}")
    print(f"Addresses with phishy behavior: {phishy_count}")
    print(f"Addresses with normal behavior: {len(transfers) - phishy_count}")
    
    if phishy_count > 0:
        print(f"\n⚠️  TOKEN IS PHISHY! ⚠️")
        print(f"\nFound {phishy_count} address(es) with suspicious behavior:\n")
        
        # Calculate totals
        total_transferred_all = 0.0
        total_bought_all = 0.0
        total_transferred_without_buy_all = 0.0
        
        for i, phishy in enumerate(phishy_addresses, 1):
            print(f"{i}. Address: {phishy['address']}")
            print(f"   First Transfer: {format_timestamp(phishy['first_transfer_time'])}")
            print(f"   First Buy: {format_timestamp(phishy['first_buy_time'])}")
            
            # Display amount information
            total_transferred = phishy.get('total_transferred', 0)
            total_bought = phishy.get('total_bought', 0)
            transferred_without_buy = phishy.get('transferred_without_buy', 0)
            
            try:
                transferred_float = float(total_transferred) if total_transferred else 0.0
                bought_float = float(total_bought) if total_bought else 0.0
                without_buy_float = float(transferred_without_buy) if transferred_without_buy else 0.0
                
                total_transferred_all += transferred_float
                total_bought_all += bought_float
                total_transferred_without_buy_all += without_buy_float
                
                transferred_str = f"{transferred_float:,.2f}" if transferred_float > 0 else "0"
                bought_str = f"{bought_float:,.2f}" if bought_float > 0 else "0"
                without_buy_str = f"{without_buy_float:,.2f}" if without_buy_float > 0 else "0"
                
                print(f"   Total Transferred: {transferred_str}")
                print(f"   Total Bought: {bought_str}")
                if without_buy_float > 0:
                    print(f"   ⚠️  Transferred Without Buy: {without_buy_str} (This amount was sent but never purchased)")
            except (ValueError, TypeError):
                print(f"   Total Transferred: {total_transferred}")
                print(f"   Total Bought: {total_bought}")
                if transferred_without_buy > 0:
                    print(f"   ⚠️  Transferred Without Buy: {transferred_without_buy}")
            
            print(f"   Reason: {phishy['reason']}")
            print()
        
        # Print summary
        print("\n" + "-"*60)
        print("SUMMARY OF PHISHY BEHAVIOR:")
        print("-"*60)
        print(f"Total Amount Transferred to Phishy Addresses: {total_transferred_all:,.2f}")
        print(f"Total Amount Bought by Phishy Addresses: {total_bought_all:,.2f}")
        print(f"⚠️  Total Amount Transferred WITHOUT Purchase: {total_transferred_without_buy_all:,.2f}")
        print("-"*60)
    else:
        print("\n✅ Token appears to be safe (no phishy behavior detected)")
    
    print("="*60)


if __name__ == "__main__":
    main()

