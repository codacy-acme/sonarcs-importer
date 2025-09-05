#!/usr/bin/env python3
"""
Script to check which SonarQube rules from the XML file are missing in Codacy
"""

import requests
import sys
import os
import argparse
from pathlib import Path
from typing import List
import defusedxml.ElementTree as xml_tree

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
    tree = xml_tree.parse("csharp_sonarqube_rules.xml")
    root = tree.getroot()

    rules = []
    for rule in root.findall('.//rule'):
        key_elem = rule.find('key')
        if key_elem is not None and key_elem.text is not None:
            rules.append(key_elem.text)

    return sorted(rules)

def get_codacy_patterns(api_token):
    """Get all SonarC# pattern IDs from Codacy"""
    headers = {
        "api-token": api_token,
        "Accept": "application/json"
    }

    url = "https://app.codacy.com/api/v3/tools/8954dff3-f19c-429c-ac76-c45fa5e73b62/patterns"

    response = requests.get(url, headers=headers, timeout=60)
    response.raise_for_status()

    patterns_data = response.json()
    patterns = patterns_data.get('data', [])

    # Extract rule keys from pattern IDs (remove "SonarCSharp_" prefix)
    pattern_keys = []
    for pattern in patterns:
        pattern_id = pattern.get('id', '')
        if pattern_id.startswith('SonarCSharp_'):
            rule_key = pattern_id.replace('SonarCSharp_', '')
            pattern_keys.append(rule_key)

    return sorted(pattern_keys)

def main():
    parser = argparse.ArgumentParser(
        description="Check which SonarQube rules from XML are missing in Codacy patterns"
    )

    parser.add_argument(
        "--api-token",
        help="Codacy API token (can also be set via CODACY_API_TOKEN environment variable or .env file)"
    )

    args = parser.parse_args()

    # Get API token
    api_token = get_api_token(args.api_token)

    print("Checking for missing rules...")

    xml_rules = get_xml_rules()
    codacy_patterns = get_codacy_patterns(api_token)

    print(f"Rules in XML: {len(xml_rules)}")
    print(f"Patterns in Codacy: {len(codacy_patterns)}")

    # Find rules in XML that don't exist in Codacy
    missing_in_codacy = set(xml_rules) - set(codacy_patterns)

    # Find patterns in Codacy that aren't in XML
    extra_in_codacy = set(codacy_patterns) - set(xml_rules)

    if missing_in_codacy:
        print(f"\nRules in XML but NOT in Codacy ({len(missing_in_codacy)}):")
        for rule in sorted(missing_in_codacy):
            print(f"  - {rule}")

    if extra_in_codacy:
        print(f"\nPatterns in Codacy but NOT in XML ({len(extra_in_codacy)}):")
        for rule in sorted(extra_in_codacy):
            print(f"  + {rule}")

    print("\nSummary:")
    print(f"  XML rules: {len(xml_rules)}")
    print(f"  Codacy patterns: {len(codacy_patterns)}")
    print(f"  Missing in Codacy: {len(missing_in_codacy)}")
    print(f"  Extra in Codacy: {len(extra_in_codacy)}")
    print(f"  Matching rules: {len(set(xml_rules) & set(codacy_patterns))}")


if __name__ == "__main__":
    main()
