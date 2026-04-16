
````md
# Aegis AEO/GEO Assignment

Private Python project for **AEO (Answer Engine Optimization)** and **GEO (Generative Engine Optimization)** analysis.  
This repository contains APIs, services, and tests for evaluating content quality, extracting structured fanout opportunities, analyzing gaps, and running automated answer-quality checks.

## Overview

The project is designed to help assess how well content performs for answer engines and generative search systems. It includes:

- content parsing utilities
- fanout generation and parsing logic
- gap analysis services
- AEO-focused quality checks
- API endpoints for running analysis
- automated tests for core evaluation logic

## Project Structure

```text
app/
  __init__.py
  main.py
  api/
    __init__.py
    aeo.py
    fanout.py
  models/
    __init__.py
    schemas.py
  services/
    __init__.py
    content_parser.py
    fanout_engine.py
    gap_analyzer.py
    aeo_checks/
      __init__.py
      base.py
      direct_answer.py
      htag_hierarchy.py
      readability.py

tests/
  __init__.py
  test_direct_answer.py
  test_htag_hierarchy.py
  test_readability.py
  test_fanout_parsing.py

requirements.txt
README.md
PROMPT_LOG.md
````

## Core Capabilities

### AEO checks

The project includes multiple answer-quality checks, such as:

* **Direct Answer Check**
  Evaluates whether content provides a clear, concise, and direct response.

* **Heading Hierarchy Check**
  Reviews heading structure and organization for clarity and machine readability.

* **Readability Check**
  Measures how easy the content is to read and understand.

### Fanout Analysis

The fanout logic helps identify content expansion opportunities by breaking a topic into related subtopics, likely follow-up questions, or answer branches.

### Gap Analysis

The gap analyzer helps identify missing coverage areas in the content so it can be improved for search, AI answers, and structured response generation.

## API

The application exposes API endpoints through the `app/api` layer.

Main API modules:

* `app/api/aeo.py`
* `app/api/fanout.py`

The application entry point is:

* `app/main.py`

## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/GaurAkshat24/aegis-aeo-geo-assignment.git
cd aegis-aeo-geo-assignment
pip install -r requirements.txt
```

## Running the Application

Start the app from the project root:

```bash
python -m app.main
```

If this project uses FastAPI or another ASGI framework, run it with the appropriate server, for example:

```bash
uvicorn app.main:app --reload
```

## Running Tests

Run the test suite with:

```bash
pytest
```

You can also run specific test files:

```bash
pytest tests/test_direct_answer.py
pytest tests/test_htag_hierarchy.py
pytest tests/test_readability.py
pytest tests/test_fanout_parsing.py
```

## Use Cases

This project can be used for:

* evaluating whether content is optimized for answer engines
* improving structure and readability of written content
* identifying missing topical coverage
* generating fanout ideas for content expansion
* validating quality checks through automated tests

## Tech Stack

* Python
* API-based service architecture
* automated unit tests with `pytest`

## Notes

* This is a private assignment repository.
* `PROMPT_LOG.md` may contain the original prompt history or execution notes used during development.
* The codebase is organized to keep API routes, services, schemas, and tests separate and maintainable.

## Future Improvements

Potential enhancements include:

* richer scoring and weighted ranking across checks
* support for more SEO/AEO/GEO signals
* expanded fanout generation logic
* more robust schema validation
* dashboard or frontend integration for analysis results

## Author

**Akshat Gaur**
GitHub: [GaurAkshat24](https://github.com/GaurAkshat24)

```
