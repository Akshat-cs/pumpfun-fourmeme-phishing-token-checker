#!/usr/bin/env python3
"""
Script to check if a Pump.fun token is phishy by analyzing transfers vs purchases.
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


def get_top_holders_pumpfun(token_address: str, api_key: str) -> List[Dict]:
    """
    Get top 10 holders of a Pump.fun token.
    
    Args:
        token_address: The token mint address
        api_key: API key for authentication (required)
    
    Returns:
        List of holder information with address and holding amount
    """
    query = """
    query MyQuery($token: String) {
  Solana {
    BalanceUpdates(
      limit: {count: 10}
      orderBy: {descendingByField: "BalanceUpdate_Holding_maximum"}
      where: {BalanceUpdate: {Currency: {MintAddress: {is: $token}}}, Transaction: {Result: {Success: true}}}
    ) {
      BalanceUpdate {
        Currency {
          Name
          MintAddress
          Symbol
        }
        Account {
          Token {
            Owner
          }
        }
        Holding: PostBalance(maximum: Block_Slot, selectWhere: {ne: "0"})
      }
    }
  }
}

    """
    
    variables = {
        "token": token_address
    }
    
    print(f"Fetching top 10 holders for token: {token_address}")
    response = make_graphql_request(query, variables, api_key)
    
    holders = []
    if "data" in response:
        solana_data = response["data"].get("Solana")
        if solana_data:
            if isinstance(solana_data, list) and len(solana_data) > 0:
                balance_updates = solana_data[0].get("BalanceUpdates", [])
            elif isinstance(solana_data, dict):
                balance_updates = solana_data.get("BalanceUpdates", [])
            else:
                balance_updates = []
            
            for update in balance_updates:
                owner = update["BalanceUpdate"]["Account"]["Token"]["Owner"]
                holding = update["BalanceUpdate"].get("Holding", 0)
                percent_holding = update.get("percent_holding", 0)
                holders.append({
                    "address": owner,
                    "holding": holding,
                    "percent_holding": float(percent_holding) if percent_holding else 0
                })
    
    return holders


# Mayhem mode AI agent address
MAYHEM_AI_AGENT_ADDRESS = "BwWK17cbHxwWBKZkUYvzxLcNQ1YVyaFezduWbtm2de6s"

def analyze_holder_distribution(token_address: str, creator_address: Optional[str], 
                                bonding_curve: Optional[str], is_mayhem_mode: bool, api_key: str) -> Dict:
    """
    Analyze holder distribution for a token using top 10 holders only.
    
    Args:
        token_address: The token mint address
        creator_address: The creator's address
        bonding_curve: The bonding curve address (to exclude)
        is_mayhem_mode: Whether the token is in Mayhem mode
        api_key: API key for authentication (required)
    
    Returns:
        Dictionary with analysis results:
        - creator_percent: Creator's holding percentage (if in top 10)
        - creator_check_passed: True if creator holds < 5% or not in top 10
        - other_holders_check_passed: True if all other holders in top 10 hold < 5%
        - top10_percent: Top 10 holders' total percentage (excluding bonding curve and Mayhem AI agent)
        - top10_check_passed: True if top 10 hold < 70%
        - failed_holder: Address of holder that failed the check (if any)
    """
    top_holders = get_top_holders_pumpfun(token_address, api_key)
    
    if not top_holders:
        return {
            "creator_percent": 0,
            "creator_check_passed": True,
            "other_holders_check_passed": True,
            "top10_percent": 0,
            "top10_check_passed": True,
            "failed_holder": None,
            "error": "Could not fetch holders"
        }
    
    # Calculate total supply based on Mayhem mode
    # Non-mayhem tokens: 1 Billion, Mayhem tokens: 2 Billion
    total_supply = 2_000_000_000 if is_mayhem_mode else 1_000_000_000
    
    # Calculate percentage holding for each holder and filter out bonding curve and Mayhem AI agent
    holders_with_percent = []
    for holder in top_holders:
        address = holder["address"]
        # Skip bonding curve and Mayhem AI agent
        if bonding_curve and address == bonding_curve:
            continue
        if address == MAYHEM_AI_AGENT_ADDRESS:
            continue
        
        holding = float(holder.get("holding", 0) or 0)
        percent_holding = (holding / total_supply) * 100 if total_supply > 0 else 0
        
        holders_with_percent.append({
            "address": address,
            "holding": holding,
            "percent_holding": percent_holding
        })
    
    # Check if creator is in top 10
    creator_percent = 0
    creator_in_top10 = False
    if creator_address:
        for holder in holders_with_percent:
            if holder["address"] == creator_address:
                creator_percent = holder["percent_holding"]
                creator_in_top10 = True
                break
    
    # Creator check: passes if not in top 10 OR if in top 10 but holds < 5%
    creator_check_passed = not creator_in_top10 or creator_percent < 5.0
    
    # Check if any other holder in top 10 (excluding creator, bonding curve, and Mayhem AI agent) holds >= 5%
    other_holders_check_passed = True
    failed_holder = None
    for holder in holders_with_percent:
        if creator_address and holder["address"] == creator_address:
            continue
        if holder["percent_holding"] >= 5.0:
            other_holders_check_passed = False
            failed_holder = holder["address"]
            break
    
    # Calculate top 10 holders' total percentage (excluding bonding curve and Mayhem AI agent)
    top10_percent = sum(h["percent_holding"] for h in holders_with_percent)
    top10_check_passed = top10_percent < 70.0
    
    return {
        "creator_percent": round(creator_percent, 2),
        "creator_check_passed": creator_check_passed,
        "other_holders_check_passed": other_holders_check_passed,
        "top10_percent": round(top10_percent, 2),
        "top10_check_passed": top10_check_passed,
        "failed_holder": failed_holder
    }


def get_trades_count_last_6h(address: str, api_key: str) -> int:
    """
    Get count of trades in last 6 hours for an address.
    
    Args:
        address: The wallet address
        api_key: API key for authentication (required)
    
    Returns:
        Count of trades in last 6 hours
    """
    query = """
    query MyQuery($trader: String) {
      Solana(dataset: realtime) {
        DEXTradeByTokens(
          where: {
            Block: { Time: { since_relative: { hours_ago: 6 } } }
            Trade: {
              Side: {
                Currency: {
                  MintAddress: {
                    in: [
                      "So11111111111111111111111111111111111111112",
                      "11111111111111111111111111111111"
                    ]
                  }
                }
              }
            }
            any: [
              { Trade: { Account: { Address: { is: $trader } } } }
              { Trade: { Account: { Token: { Owner: { is: $trader } } } } }
            ]
          }
        ) {
          count
        }
      }
    }
    """
    
    variables = {
        "trader": address
    }
    
    response = make_graphql_request(query, variables, api_key)
    
    if "data" in response:
        solana_data = response["data"].get("Solana")
        if solana_data:
            if isinstance(solana_data, list) and len(solana_data) > 0:
                trades = solana_data[0].get("DEXTradeByTokens", [])
            elif isinstance(solana_data, dict):
                trades = solana_data.get("DEXTradeByTokens", [])
            else:
                trades = []
            
            if trades and len(trades) > 0:
                return trades[0].get("count", 0)
    
    return 0


def get_bonding_curve_address(token_address: str, api_key: str) -> Optional[Dict]:
    """
    Get the bonding curve address for a Pump.fun token by querying the create instruction.
    The bonding curve is the 3rd account in the Instruction accounts array.
    
    Args:
        token_address: The token mint address
        api_key: API key for authentication (required)
    
    Returns:
        Dictionary with bonding_curve, transaction_signature, creator_address, and creation_time,
        or None if not found
    """
    query = """
    query MyQuery($token: String) {
  Solana {
    Instructions(
      where: {Instruction: {Program: {Address: {is: "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"}, Method: {in: ["create", "create_v2"]}}, Accounts: {includes: {Address: {is: $token}}}}, Transaction: {Result: {Success: true}}}
    ) {
    Block{
    Creation_time:Time
    }
      Instruction {
        Accounts {
          Address
        }
        Program {
          AccountNames
          Method
          Arguments {
            Name
            Type
            Value {
              ... on Solana_ABI_Integer_Value_Arg {
                integer
              }
              ... on Solana_ABI_String_Value_Arg {
                string
              }
              ... on Solana_ABI_Address_Value_Arg {
                address
              }
              ... on Solana_ABI_BigInt_Value_Arg {
                bigInteger
              }
              ... on Solana_ABI_Bytes_Value_Arg {
                hex
              }
              ... on Solana_ABI_Boolean_Value_Arg {
                bool
              }
              ... on Solana_ABI_Float_Value_Arg {
                float
              }
              ... on Solana_ABI_Json_Value_Arg {
                json
              }
            }
          }
        }
      }
      Transaction {
        Creation_transaction:Signature
        DevAddress:Signer
      }
    }
  }
}

    """
    
    variables = {
        "token": token_address
    }
    
    print(f"Finding bonding curve address for token: {token_address}")
    response = make_graphql_request(query, variables, api_key)
    
    # Check for errors first
    if "errors" in response:
        print("Warning: GraphQL errors occurred while finding bonding curve")
        return None
    
    # Extract bonding curve address (3rd account in accounts array, index 2)
    if "data" in response and response["data"] is not None:
        solana_data = response["data"].get("Solana")
        if solana_data:
            if isinstance(solana_data, list) and len(solana_data) > 0:
                instructions = solana_data[0].get("Instructions", [])
            elif isinstance(solana_data, dict):
                instructions = solana_data.get("Instructions", [])
            else:
                instructions = []
            
            # Filter instructions by method and find bonding curve
            for instruction_item in instructions:
                instruction_data = instruction_item.get("Instruction")
                if instruction_data:
                    program_data = instruction_data.get("Program", {})
                    method = program_data.get("Method", "")
                    # Filter by method (create or create_v2)
                    if method in ["create", "create_v2"]:
                        accounts = instruction_data.get("Accounts", [])
                        if len(accounts) >= 3:
                            bonding_curve = accounts[2].get("Address")
                            if bonding_curve:
                                # Extract transaction and creator info
                                transaction_data = instruction_item.get("Transaction", {})
                                transaction_signature = transaction_data.get("Creation_transaction")
                                creator_address = transaction_data.get("DevAddress")
                                
                                # Extract creation time
                                block_data = instruction_item.get("Block", {})
                                creation_time = block_data.get("Creation_time")
                                
                                # Extract token metadata from Arguments
                                arguments = program_data.get("Arguments", [])
                                token_name = None
                                token_symbol = None
                                token_uri = None
                                is_mayhem_mode = False
                                
                                for arg in arguments:
                                    arg_name = arg.get("Name", "")
                                    arg_value = arg.get("Value", {})
                                    
                                    if arg_name == "name" and "string" in arg_value:
                                        token_name = arg_value.get("string")
                                    elif arg_name == "symbol" and "string" in arg_value:
                                        token_symbol = arg_value.get("string")
                                    elif arg_name == "uri" and "string" in arg_value:
                                        token_uri = arg_value.get("string")
                                    elif arg_name == "is_mayhem_mode" and "bool" in arg_value:
                                        is_mayhem_mode = arg_value.get("bool", False)
                                
                                print(f"Found bonding curve address: {bonding_curve}")
                                return {
                                    "bonding_curve": bonding_curve,
                                    "transaction_signature": transaction_signature,
                                    "creator_address": creator_address,
                                    "creation_time": creation_time,
                                    "token_name": token_name,
                                    "token_symbol": token_symbol,
                                    "token_uri": token_uri,
                                    "is_mayhem_mode": is_mayhem_mode
                                }
    
    print("Warning: Could not find bonding curve address")
    return None


def fetch_ipfs_metadata(uri: Optional[str]) -> Optional[Dict]:
    """
    Fetch metadata from IPFS URI.
    
    Args:
        uri: IPFS URI (e.g., https://ipfs.io/ipfs/...)
    
    Returns:
        Dictionary with metadata (image, twitter, website, telegram, description, etc.) or None if failed
    """
    if not uri:
        return None
    
    try:
        response = requests.get(uri, timeout=10)
        response.raise_for_status()
        metadata = response.json()
        return metadata
    except Exception as e:
        print(f"Warning: Failed to fetch IPFS metadata from {uri}: {e}")
        return None


def check_token_graduated(token_address: str, api_key: str) -> bool:
    """
    Check if a Pump.fun token has graduated to PumpSwap.
    
    Args:
        token_address: The token mint address
        api_key: API key for authentication (required)
    
    Returns:
        True if token has graduated (Migrate instruction found), False otherwise
    """
    query = """
    query($token:String){
      Solana {
        Instructions(
          where: {Instruction: {Accounts:{includes:{Address:{is:$token}}} Program: {Address: {is: "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"}}, Logs: {includes: {includes: "Migrate"}}}, Transaction: {Result: {Success: true}}}
        ) {
          Migrate_Time: Block {
            Time
          }
          Instruction {
            Program {
              Name
              Method
              Arguments {
                Name
                Value {
                  ... on Solana_ABI_Json_Value_Arg {
                    json
                  }
                  ... on Solana_ABI_Float_Value_Arg {
                    float
                  }
                  ... on Solana_ABI_Boolean_Value_Arg {
                    bool
                  }
                  ... on Solana_ABI_Bytes_Value_Arg {
                    hex
                  }
                  ... on Solana_ABI_BigInt_Value_Arg {
                    bigInteger
                  }
                  ... on Solana_ABI_Address_Value_Arg {
                    address
                  }
                  ... on Solana_ABI_String_Value_Arg {
                    string
                  }
                  ... on Solana_ABI_Integer_Value_Arg {
                    integer
                  }
                }
              }
              Address
              AccountNames
            }
            Accounts {
              Token {
                ProgramId
                Owner
                Mint
              }
              IsWritable
              Address
            }
          }
          Transaction {
            Signature
          }
          joinInstructions(
            join: any_inner
            Transaction_Index:Transaction_Index
            Transaction_Signature: Transaction_Signature
            where: {Instruction: {Program: {Address: {is: "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"}, Method: {is: "create_pool"}}}}
          ) {
            Instruction {
              Program {
                Name
                Method
                Arguments {
                  Value {
                    ... on Solana_ABI_Address_Value_Arg {
                      address
                    }
                    ... on Solana_ABI_String_Value_Arg {
                      string
                    }
                  }
                  Type
                  Name
                }
                AccountNames
              }
              Accounts {
                Address
                Token {
                  Owner
                  Mint
                }
              }
            }
          }
        }
      }
    }
    """
    
    variables = {
        "token": token_address
    }
    
    print(f"Checking if token has graduated: {token_address}")
    response = make_graphql_request(query, variables, api_key)
    
    if "data" in response:
        solana_data = response["data"].get("Solana")
        if solana_data:
            if isinstance(solana_data, list) and len(solana_data) > 0:
                instructions = solana_data[0].get("Instructions", [])
            elif isinstance(solana_data, dict):
                instructions = solana_data.get("Instructions", [])
            else:
                instructions = []
            
            # If any instructions are returned, token has graduated
            if instructions and len(instructions) > 0:
                return True
    
    return False


def get_liquidity_for_pool(bonding_curve: str, api_key: str) -> Optional[float]:
    """
    Get latest liquidity for a bonding curve pool.
    
    Args:
        bonding_curve: The bonding curve address
        api_key: API key for authentication (required)
    
    Returns:
        Liquidity amount in SOL (float) or None if not found
    """
    query = """
    query GetLatestLiquidityForPool($bondingcurve: String) {
      Solana(dataset: realtime) {
        DEXPools(
          where: {Pool: {Market: {MarketAddress: {is: $bondingcurve}}}, Transaction: {Result: {Success: true}}}
          orderBy: {descending: Block_Slot}
          limit: {count: 1}
        ) {
          Pool {
            Quote {
              Liquidity:PostAmount
            }
          }
        }
      }
    }
    """
    
    variables = {
        "bondingcurve": bonding_curve
    }
    
    print(f"Fetching liquidity for bonding curve: {bonding_curve}")
    response = make_graphql_request(query, variables, api_key)
    
    if "data" in response:
        solana_data = response["data"].get("Solana")
        if solana_data:
            if isinstance(solana_data, list) and len(solana_data) > 0:
                dex_pools = solana_data[0].get("DEXPools", [])
            elif isinstance(solana_data, dict):
                dex_pools = solana_data.get("DEXPools", [])
            else:
                dex_pools = []
            
            if dex_pools and len(dex_pools) > 0:
                pool = dex_pools[0].get("Pool", {})
                quote = pool.get("Quote", {})
                liquidity_str = quote.get("Liquidity")
                if liquidity_str:
                    try:
                        liquidity = float(liquidity_str)
                        return liquidity
                    except (ValueError, TypeError):
                        pass
    
    return None




def get_pump_tokens_count(address: str, api_key: str) -> int:
    """
    Get count of pump tokens held by an address.
    
    Args:
        address: The wallet address
        api_key: API key for authentication (required)
    
    Returns:
        Count of pump tokens held (with balance > 0)
    """
    query = """
    query MyQuery($address: String) {
  Solana {
    BalanceUpdates(
      where: {BalanceUpdate: {Account: {Owner: {is: $address}}, Currency: {UpdateAuthority:{is:"TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM"}}}}
      orderBy: {descendingByField: "BalanceUpdate_Balance_maximum"}
    ) {
      BalanceUpdate {
        Balance: PostBalance(maximum: Block_Slot)
        Currency {
          Name
          Symbol
          MintAddress
          UpdateAuthority
        }
      }
    }
  }
}

    """
    
    variables = {
        "address": address
    }
    
    response = make_graphql_request(query, variables, api_key)
    
    if "data" in response:
        solana_data = response["data"].get("Solana")
        if solana_data:
            if isinstance(solana_data, list) and len(solana_data) > 0:
                balance_updates = solana_data[0].get("BalanceUpdates", [])
            elif isinstance(solana_data, dict):
                balance_updates = solana_data.get("BalanceUpdates", [])
            else:
                balance_updates = []
            
            # Count unique pump tokens with balance > 0
            unique_tokens = set()
            for update in balance_updates:
                mint_address = update["BalanceUpdate"]["Currency"]["MintAddress"]
                balance = float(update["BalanceUpdate"].get("Balance", 0) or 0)
                if balance > 0:
                    unique_tokens.add(mint_address)
            
            return len(unique_tokens)
    
    return 0


def get_trades_count_last_6h(address: str, api_key: str) -> int:
    """
    Get count of trades in last 6 hours for an address.
    
    Args:
        address: The wallet address
        api_key: API key for authentication (required)
    
    Returns:
        Count of trades in last 6 hours
    """
    query = """
    query MyQuery($trader: String) {
      Solana(dataset: realtime) {
        DEXTradeByTokens(
          where: {
            Block: { Time: { since_relative: { hours_ago: 6 } } }
            Trade: {
              Side: {
                Currency: {
                  MintAddress: {
                    in: [
                      "So11111111111111111111111111111111111111112",
                      "11111111111111111111111111111111"
                    ]
                  }
                }
              }
            }
            any: [
              { Trade: { Account: { Address: { is: $trader } } } }
              { Trade: { Account: { Token: { Owner: { is: $trader } } } } }
            ]
          }
        ) {
          count
        }
      }
    }
    """
    
    variables = {
        "trader": address
    }
    
    response = make_graphql_request(query, variables, api_key)
    
    if "data" in response:
        solana_data = response["data"].get("Solana")
        if solana_data:
            if isinstance(solana_data, list) and len(solana_data) > 0:
                trades = solana_data[0].get("DEXTradeByTokens", [])
            elif isinstance(solana_data, dict):
                trades = solana_data.get("DEXTradeByTokens", [])
            else:
                trades = []
            
            if trades and len(trades) > 0:
                return trades[0].get("count", 0)
    
    return 0


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
    """Main function to run the phishy token check for Pump.fun tokens."""
    # Parse command line arguments
    token_address = None
    api_key = None
    
    # Check for command line arguments
    # Format: python check_phishy_token.py <token_address> [api_key]
    if len(sys.argv) >= 2:
        token_address = sys.argv[1]
    if len(sys.argv) >= 3:
        api_key = sys.argv[2]
    
    # Get token address if not provided
    if not token_address:
        token_address = input("Enter the Pump.fun token address to check: ").strip()
    
    if not token_address:
        print("Error: Token address is required")
        sys.exit(1)
    
    # Validate Solana address format
    if not (len(token_address) >= 32 and len(token_address) <= 44 and not token_address.startswith('0x')):
        print("Error: Invalid Pump.fun token address format")
        print("Solana addresses should be 32-44 characters and not start with 0x")
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
        print("  1. Command line: python check_phishy_token.py <token_address> [api_key]")
        print("  2. .env file: Create a .env file with BITQUERY_API_KEY=your_key_here")
        print("  3. Environment variable: export BITQUERY_API_KEY='your_key_here'")
        print("  4. Interactive prompt (when running the script)")
        print("\nSee .env.sample for an example.")
        sys.exit(1)
    
    print("\n" + "="*60)
    print(f"Checking Pump.fun token: {token_address}")
    print("="*60 + "\n")
    
    # Find bonding curve address
    print("Finding bonding curve address...")
    bonding_curve_data = get_bonding_curve_address(token_address, api_key)
    if not bonding_curve_data:
        print("Error: Could not find bonding curve address for this token.")
        print("App provides analysis only on recent tokens.")
        sys.exit(1)
    
    bonding_curve = bonding_curve_data.get("bonding_curve") if isinstance(bonding_curve_data, dict) else bonding_curve_data
    print(f"Found bonding curve: {bonding_curve}\n")
    
    # Step 1: Get first transfers
    transfers = get_first_transfers_pumpfun(token_address, bonding_curve, api_key)
    
    if not transfers:
        print("No transfers found for this token.")
        return
    
    print(f"Found {len(transfers)} addresses that received transfers\n")
    
    # Extract address list
    addresses = [t["Transfer"]["Receiver"]["Token"]["Owner"] for t in transfers]
    
    # Step 2: Get first buys for these addresses
    buy_data = get_first_buys_pumpfun(token_address, addresses, api_key)
    
    print(f"Found buy records for {len(buy_data)} addresses\n")
    
    # Step 3: Analyze for phishy behavior
    phishy_count, phishy_addresses = analyze_phishy_behavior_pumpfun(transfers, buy_data)
    
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

