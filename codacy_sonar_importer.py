#!/usr/bin/env python3
"""
Codacy SonarQube Rules Importer

This script imports SonarQube rules from an XML file and creates a Codacy coding standard
with only the specified rules enabled for C# language.

SONAR RULES SOURCE:
    By default, the script reads SonarQube rules from 'csharp_sonarqube_rules.xml'
    which should be placed in the same directory as this script. This XML file contains
    the exported SonarQube quality profile with the specific rules you want to import.

    You can specify a different XML file using the --xml-file parameter.

Usage:
    python codacy_sonar_importer.py --organization <org_name> [--standard-name <name>] [--api-token <token>] [--xml-file <path>]

Requirements:
    - CODACY_API_TOKEN environment variable or --api-token parameter
    - SonarQube XML rules file (default: 'csharp_sonarqube_rules.xml' in same directory)

XML File Format:
    The XML file should be a SonarQube quality profile export containing <rule> elements
    with repositoryKey, key, priority, and optional parameters for each rule.
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from typing import Dict, List, Set
import requests
from urllib.parse import quote
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


class CodacySonarImporter:
    def __init__(self, api_token: str, organization: str, standard_name: str = "Imported Sonar Rules"):
        self.api_token = api_token
        self.organization = organization
        self.standard_name = standard_name
        self.base_url = "https://app.codacy.com/api/v3"
        self.headers = {
            "api-token": api_token,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        self.sonar_rules: List[Dict] = []
        self.tool_uuids: Dict[str, str] = {}

    def parse_sonar_xml(self, xml_file: str) -> None:
        """Parse the SonarQube XML file to extract rules."""
        print(f"Parsing SonarQube XML file: {xml_file}")

        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            # Extract rules from XML
            rules = root.findall('.//rule')
            print(f"Found {len(rules)} rules in XML file")

            for rule in rules:
                repository_key = rule.find('repositoryKey').text
                key = rule.find('key').text
                priority = rule.find('priority').text

                # Extract parameters if they exist
                parameters = {}
                params_element = rule.find('parameters')
                if params_element is not None:
                    for param in params_element.findall('parameter'):
                        param_key = param.find('key').text
                        param_value = param.find('value').text
                        parameters[param_key] = param_value

                self.sonar_rules.append({
                    'repository_key': repository_key,
                    'key': key,
                    'priority': priority,
                    'parameters': parameters
                })

            print(f"Successfully parsed {len(self.sonar_rules)} SonarQube rules")

        except ET.ParseError as e:
            print(f"Error parsing XML file: {e}")
            sys.exit(1)
        except FileNotFoundError:
            print(f"XML file not found: {xml_file}")
            sys.exit(1)

    def get_tools(self) -> None:
        """Retrieve all available tools from Codacy API."""
        print("Retrieving available tools from Codacy...")

        url = f"{self.base_url}/tools"

        try:
            response = requests.get(url, headers=self.headers, timeout=60)
            response.raise_for_status()

            tools_data = response.json()
            tools = tools_data.get('data', [])

            print(f"Found {len(tools)} available tools")

            # Store tool UUIDs for later use
            for tool in tools:
                tool_name = tool.get('name', '').lower()
                tool_uuid = tool.get('uuid')
                if tool_uuid:
                    self.tool_uuids[tool_name] = tool_uuid

            print(f"Mapped {len(self.tool_uuids)} tool UUIDs")

        except requests.exceptions.RequestException as e:
            print(f"Error retrieving tools: {e}")
            sys.exit(1)

    def create_coding_standard(self) -> str:
        """Create a new coding standard in Codacy."""
        print(f"Creating coding standard: {self.standard_name}")

        # Check if standard name already exists and create a unique name if needed
        final_name = self._get_unique_standard_name()

        url = f"{self.base_url}/organizations/gh/{quote(self.organization)}/coding-standards"

        payload = {
            "name": final_name,
            "languages": ["CSharp"]
        }

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=60)
            response.raise_for_status()

            standard_data = response.json()
            standard_id = standard_data['data']['id']

            print(f"Successfully created coding standard with ID: {standard_id}")
            return str(standard_id)

        except requests.exceptions.RequestException as e:
            print(f"Error creating coding standard: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            sys.exit(1)

    def _get_unique_standard_name(self) -> str:
        """Get a unique name for the coding standard."""
        url = f"{self.base_url}/organizations/gh/{quote(self.organization)}/coding-standards"

        try:
            response = requests.get(url, headers=self.headers, timeout=60)
            response.raise_for_status()

            standards_data = response.json()
            existing_names = {std['name'] for std in standards_data.get('data', [])}

            # If name doesn't exist, use it as is
            if self.standard_name not in existing_names:
                return self.standard_name

            # Otherwise, find a unique name by appending a number
            counter = 1
            while f"{self.standard_name} ({counter})" in existing_names:
                counter += 1

            unique_name = f"{self.standard_name} ({counter})"
            print(f"Standard name '{self.standard_name}' already exists, using '{unique_name}'")
            return unique_name

        except requests.exceptions.RequestException as e:
            print(f"Warning: Could not check existing standard names: {e}")
            return self.standard_name

    def disable_all_tools(self, standard_id: str) -> None:
        """Disable all tools in the coding standard first."""
        print("Disabling all existing tools and patterns...")

        # Get all tools for the coding standard
        url = f"{self.base_url}/organizations/gh/{quote(self.organization)}/coding-standards/{standard_id}/tools"

        try:
            response = requests.get(url, headers=self.headers, timeout=60)
            response.raise_for_status()

            tools_data = response.json()
            tools = tools_data.get('data', [])

            # Disable each tool
            for tool in tools:
                tool_uuid = tool.get('uuid')
                if tool_uuid:
                    self._disable_tool(standard_id, tool_uuid)

            print(f"Disabled {len(tools)} tools")

        except requests.exceptions.RequestException as e:
            print(f"Error retrieving tools for coding standard: {e}")
            sys.exit(1)

    def _disable_tool(self, standard_id: str, tool_uuid: str) -> None:
        """Disable a specific tool in the coding standard."""
        url = f"{self.base_url}/organizations/gh/{quote(self.organization)}/coding-standards/{standard_id}/tools/{tool_uuid}"

        payload = {
            "enabled": False,
            "patterns": []
        }

        try:
            response = requests.patch(url, headers=self.headers, json=payload, timeout=60)
            response.raise_for_status()

        except requests.exceptions.RequestException as e:
            print(f"Warning: Could not disable tool {tool_uuid}: {e}")

    def enable_sonar_rules(self, standard_id: str) -> None:
        """Enable only the SonarQube rules from the XML file."""
        print("Enabling SonarQube rules from XML file...")

        # Group rules by tool (we'll need to map SonarQube repositories to Codacy tools)
        tool_patterns = self._map_sonar_rules_to_codacy_patterns()

        enabled_rules_count = 0

        for tool_name, patterns in tool_patterns.items():
            tool_uuid = self.tool_uuids.get(tool_name.lower())
            if not tool_uuid:
                print(f"Warning: Could not find Codacy tool for '{tool_name}'")
                continue

            print(f"Enabling {len(patterns)} patterns for tool: {tool_name}")

            # Enable the tool and its patterns
            success = self._enable_tool_patterns(standard_id, tool_uuid, patterns)
            if success:
                enabled_rules_count += len(patterns)

        print(f"Successfully enabled {enabled_rules_count} rules")

    def _map_sonar_rules_to_codacy_patterns(self) -> Dict[str, List[Dict]]:
        """Map SonarQube rules to Codacy tool patterns."""
        # First, get available patterns from Codacy
        available_patterns = self._get_available_patterns()

        tool_patterns = {}
        skipped_rules = []

        for rule in self.sonar_rules:
            repository_key = rule['repository_key']
            rule_key = rule['key']

            # Map SonarQube repository keys to Codacy tool names
            if repository_key == 'csharpsquid':
                tool_name = 'SonarC#'
            elif repository_key == 'roslyn.sonaranalyzer.security.cs':
                tool_name = 'SonarC#'  # Both repositories map to the same Codacy tool
            else:
                print(f"Warning: Unknown repository key '{repository_key}' for rule '{rule_key}'")
                continue

            # Check if this pattern exists in Codacy
            pattern_id = f"SonarCSharp_{rule_key}"
            if pattern_id not in available_patterns:
                skipped_rules.append(rule_key)
                continue

            if tool_name not in tool_patterns:
                tool_patterns[tool_name] = []

            # Create pattern configuration
            pattern_config = {
                "id": pattern_id,  # Codacy pattern ID format
                "enabled": True
            }

            # Add parameters if they exist
            if rule['parameters']:
                pattern_config["parameters"] = [
                    {"name": key, "value": value}
                    for key, value in rule['parameters'].items()
                ]

            tool_patterns[tool_name].append(pattern_config)

        if skipped_rules:
            print(f"Warning: {len(skipped_rules)} rules from XML don't exist in Codacy and will be skipped:")
            for rule in sorted(skipped_rules)[:10]:  # Show first 10
                print(f"  - {rule}")
            if len(skipped_rules) > 10:
                print(f"  ... and {len(skipped_rules) - 10} more")

        return tool_patterns

    def _get_available_patterns(self) -> set:
        """Get set of available pattern IDs from Codacy SonarC# tool with pagination support."""
        all_patterns = set()
        cursor = None

        while True:
            url = f"{self.base_url}/tools/8954dff3-f19c-429c-ac76-c45fa5e73b62/patterns"
            params = {}
            if cursor:
                params['cursor'] = cursor

            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=60)
                response.raise_for_status()

                patterns_data = response.json()
                patterns = patterns_data.get('data', [])

                # Add patterns from this page
                for pattern in patterns:
                    pattern_id = pattern.get('id')
                    if pattern_id:
                        all_patterns.add(pattern_id)

                # Check if there are more pages
                pagination = patterns_data.get('pagination', {})
                cursor = pagination.get('cursor')

                if not cursor:
                    break

            except requests.exceptions.RequestException as e:
                print(f"Warning: Could not retrieve available patterns: {e}")
                break

        print(f"Retrieved {len(all_patterns)} available patterns from Codacy")
        return all_patterns

    def _enable_tool_patterns(self, standard_id: str, tool_uuid: str, patterns: List[Dict]) -> bool:
        """Enable a tool and its patterns in the coding standard, ensuring ONLY specified patterns are enabled."""
        url = f"{self.base_url}/organizations/gh/{quote(self.organization)}/coding-standards/{standard_id}/tools/{tool_uuid}"

        # Get all available patterns for this tool
        all_available_patterns = self._get_all_tool_patterns(tool_uuid)

        # Create a comprehensive patterns list: enable our patterns, disable all others
        comprehensive_patterns = []

        # First, add our patterns as enabled
        enabled_pattern_ids = {pattern["id"] for pattern in patterns}
        comprehensive_patterns.extend(patterns)

        # Then, add all other patterns as explicitly disabled
        for pattern_id in all_available_patterns:
            if pattern_id not in enabled_pattern_ids:
                comprehensive_patterns.append({
                    "id": pattern_id,
                    "enabled": False
                })

        payload = {
            "enabled": True,
            "patterns": comprehensive_patterns
        }

        print(f"Enabling {len(patterns)} patterns and explicitly disabling {len(all_available_patterns) - len(patterns)} others")

        try:
            response = requests.patch(url, headers=self.headers, json=payload, timeout=60)
            response.raise_for_status()
            return True

        except requests.exceptions.RequestException as e:
            print(f"Error enabling tool patterns: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return False

    def _get_all_tool_patterns(self, tool_uuid: str) -> set:
        """Get all available pattern IDs for a specific tool."""
        all_patterns = set()
        cursor = None

        while True:
            url = f"{self.base_url}/tools/{tool_uuid}/patterns"
            params = {}
            if cursor:
                params['cursor'] = cursor

            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=60)
                response.raise_for_status()

                patterns_data = response.json()
                patterns = patterns_data.get('data', [])

                # Add patterns from this page
                for pattern in patterns:
                    pattern_id = pattern.get('id')
                    if pattern_id:
                        all_patterns.add(pattern_id)

                # Check if there are more pages
                pagination = patterns_data.get('pagination', {})
                cursor = pagination.get('cursor')

                if not cursor:
                    break

            except requests.exceptions.RequestException as e:
                print(f"Warning: Could not retrieve all patterns for tool {tool_uuid}: {e}")
                break

        return all_patterns

    def promote_coding_standard(self, standard_id: str) -> None:
        """Promote the draft coding standard to make it effective."""
        print("Promoting coding standard from draft to effective...")

        url = f"{self.base_url}/organizations/gh/{quote(self.organization)}/coding-standards/{standard_id}/promote"

        try:
            response = requests.post(url, headers=self.headers, timeout=60)
            response.raise_for_status()

            print("Successfully promoted coding standard")

        except requests.exceptions.RequestException as e:
            print(f"Error promoting coding standard: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            sys.exit(1)

    def run(self, xml_file: str = "csharp_sonarqube_rules.xml") -> None:
        """Execute the complete import process."""
        print("Starting Codacy SonarQube Rules Import Process")
        print("=" * 50)

        # Step 1: Parse SonarQube XML file
        self.parse_sonar_xml(xml_file)

        # Step 2: Get available tools from Codacy
        self.get_tools()

        # Step 3: Create coding standard
        standard_id = self.create_coding_standard()

        # Step 4: Disable all existing tools and patterns
        self.disable_all_tools(standard_id)

        # Step 5: Enable only the SonarQube rules
        self.enable_sonar_rules(standard_id)

        # Step 6: Promote the coding standard
        self.promote_coding_standard(standard_id)

        # Step 7: Generate output files
        self._generate_output_files()

        print("=" * 50)
        print("Import process completed successfully!")
        print(f"Created coding standard: {self.standard_name}")
        print(f"Organization: {self.organization}")

        # Calculate actual imported rules (but don't show warnings again)
        available_patterns = self._get_available_patterns()
        actual_imported = 0
        for rule in self.sonar_rules:
            pattern_id = f"SonarCSharp_{rule['key']}"
            if pattern_id in available_patterns:
                actual_imported += 1

        print(f"Total rules in XML: {len(self.sonar_rules)}")
        print(f"Rules successfully imported: {actual_imported}")
        print(f"Rules skipped (not available in Codacy): {len(self.sonar_rules) - actual_imported}")

    def _generate_output_files(self) -> None:
        """Generate output files with skipped rules and enabled patterns."""
        print("Generating output files...")

        available_patterns = self._get_available_patterns()

        enabled_rules = []
        skipped_rules = []

        for rule in self.sonar_rules:
            rule_key = rule['key']
            pattern_id = f"SonarCSharp_{rule_key}"

            if pattern_id in available_patterns:
                enabled_rules.append({
                    'rule_key': rule_key,
                    'pattern_id': pattern_id,
                    'repository_key': rule['repository_key'],
                    'priority': rule['priority'],
                    'parameters': rule['parameters']
                })
            else:
                skipped_rules.append({
                    'rule_key': rule_key,
                    'pattern_id': pattern_id,
                    'repository_key': rule['repository_key'],
                    'priority': rule['priority'],
                    'reason': 'Pattern not available in Codacy'
                })

        # Generate timestamp for unique filenames
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Write skipped rules file
        skipped_filename = f"skipped_rules_{timestamp}.json"
        with open(skipped_filename, 'w') as f:
            json.dump({
                'summary': {
                    'total_skipped': len(skipped_rules),
                    'coding_standard': self.standard_name,
                    'organization': self.organization,
                    'timestamp': datetime.now().isoformat()
                },
                'skipped_rules': skipped_rules
            }, f, indent=2)

        # Write enabled patterns file
        enabled_filename = f"enabled_patterns_{timestamp}.json"
        with open(enabled_filename, 'w') as f:
            json.dump({
                'summary': {
                    'total_enabled': len(enabled_rules),
                    'coding_standard': self.standard_name,
                    'organization': self.organization,
                    'timestamp': datetime.now().isoformat()
                },
                'enabled_patterns': enabled_rules
            }, f, indent=2)

        print(f"Generated output files:")
        print(f"  - Skipped rules: {skipped_filename} ({len(skipped_rules)} rules)")
        print(f"  - Enabled patterns: {enabled_filename} ({len(enabled_rules)} patterns)")


def main():
    parser = argparse.ArgumentParser(
        description="Import SonarQube rules into Codacy as a coding standard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python codacy_sonar_importer.py --organization my-org
  python codacy_sonar_importer.py --organization my-org --standard-name "Custom Sonar Rules"
  python codacy_sonar_importer.py --organization my-org --xml-file my_rules.xml
  python codacy_sonar_importer.py --organization my-org --api-token your-token-here
        """
    )

    parser.add_argument(
        "--organization",
        required=True,
        help="GitHub organization name"
    )

    parser.add_argument(
        "--standard-name",
        default="Imported Sonar Rules",
        help="Name for the coding standard (default: 'Imported Sonar Rules')"
    )

    parser.add_argument(
        "--api-token",
        help="Codacy API token (can also be set via CODACY_API_TOKEN environment variable)"
    )

    parser.add_argument(
        "--xml-file",
        default="csharp_sonarqube_rules.xml",
        help="Path to the SonarQube XML rules file (default: 'csharp_sonarqube_rules.xml')"
    )

    args = parser.parse_args()

    # Get API token using the new function that supports .env files
    api_token = get_api_token(args.api_token)

    # Create and run the importer
    importer = CodacySonarImporter(
        api_token=api_token,
        organization=args.organization,
        standard_name=args.standard_name
    )

    try:
        importer.run(args.xml_file)
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
