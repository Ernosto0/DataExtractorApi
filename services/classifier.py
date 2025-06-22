import json
import os
import openai
from dotenv import load_dotenv
load_dotenv()

import logging

logger = logging.getLogger(__name__)

class OpenAIClassifier:
    def __init__(self, json_data: dict, fields=None):
        self.json_data = json_data
        self.fields = fields
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        logger.info(f"OpenAIClassifier initialized with data: {self.json_data}")
        logger.info(f"OpenAIClassifier initialized with fields: {self.fields}")

    def openai_api_call(self):
        text = self.json_data.get("text", "")
        if not text:
            return {"error": "No text provided for classification"}

        # Create the prompt for classification
        labels_str = ", ".join(self.fields)
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