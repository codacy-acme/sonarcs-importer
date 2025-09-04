# Codacy SonarQube C# Rules Importer

This project provides tools to import SonarQube C# rules into Codacy as coding standards, along with utilities for verification and debugging.

## Features

- Import SonarQube XML rules into Codacy coding standards
- Support for C# language with SonarC# tool
- Disable all existing patterns before enabling only specified rules
- Generate output files showing enabled/skipped patterns
- Multiple utility scripts for verification and debugging

## Setup

### 1. API Token Configuration

You need a Codacy API token to use these tools. The token can be provided in three ways (in order of priority):

1. **Command-line argument**: `--api-token your_token_here`
2. **Environment variable**: `export CODACY_API_TOKEN=your_token_here`
3. **`.env` file**: Create a `.env` file with `CODACY_API_TOKEN=your_token_here`

#### Getting Your API Token

1. Go to [Codacy API Tokens](https://https://app.codacy.com/account/access-management)
2. Generate a new API token
3. Copy the token for use with the scripts

#### Using .env File (Recommended)

```bash
# Copy the example file
cp .env.example .env

# Edit .env and replace with your actual token
CODACY_API_TOKEN=your_actual_api_token_here
```

### 2. SonarQube Rules File

Place your SonarQube quality profile export as `csharp_sonarqube_rules.xml` in the project directory, or specify a different file using the `--xml-file` parameter.

## Usage

### Main Import Script

```bash
# Basic usage (uses .env file or environment variable)
python codacy_sonar_importer.py --organization your-org-name

# With custom standard name
python codacy_sonar_importer.py --organization your-org-name --standard-name "My Custom Rules"

# With custom XML file
python codacy_sonar_importer.py --organization your-org-name --xml-file my_rules.xml

# With API token as argument
python codacy_sonar_importer.py --organization your-org-name --api-token your_token_here
```

### Utility Scripts

All utility scripts support the same API token configuration methods:

```bash
# Verify coding standard patterns
python verify_coding_standard.py --standard-id 12345

# Check missing rules
python check_missing_rules.py

# Analyze default patterns
python get_default_patterns.py

# Debug pattern counts
python debug_pattern_count.py
```

## Files

- `codacy_sonar_importer.py` - Main import script
- `verify_coding_standard.py` - Verify patterns in a coding standard
- `check_missing_rules.py` - Check which XML rules are missing in Codacy
- `get_default_patterns.py` - Analyze available vs XML patterns
- `debug_pattern_count.py` - Debug coding standard behavior
- `csharp_sonarqube_rules.xml` - Default SonarQube rules file
- `.env.example` - Example environment file

## Output Files

The main script generates timestamped output files:
- `skipped_rules_YYYYMMDD_HHMMSS.json` - Rules that couldn't be imported
- `enabled_patterns_YYYYMMDD_HHMMSS.json` - Successfully enabled patterns

## Security

- The `.env` file is ignored by git to prevent accidental token exposure
- Never commit API tokens to version control
- Use environment variables or .env files for token management
