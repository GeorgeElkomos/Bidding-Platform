# Tender Evaluation Package

This package provides functionality to evaluate tender proposals using a multi-agent system powered by Google's Gemini AI.

## Installation

1. Unzip the package to your project directory
2. Install the requirements:
   `ash
   pip install -r requirements.txt
   `
3. Copy .env.example to .env and add your Gemini API key:
   `
   GEMINI_API_KEY=your_api_key_here
   `

## Usage

See example_usage.py for a complete example of how to use the tender evaluator.

Basic usage:

`python
from tender_evaluator import TenderEvaluator
import asyncio

async def main():
    evaluator = TenderEvaluator()
    result = await evaluator.evaluate_tender(terms_file, proposal_files, top_n)
    print(result)

asyncio.run(main())
`

## Requirements

- Python 3.9+
- See requirements.txt for package dependencies
