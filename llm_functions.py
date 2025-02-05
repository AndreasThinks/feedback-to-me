"""
Functions for processing feedback using Google's Gemini LLM.

Install the required SDK:
$ pip install google.ai.generativelanguage
"""

import os
import json
import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content
from typing import Dict, List, Optional

# Configure Gemini with API key
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

def create_feedback_model():
    """Create and configure the Gemini model for feedback processing."""
    generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
        "response_schema": content.Schema(
            type=content.Type.OBJECT,
            enum=[],
            required=["positive_themes", "negative_themes", "neutral_themes"],
            properties={
                "positive_themes": content.Schema(
                    type=content.Type.ARRAY,
                    items=content.Schema(
                        type=content.Type.STRING,
                    ),
                ),
                "negative_themes": content.Schema(
                    type=content.Type.ARRAY,
                    items=content.Schema(
                        type=content.Type.STRING,
                    ),
                ),
                "neutral_themes": content.Schema(
                    type=content.Type.ARRAY,
                    items=content.Schema(
                        type=content.Type.STRING,
                    ),
                ),
            },
        ),
        "response_mime_type": "application/json",
    }

    return genai.GenerativeModel(
        model_name="gemini-1.5-flash-8b",
        generation_config=generation_config,
        system_instruction="You are a helpful assistant who helps collect and anonymise 360 feedback requests.",
    )

def convert_feedback_text_to_themes(feedback_text: str) -> Optional[Dict[str, List[str]]]:
    """
    Process feedback text using Gemini to extract themes and sentiments.
    
    Args:
        feedback_text: The raw feedback text to process
        
    Returns:
        Dictionary containing positive_themes, negative_themes, and neutral_themes lists,
        or None if processing fails
    """
    try:
        model = create_feedback_model()
        prompt = f"""Please read the feedback paragraph below, and convert it into a series of positive, negative, and neutral traits. 
Each trait should be a single sentence, and should ensure the feedback is totally anonymous.

Examples of positive traits: 
- You thrive under pressure
- You always show initiative
- You are friendly and nice

Example of negative traits:
- You can withdraw when scared
- You can let your temper get the better of you

Example of neutral traits:
- You tend to work independently
- You maintain a consistent schedule

The feedback paragraph is below. Please return an array of positive, negative, and neutral traits as requested, 
or leave the array as empty if you can't find anything matching that sentiment.

Feedback:
{feedback_text}"""

        chat = model.start_chat()
        response = chat.send_message(prompt)
        
        # Extract JSON from response
        json_str = response.text
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        
        result = json.loads(json_str)
        
        # Ensure all required keys exist
        for key in ["positive_themes", "negative_themes", "neutral_themes"]:
            if key not in result:
                result[key] = []
                
        return result
        
    except Exception as e:
        print(f"Error processing feedback: {str(e)}")
        return None

def generate_completed_feedback_report():
    """Takes a list of scores and feedback themes, and generates a final report."""

    # TODO: Implement this function
    pass