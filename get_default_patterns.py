#!/usr/bin/env python3
"""
Script to get all default patterns for SonarC# tool from Codacy
"""

import requests
import sys
import os
import argparse
from pathlib import Path
from typing import Dict, Optional
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

def get_xml_rules() -> set:
    """Extract rule keys from XML file"""
    tree = xml_tree.parse("csharp_sonarqube_rules.xml")
    root = tree.getroot()

    rules = []
    for rule in root.findall('.//rule'):
        key_elem = rule.find('key')
        if key_elem is not None and key_elem.text is not None:
            rules.append(key_elem.text)

    return set(rules)

def get_all_sonarc_patterns(api_token):
    """Get all available SonarC# patterns from Codacy"""
    headers = {
        "api-token": api_token,
        "Accept": "application/json"
    }

    all_patterns = set()
    cursor = None

    while True:
        url = "https://app.codacy.com/api/v3/tools/8954dff3-f19c-429c-ac76-c45fa5e73b62/patterns"
        params = {}
        if cursor:
            params['cursor'] = cursor

        try:
            response = requests.get(url, headers=headers, params=params, timeout=60)
            response.raise_for_status()

            patterns_data = response.json()
            patterns = patterns_data.get('data', [])

            # Add patterns from this page
            for pattern in patterns:
                pattern_id = pattern.get('id')
                if pattern_id and pattern_id.startswith('SonarCSharp_'):
                    rule_key = pattern_id.replace('SonarCSharp_', '')
                    all_patterns.add(rule_key)

            # Check if there are more pages
            pagination = patterns_data.get('pagination', {})
            cursor = pagination.get('cursor')

            if not cursor:
                break

        except requests.exceptions.RequestException as e:
            print(f"Error retrieving patterns: {e}")
            break

    return all_patterns

def main():
    parser = argparse.ArgumentParser(
        description="Identify which patterns Codacy enables by default for SonarC#"
    )

    parser.add_argument(
        "--api-token",
        help="Codacy API token (can also be set via CODACY_API_TOKEN environment variable or .env file)"
    )

    args = parser.parse_args()

    # Get API token
    api_token = get_api_token(args.api_token)

    print("Analyzing default patterns vs XML patterns")
    print("=" * 50)

    xml_rules = get_xml_rules()
    all_patterns = get_all_sonarc_patterns(api_token)

    print(f"Rules in XML: {len(xml_rules)}")
    print(f"Total SonarC# patterns available: {len(all_patterns)}")

    # Find patterns that exist in Codacy but NOT in our XML
    extra_patterns = all_patterns - xml_rules

    # Find patterns in XML that don't exist in Codacy
    missing_patterns = xml_rules - all_patterns

    print(f"Patterns in XML that exist in Codacy: {len(xml_rules & all_patterns)}")
    print(f"Patterns in XML that DON'T exist in Codacy: {len(missing_patterns)}")
    print(f"Extra patterns in Codacy (not in XML): {len(extra_patterns)}")

    if missing_patterns:
        print(f"\nPatterns in XML but NOT in Codacy ({len(missing_patterns)}):")
        for pattern in sorted(missing_patterns)[:10]:
            print(f"  - {pattern}")
        if len(missing_patterns) > 10:
            print(f"  ... and {len(missing_patterns) - 10} more")

    # The discrepancy is likely that Codacy enables some of these "extra" patterns by default
    print("\nThe extra patterns that Codacy might be enabling by default")
    print(f"are likely from this list of {len(extra_patterns)} available patterns not in our XML.")


if __name__ == "__main__":
    main()
