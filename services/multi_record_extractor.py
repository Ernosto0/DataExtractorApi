import json
import os
import openai
from dotenv import load_dotenv
from typing import List, Dict, Union
load_dotenv()

import logging

logger = logging.getLogger(__name__)

# TODO: Implement this
# Detect the type of the text
# If the text is more than 2000 characters, return "partial"
# If the text is less than 2000 characters, return "single"
def run(text: str, fields: list = None):
    
    if len(text) > 2000:
        logger.info(f"Text is more than 2000 characters ({len(text)}), using MultiRecordExtractorMulti")
        extractor = MultiRecordExtractorMulti()
        return extractor.extract_records_multi(text, fields)
    else:
        logger.info(f"Text is less than 2000 characters ({len(text)}), using MultiRecordExtractorSingle")
        extractor = MultiRecordExtractorSingle()
        return extractor.extract_records(text, fields)

def _process_fields_input(fields):
    """Process fields input to handle string, list, and dict formats"""
    if fields is None:
        return []
    
    if isinstance(fields, str):
        # If it's a string, treat it as a single field
        return [fields]
    elif isinstance(fields, list):
        # If it's already a list, return as-is
        return fields
    elif isinstance(fields, dict):
        # If it's a dict, use the values
        return list(fields.values())
    else:
        # Fallback: try to convert to list
        return list(fields) if hasattr(fields, '__iter__') else [str(fields)]

class MultiRecordExtractorSingle:
    def __init__(self):
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def extract_records(self, text: str, fields: list = None) -> Union[List[Dict], Dict[str, str]]:
        """
        Extract structured data from unstructured text.
        Returns a list of dictionaries containing the extracted records.
        If an error occurs, returns a dictionary with error details.
        """
        try:
            # Process fields to handle string, list, and dict formats
            processed_fields = _process_fields_input(fields)
            
            # Build the prompt based on whether fields are specified
            if processed_fields:
                fields_instruction = f"Focus on extracting these specific fields: {', '.join(processed_fields)}"
                example_fields = {field: f"value_{i+1}" for i, field in enumerate(processed_fields[:2])}
                example_format = f"[{json.dumps(example_fields)}, {json.dumps(example_fields)}]"
            else:
                fields_instruction = "Extract all relevant fields based on the text content"
                example_format = '[{"field1": "value1", "field2": "value2"}, {"field1": "value3", "field2": "value4"}]'
            
            prompt = f"""
            Extract multiple records from the following text. Each record should be structured as a dictionary.
            Return ONLY a valid JSON array containing all extracted records.

            Text to process:
            \"\"\"
            {text}
            \"\"\"

            Important instructions:
            1. Return ONLY a valid JSON array of objects
            2. {fields_instruction}
            3. Be consistent with field names across all records
            4. Preserve the original values (don't convert currencies, dates, etc.)
            5. Don't add any explanations or notes
            6. Don't include any fields that aren't present in the text
            7. Use clear, descriptive field names
            8. Maintain the order of records as they appear in the text
            9. For numeric values (quantities, amounts, etc.), use numbers instead of strings when possible
            10. For dates, use string format

            Example format:
            {example_format}
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

class MultiRecordExtractorMulti:
    def __init__(self):
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def extract_records_multi(self, text: str, fields: list = None) -> Union[List[Dict], Dict[str, str]]:
        """
        Extract structured data from long unstructured text by processing it in chunks.
        Returns a list of dictionaries containing the extracted records.
        If an error occurs, returns a dictionary with error details.
        """
        try:
            # Process fields to handle string, list, and dict formats
            processed_fields = _process_fields_input(fields)
            
            # Build the prompt based on whether fields are specified
            if processed_fields:
                fields_instruction = f"Focus on extracting these specific fields: {', '.join(processed_fields)}"
                example_fields = {field: f"value_{i+1}" for i, field in enumerate(processed_fields[:2])}
                example_format = f"[{json.dumps(example_fields)}, {json.dumps(example_fields)}]"
            else:
                fields_instruction = "Extract all relevant fields based on the text content"
                example_format = '[{"field1": "value1", "field2": "value2"}, {"field1": "value3", "field2": "value4"}]'
            
            chunk_size = 1000
            all_records = []
            
            start = 0
            while start < len(text):
                chunk = text[start:start+chunk_size]
                
                prompt = f"""
                Extract multiple records from the following text. Each record should be structured as a dictionary.
                Return ONLY a valid JSON array containing all extracted records.

                Text to process:
                \"\"\"
                {chunk}
                \"\"\"

                Important instructions:
                1. Return ONLY a valid JSON array of objects
                2. {fields_instruction}
                3. Be consistent with field names across all records
                4. Preserve the original values (don't convert currencies, dates, etc.)
                5. Don't add any explanations or notes
                6. Don't include any fields that aren't present in the text
                7. Use clear, descriptive field names
                8. Maintain the order of records as they appear in the text
                9. For numeric values (quantities, amounts, etc.), use numbers instead of strings when possible
                10. For dates, use string format

                Example format:
                {example_format}
                """

                try:
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
                    logger.info(f"OpenAI API response for chunk: {output_text}")

                    try:
                        chunk_data = json.loads(output_text)
                        if isinstance(chunk_data, list):
                            all_records.extend(chunk_data)
                            logger.info(f"Extracted {len(chunk_data)} records from chunk")
                        else:
                            logger.warning(f"Chunk returned non-list data: {chunk_data}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse GPT output for chunk: {e}")
                        
                except Exception as e:
                    logger.error(f"OpenAI API call failed for chunk: {e}")
                    
                start += chunk_size

            logger.info(f"Total records extracted: {len(all_records)}")
            return all_records

        except Exception as e:
            logger.error(f"Multi-record extraction failed: {e}")
            return {
                "error": "Extraction failed",
                "details": str(e)
            }

# Keep the original class for backward compatibility
class MultiRecordExtractor(MultiRecordExtractorSingle):
    pass
