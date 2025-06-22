import json
import os
import openai
from dotenv import load_dotenv
from typing import List, Dict, Union
load_dotenv()

import logging

logger = logging.getLogger(__name__)

class MultiRecordExtractor:
    def __init__(self):
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def extract_records(self, text: str) -> Union[List[Dict], Dict[str, str]]:
        """
        Extract structured data from unstructured text.
        Returns a list of dictionaries containing the extracted records.
        If an error occurs, returns a dictionary with error details.
        """
        try:
            prompt = f"""
            Extract multiple records from the following text. Each record should be structured as a dictionary.
            Return ONLY a valid JSON array containing all extracted records.

            Text to process:
            \"\"\"
            {text}
            \"\"\"

            Important instructions:
            1. Return ONLY a valid JSON array of objects
            2. Each object should contain relevant fields based on the text
            3. Be consistent with field names across all records
            4. Preserve the original values (don't convert currencies, dates, etc.)
            5. Don't add any explanations or notes
            6. Don't include any fields that aren't present in the text
            7. Use clear, descriptive field names
            8. Maintain the order of records as they appear in the text

            Example format:
            [
                {{"field1": "value1", "field2": "value2"}},
                {{"field1": "value3", "field2": "value4"}}
            ]
            """

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise data extraction assistant that extracts multiple records from text and returns them as a JSON array. Each record should be structured consistently with appropriate field names."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for consistent results
            )

            output_text = response.choices[0].message.content.strip()
            logger.info(f"OpenAI API response: {output_text}")

            try:
                extracted_data = json.loads(output_text)
                if not isinstance(extracted_data, list):
                    return {
                        "error": "Invalid format",
                        "details": "Expected a JSON array of records"
                    }
                return extracted_data

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse GPT output: {e}")
                return {
                    "error": "Failed to parse extraction result",
                    "details": str(e),
                    "raw": output_text
                }

        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            return {
                "error": "Extraction failed",
                "details": str(e)
            }
        