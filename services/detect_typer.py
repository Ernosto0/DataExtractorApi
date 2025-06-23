import json
import os
import openai
from dotenv import load_dotenv
from typing import List, Dict, Union
load_dotenv()

import logging

logger = logging.getLogger(__name__)


class DetectTyper:
    def __init__(self, text: str, fields: List[str]):
        self.text = text
        self.fields = fields
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def detect_type(self) -> Dict[str, str]:
        try:
            fields_str = ", ".join(self.fields)
            prompt = f"""Given the following text, detect and extract the precise data type for each specified field.
            Text: {self.text}
            
            Fields to analyze: {fields_str}
            
            For each field, determine its exact data type using ONLY these categories:
            - string: for general text without specific format
            - email: for email addresses
            - phone: for phone numbers
            - date: for any date format
            - currency: for monetary values
            - integer: for whole numbers
            - float: for decimal numbers
            - boolean: for true/false values
            - url: for web addresses
            - address: for physical addresses
            - id: for any kind of identifier or reference number
            - enum: for fields with a fixed set of possible values
            - json: for structured data
            - timestamp: for date-time values
            - ipv4: for IPv4 addresses
            - ipv6: for IPv6 addresses
            - uuid: for UUID format
            - base64: for base64 encoded data
            
            Return the response in this format:
            {{"field_name": "data_type"}}
            
            Example response:
            {{
                "name": "string",
                "email": "email",
                "phone": "phone",
                "order_id": "id",
                "amount": "currency",
                "is_active": "boolean",
                "created_at": "timestamp"
            }}
            """

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1  # Lower temperature for more consistent type detection
            )

            result = response.choices[0].message.content
            
            # Try to parse the response as JSON
            try:
                if isinstance(result, str):
                    result_dict = json.loads(result)
                else:
                    result_dict = result
                
                # Validate that all requested fields are present
                missing_fields = set(self.fields) - set(result_dict.keys())
                if missing_fields:
                    logger.warning(f"Missing fields in response: {missing_fields}")
                    for field in missing_fields:
                        result_dict[field] = "string"  # Default to string for missing fields
                
                # Validate that all types are from our allowed set
                allowed_types = {
                    "string", "email", "phone", "date", "currency", "integer", 
                    "float", "boolean", "url", "address", "id", "enum", "json",
                    "timestamp", "ipv4", "ipv6", "uuid", "base64"
                }
                
                for field, type_ in result_dict.items():
                    if type_ not in allowed_types:
                        logger.warning(f"Invalid type '{type_}' for field '{field}', defaulting to 'string'")
                        result_dict[field] = "string"
                
                return result_dict
                
            except json.JSONDecodeError:
                logger.error(f"Failed to parse AI response as JSON: {result}")
                return {field: "string" for field in self.fields}

        except Exception as e:
            logger.error(f"Error in detect_type: {str(e)}")
            raise Exception(f"Failed to detect types: {str(e)}")