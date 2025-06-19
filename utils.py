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

        logger.info(f"OpenAIExtractor initialized with data: {self.json_data}")
        logger.info(f"OpenAIExtractor initialized with fields: {self.fields}")

    def openai_api_call(self):
        # Build a dynamic prompt
        input_text = self.json_data.get("text", "")
        fields_requested = self.fields

        if isinstance(fields_requested, dict):
            field_list = list(fields_requested.values())
        elif isinstance(fields_requested, list):
            field_list = fields_requested
        else:
            field_list = ["name", "address", "date"]  # default fallback

        field_string = ", ".join(field_list)

        prompt = f"""
                    Given the following text, extract the following fields: {field_string}

                    Text:
                    \"\"\"
                    {input_text}
                    \"\"\"

                    Return the result in JSON format.
                """

        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts structured fields from free-form text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )

        # GPT response will be JSON text; we parse it
        output_text = response.choices[0].message.content.strip()
        try:
            return json.loads(output_text)
        except json.JSONDecodeError:
            return {"error": "Failed to parse GPT output", "raw": output_text}
