#!/usr/bin/env python3
"""
Script to verify what patterns are actually enabled in a Codacy coding standard
and compare with the XML file
"""

import requests
import sys
import os
import argparse
from pathlib import Path
from typing import List, Optional
import defusedxml.ElementTree as ET

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

def get_xml_rules() -> List[str]:
    """Extract rule keys from XML file"""
    tree = ET.parse("csharp_sonarqube_rules.xml")
    root = tree.getroot()

    rules = []
    for rule in root.findall('.//rule'):
        key_elem = rule.find('key')
        if key_elem is not None and key_elem.text is not None:
            rules.append(key_elem.text)

    return sorted(rules)

def get_enabled_patterns_in_standard(standard_id, api_token):
    """Get enabled patterns from a specific coding standard"""
    headers = {
        "api-token": api_token,
        "Accept": "application/json"
    }

    # Get the SonarC# tool configuration for this coding standard
    url = f"https://app.codacy.com/api/v3/organizations/gh/codacy-acme/coding-standards/{standard_id}/tools/8954dff3-f19c-429c-ac76-c45fa5e73b62"

    try:
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()

        tool_data = response.json()
        patterns = tool_data.get('data', {}).get('patterns', [])

        # Extract enabled pattern IDs and convert to rule keys
        enabled_rules = []
        for pattern in patterns:
            if pattern.get('enabled', False):
                pattern_id = pattern.get('id', '')
                if pattern_id.startswith('SonarCSharp_'):
                    rule_key = pattern_id.replace('SonarCSharp_', '')
                    enabled_rules.append(rule_key)

        return sorted(enabled_rules)

    except requests.exceptions.RequestException as e:
        print(f"Error retrieving coding standard patterns: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return []

def main():
    parser = argparse.ArgumentParser(
        description="Verify patterns enabled in a Codacy coding standard against XML file"
    )

    parser.add_argument(
        "--standard-id",
        default="128992",
        help="Coding standard ID to verify (default: 128992)"
    )

    parser.add_argument(
        "--api-token",
        help="Codacy API token (can also be set via CODACY_API_TOKEN environment variable or .env file)"
    )

    args = parser.parse_args()

    # Get API token
    api_token = get_api_token(args.api_token)

    print(f"Verifying Coding Standard ID: {args.standard_id}")
    print("=" * 50)

    xml_rules = get_xml_rules()
    enabled_rules = get_enabled_patterns_in_standard(args.standard_id, api_token)

    print(f"Rules in XML: {len(xml_rules)}")
    print(f"Patterns enabled in coding standard: {len(enabled_rules)}")

    # Find rules in XML that are NOT enabled in the coding standard
    missing_in_standard = set(xml_rules) - set(enabled_rules)

    # Find patterns enabled in standard that are NOT in XML
    extra_in_standard = set(enabled_rules) - set(xml_rules)

    if missing_in_standard:
        print(f"\nRules in XML but NOT enabled in coding standard ({len(missing_in_standard)}):")
        for rule in sorted(missing_in_standard):
            print(f"  - {rule}")

    if extra_in_standard:
        print(f"\nPatterns enabled in coding standard but NOT in XML ({len(extra_in_standard)}):")
        for rule in sorted(extra_in_standard):
            print(f"  + {rule}")

    # Show matching rules
    matching_rules = set(xml_rules) & set(enabled_rules)

    print(f"\nSummary:")
    print(f"  XML rules: {len(xml_rules)}")
    print(f"  Enabled patterns: {len(enabled_rules)}")
    print(f"  Missing from standard: {len(missing_in_standard)}")
    print(f"  Extra in standard: {len(extra_in_standard)}")
    print(f"  Correctly enabled: {len(matching_rules)}")

    success_rate = (len(matching_rules) / len(xml_rules)) * 100
    print(f"  Success rate: {success_rate:.1f}%")

if __name__ == "__main__":
    main()
