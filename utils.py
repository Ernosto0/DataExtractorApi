import openai
import os
import json
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class DataExtractor:
    def __init__(self, json_data: dict):
        self.json_data = json_data

    def extract_data(self):
        return self.json_data

    def extract_data_from_json(self):
        return self.json_data

    def extract_data_from_csv(self):
        return self.json_data

    def extract_data_from_excel(self):
        # TODO: Implement Excel reading
        return self.json_data


class OpenAIExtractor:
    def __init__(self, json_data: dict, fields=None):
        self.json_data = json_data
        self.fields = fields
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        logger.info(f"OpenAIExtractor initialized with data: {self.json_data}")
        logger.info(f"OpenAIExtractor initialized with fields: {self.fields}")

    def _process_fields(self):
        """Process fields to handle both list and dict formats"""
        if self.fields is None:
            return [], {}
            
        if isinstance(self.fields, dict):
            # Create a mapping of original field to alias
            field_mapping = {v: k for k, v in self.fields.items()}
            field_list = list(self.fields.values())
        else:
            # For list format, use the same name for both original and alias
            field_mapping = {field: field for field in self.fields}
            field_list = self.fields

        return field_list, field_mapping

    def openai_api_call(self):
        input_text = self.json_data.get("text", "")
        field_list, field_mapping = self._process_fields()

        if not field_list:
            raise ValueError("No valid fields specified for extraction")

        field_string = ", ".join(field_list)
        
        # Enhanced prompt to ensure consistent JSON output with proper type handling
        prompt = f"""
            Given the following text, extract these specific fields: {field_string}
            
            Text:
            \"\"\"
            {input_text}
            \"\"\"
            
            Important instructions:
            1. Return ONLY a valid JSON object
            2. Include ALL requested fields in the output
            3. Use null for any fields that cannot be found or are uncertain
            4. Do not include any additional fields
            5. Do not include any explanations or notes
            6. For numeric values (quantities, amounts, etc.), use numbers instead of strings
            7. For dates, use string format
            8. For currency amounts, return only the numeric value without currency symbols
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a precise data extraction assistant that returns only valid JSON. For numeric fields like quantities and amounts, use numbers instead of strings. For dates, use strings. For currency, extract only the numeric value."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
            )

            output_text = response.choices[0].message.content.strip()
            
            try:
                extracted_data = json.loads(output_text)
                
                # Process the extracted data
                processed_result = {}
                for original_field, alias in field_mapping.items():
                    value = extracted_data.get(original_field)
                    # Convert string numbers to actual numbers if possible
                    if isinstance(value, str) and value.replace('.', '').isdigit():
                        try:
                            # Convert to int if no decimal point, float if there is one
                            value = int(value) if '.' not in value else float(value)
                        except (ValueError, TypeError):
                            pass
                    processed_result[alias] = value
                
                return processed_result
                
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
