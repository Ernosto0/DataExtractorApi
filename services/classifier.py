import json
import os
import openai
from dotenv import load_dotenv
load_dotenv()

import logging

logger = logging.getLogger(__name__)

# TODO: Implement this
# Detect the type of the text
# If the text is more than 2000 characters, return "partial"
# If the text is less than 2000 characters, return "single"
def run(text: str, fields: list):
    
    if len(text) > 2000:
        logger.info(f"Text is more than 2000 characters ({len(text)}), using OpenAIClassifierMulti")
        openai_classifier = OpenAIClassifierMulti({"text": text}, fields=fields)
        return openai_classifier.openai_api_callmulti()
    else:
        logger.info(f"Text is less than 2000 characters ({len(text)}), using OpenAIClassifierSingle")
        openai_classifier = OpenAIClassifierSingle({"text": text}, fields=fields)
        return openai_classifier.openai_api_call()

def _process_fields_input(fields):
    """Process fields input to handle string, list, and dict formats"""
    if fields is None:
        return []
    
    if isinstance(fields, str):
        # If it's a string, treat it as a single label
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

class OpenAIClassifierSingle:
    def __init__(self, json_data: dict, fields=None):
        self.json_data = json_data
        self.fields = fields
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        logger.info(f"OpenAIClassifierSingle initialized with data: {self.json_data}")
        logger.info(f"OpenAIClassifierSingle initialized with fields: {self.fields}")

    def openai_api_call(self):
        text = self.json_data.get("text", "")
        if not text:
            return {"error": "No text provided for classification"}

        # Process fields to handle string, list, and dict formats
        processed_fields = _process_fields_input(self.fields)
        if not processed_fields:
            return {"error": "No valid labels provided for classification"}

        # Create the prompt for classification
        labels_str = ", ".join(processed_fields)
        prompt = f"""Classify the following text into one or more of these categories: {labels_str}

Text: {text}

Return the result as a JSON object with a 'labels' key containing an array of matched labels. Only include labels that are relevant to the text."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a precise text classification assistant that returns only valid JSON with matched labels."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
            )

            output_text = response.choices[0].message.content.strip()
            logger.info(f"OpenAI API call response: {output_text}")
            
            try:
                result = json.loads(output_text)
                if not isinstance(result.get("labels"), list):
                    return {
                        "error": "Invalid classification result format",
                        "details": "Expected 'labels' array in response"
                    }
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse GPT output: {e}")
                return {
                    "error": "Failed to parse classification result",
                    "details": str(e),
                    "raw": output_text
                }
                
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            return {
                "error": "Classification failed",
                "details": str(e)
            }

class OpenAIClassifierMulti:
    def __init__(self, json_data: dict, fields=None):
        self.json_data = json_data
        self.fields = fields
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        logger.info(f"OpenAIClassifierMulti initialized with data: {self.json_data}")
        logger.info(f"OpenAIClassifierMulti initialized with fields: {self.fields}")

    def openai_api_callmulti(self):
        input_text = self.json_data.get("text", "")
        if not input_text:
            return {"error": "No text provided for classification"}

        # Process fields to handle string, list, and dict formats
        processed_fields = _process_fields_input(self.fields)
        if not processed_fields:
            return {"error": "No valid labels provided for classification"}

        labels_str = ", ".join(processed_fields)
        chunk_size = 1000
        all_labels = set()

        start = 0
        while start < len(input_text):
            chunk = input_text[start:start+chunk_size]

            prompt = f"""Classify the following text into one or more of these categories: {labels_str}

Text: {chunk}

Return the result as a JSON object with a 'labels' key containing an array of matched labels. Only include labels that are relevant to the text."""

            try:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are a precise text classification assistant that returns only valid JSON with matched labels."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                )

                output_text = response.choices[0].message.content.strip()
                logger.info(f"OpenAI API call response: {output_text}")
                
                try:
                    chunk_result = json.loads(output_text)
                    if isinstance(chunk_result.get("labels"), list):
                        all_labels.update(chunk_result["labels"])
                    logger.info(f"Classified chunk labels: {chunk_result.get('labels', [])}")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse GPT output for chunk: {e}")
                    
            except Exception as e:
                logger.error(f"OpenAI API call failed for chunk: {e}")
                
            start += chunk_size

        # Return consolidated results
        result = {"labels": list(all_labels)}
        logger.info(f"Final classification result: {result}")
        return result

# Keep the original class for backward compatibility
class OpenAIClassifier(OpenAIClassifierSingle):
    pass