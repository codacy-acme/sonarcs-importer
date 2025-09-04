#!/usr/bin/env python3
"""
Debug script to understand the pattern count discrepancy
"""

import requests
import json
import os
import sys
import argparse
from pathlib import Path

def load_env_file():
    """Load environment variables from .env file if it exists"""
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

def get_api_token(args_token=None):
    """Get API token from command line args, environment variable, or .env file"""
    load_env_file()
    
    # Priority: command line arg > environment variable > .env file
    token = args_token or os.getenv("CODACY_API_TOKEN")
    
    if not token:
        print("Error: Codacy API token is required.")
        print("Set it via:")
        print("  1. --api-token argument")
        print("  2. CODACY_API_TOKEN environment variable")
        print("  3. CODACY_API_TOKEN in .env file")
        sys.exit(1)
    
    return token

def create_minimal_standard(api_token):
    """Create a minimal coding standard to test default behavior"""
    headers = {
        "api-token": api_token,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    url = "https://app.codacy.com/api/v3/organizations/gh/codacy-acme/coding-standards"
    
    payload = {
        "name": "Minimal Test",
        "languages": ["CSharp"]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        standard_data = response.json()
        standard_id = standard_data['data']['id']
        
        print(f"Created minimal coding standard with ID: {standard_id}")
        return str(standard_id)
        
    except requests.exceptions.RequestException as e:
        print(f"Error creating coding standard: {e}")
        return None

def check_standard_patterns(standard_id, api_token):
    """Check how many patterns are enabled in a coding standard"""
    headers = {
        "api-token": api_token,
        "Accept": "application/json"
    }
    
    url = f"https://app.codacy.com/api/v3/organizations/gh/codacy-acme/coding-standards"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        standards_data = response.json()
        standards = standards_data.get('data', [])
        
        for standard in standards:
            if str(standard.get('id')) == standard_id:
                meta = standard.get('meta', {})
                enabled_patterns = meta.get('enabledPatternsCount', 0)
                enabled_tools = meta.get('enabledToolsCount', 0)
                
                print(f"Standard ID {standard_id} ({standard.get('name')}):")
                print(f"  Enabled tools: {enabled_tools}")
                print(f"  Enabled patterns: {enabled_patterns}")
                return enabled_patterns
        
        print(f"Standard {standard_id} not found")
        return 0
        
    except requests.exceptions.RequestException as e:
        print(f"Error checking standard: {e}")
        return 0

def disable_all_tools_in_standard(standard_id, api_token):
    """Disable all tools in a coding standard"""
    headers = {
        "api-token": api_token,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Get all tools for the coding standard
    url = f"https://app.codacy.com/api/v3/organizations/gh/codacy-acme/coding-standards/{standard_id}/tools"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        tools_data = response.json()
        tools = tools_data.get('data', [])
        
        print(f"Found {len(tools)} tools in the coding standard")
        
        # Disable each tool
        for tool in tools:
            tool_uuid = tool.get('uuid')
            if tool_uuid:
                disable_url = f"https://app.codacy.com/api/v3/organizations/gh/codacy-acme/coding-standards/{standard_id}/tools/{tool_uuid}"
                
                payload = {
                    "enabled": False,
                    "patterns": []
                }
                
                disable_response = requests.patch(disable_url, headers=headers, json=payload)
                disable_response.raise_for_status()
                print(f"Disabled tool {tool_uuid}")
        
        return len(tools)
        
    except requests.exceptions.RequestException as e:
        print(f"Error disabling tools: {e}")
        return 0

def main():
    parser = argparse.ArgumentParser(
        description="Debug Codacy coding standard default behavior"
    )
    
    parser.add_argument(
        "--api-token",
        help="Codacy API token (can also be set via CODACY_API_TOKEN environment variable or .env file)"
    )
    
    args = parser.parse_args()
    
    # Get API token
    api_token = get_api_token(args.api_token)
    
    print("Testing Codacy coding standard default behavior")
    print("=" * 50)
    
    # Create a minimal coding standard
    standard_id = create_minimal_standard(api_token)
    if not standard_id:
        return
    
    # Check initial pattern count
    print("\n1. Initial state (just created):")
    initial_count = check_standard_patterns(standard_id, api_token)
    
    # Disable all tools
    print("\n2. Disabling all tools...")
    disabled_tools = disable_all_tools_in_standard(standard_id, api_token)
    
    # Check pattern count after disabling
    print("\n3. After disabling all tools:")
    after_disable_count = check_standard_patterns(standard_id, api_token)
    
    print(f"\nSummary:")
    print(f"  Initial patterns: {initial_count}")
    print(f"  After disabling all tools: {after_disable_count}")
    print(f"  Tools disabled: {disabled_tools}")

if __name__ == "__main__":
    main()
