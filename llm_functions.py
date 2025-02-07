"""
Functions for processing feedback using Google's Gemini models via LangChain.

Required packages:
    pip install langchain-google-genai pydantic

This module uses LangChain's ChatGoogleGenerativeAI and structured output with a Pydantic model.
"""

import os
import json
import logging
from typing import List, Dict, Optional

from pydantic import BaseModel
from langchain.output_parsers import PydanticOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI

# Configure logger for debugging
from utils import logger


def clean_markdown(text: str) -> str:
    """
    Cleans markdown text from LLM output by removing unnecessary code block markers.
    
    Args:
        text (str): The input text that may contain markdown with or without code block markers
        
    Returns:
        str: Clean markdown text with any surrounding code block markers removed
    """
    # Strip whitespace first
    text = text.strip()
    
    # Check if text starts with ```markdown and ends with ```
    if text.startswith('```markdown') and text.endswith('```'):
        # Remove the opening ```markdown and closing ```
        text = text[len('```markdown'):].rstrip('`').strip()
    # Check if text just starts and ends with ``` (language not specified)
    elif text.startswith('```') and text.endswith('```'):
        # Remove the opening and closing ```
        text = text[3:].rstrip('`').strip()
        
    return text

# Define a Pydantic model for structured output
class ThemesResponse(BaseModel):
    positive: List[str]
    negative: List[str]
    neutral: List[str]

def create_feedback_llm() -> ChatGoogleGenerativeAI:
    """
    Creates and configures the LangChain ChatGoogleGenerativeAI model for feedback processing.
    Uses the Google Gemini flash-lite model.
    """
    logger.debug("Creating LLM instance using Gemini flash-lite preview model.")
    llm_instance = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-lite-preview-02-05",
        api_key=os.getenv("GEMINI_API_KEY"),
        temperature=1,
        max_tokens=8192,
        top_p=0.95,
        top_k=40,
        system_message="You are a helpful assistant who helps collect and anonymise 360 feedback requests."
    )
    logger.debug("LLM instance created successfully.")
    return llm_instance

def convert_feedback_text_to_themes(feedback_text: str) -> Optional[Dict[str, List[str]]]:
    """
    Process feedback text using LangChain and Google Gemini to extract themes and sentiments.
    
    Args:
        feedback_text: The raw feedback text to process.
    
    Returns:
        Dictionary containing positive, negative, and neutral theme lists lists,
        or None if processing fails.
    """
    try:
        logger.debug("Starting to convert feedback text to themes.")
        # Create the LLM instance
        llm = create_feedback_llm()
        
        # Create a structured output parser using the Pydantic model
        parser = PydanticOutputParser(pydantic_object=ThemesResponse)
        format_instructions = parser.get_format_instructions()
        
        prompt = f"""Please read the feedback paragraph below, and convert it into a series of positive, negative, and neutral traits.
Each trait should be a single sentence. Ensure that the feedback is totally anonymous.
Examples:

Positive traits:
- You thrive under pressure
- You always show initiative
- You are friendly and nice

Negative traits:
- You can withdraw when scared
- You can let your temper get the better of you

Neutral traits:
- You tend to work independently
- You maintain a consistent schedule

Return the output in JSON format as described below.
{format_instructions}

Feedback:
{feedback_text}"""
        
        logger.debug("Sending prompt to LLM for feedback conversion.")
        # Invoke the LLM; message order: system message is already set during llm creation.
        messages = [("human", prompt)]
        response = llm.invoke(messages)
        logger.debug("Received response from LLM for feedback conversion.")
        logger.debug(f"Raw LLM response: {response.content}")
        
        # Parse the structured output using the Pydantic model
        result = parser.parse(response.content)
        # Ensure all required keys even if empty lists
        for key in ["positive", "negative", "neutral"]:
            if getattr(result, key) is None:
                setattr(result, key, [])
        logger.debug("Feedback conversion parsed successfully.")
        return result.dict()
        
    except Exception as e:
        logger.error(f"Error processing feedback: {str(e)}")
        return None

def generate_completed_feedback_report(feedback_input: str) -> str:
    """
    Takes formatted feedback data and generates a comprehensive feedback report using Google Gemini via LangChain.
    
    Args:
        feedback_input: Formatted string containing feedback data with quality ratings and themed feedback.
        
    Returns:
        A markdown-formatted feedback report string.
    """
    try:
        logger.debug("Starting generation of complete feedback report.")
        # Instantiate LLM for report generation using a different Gemini model
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-001",
            api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.7,
            max_tokens=8192,
            top_p=0.8,
            top_k=40
        )
        
        prompt = f"""You are a professional feedback report writer. Your task is to analyze the feedback data below and create a comprehensive, well-structured feedback report in markdown format.

The report should:
1. Start with an executive summary highlighting key strengths and areas for improvement.
2. Include a detailed analysis of the quality ratings, explaining their meaning.
3. Discuss the identified themes by grouping related feedback together.
4. Provide actionable recommendations based on the feedback.
5. Use a professional, constructive tone throughout.
6. Format everything in markdown for easy reading.
7. Do not output anything other than the markdown text.

Here is the feedback data to analyze:

{feedback_input}

Please generate a comprehensive feedback report that is:
- Well-structured with clear sections.
- Written in a professional tone.
- Balanced between strengths and areas for improvement.
- Focused on actionable insights.
- Fully formatted in markdown with appropriate headers and bullet points.

You should return the markdown directly, with no additional formatting needed. JUST OUTPUT THE MARKDOWN."""
        
        logger.debug("Sending prompt to LLM for feedback report generation.")
        messages = [("human", prompt)]
        response = llm.invoke(messages)
        logger.debug("Received response from LLM for feedback report generation.")
        logger.debug("Feedback report generated successfully.")
        markdown_output = clean_markdown(response.content)
        return  markdown_output
        
    except Exception as e:
        logger.error(f"Error generating feedback report: {str(e)}")
        return "Error: Unable to generate feedback report. Please try again later."
if __name__ == "__main__":
    logger.debug("Executing example usage from llm_functions main block.")
    # Example usage for generating a complete feedback report
    sample_feedback = (
        "I find that you always show initiative but sometimes you let your temper get the better of you. "
        "However, overall you tend to work independently and thrive under pressure."
    )
    
    logger.debug("Extracting themes from sample feedback.")
    themes = convert_feedback_text_to_themes(sample_feedback)
    logger.debug(f"Extracted Themes: {themes}")
    print("Extracted Themes:")
    print(themes)
    
    # Generate a complete feedback report using the extracted themes combined with quality ratings
    # Here, we assume a sample quality rating and include the themes in the input data.
    feedback_input = f"Quality Ratings: 4.5/5\nThemes: {themes}"
    logger.debug("Generating feedback report using provided feedback input.")
    report = generate_completed_feedback_report(feedback_input)
    logger.debug("Feedback Report generated:")
    logger.debug(report)
    print("\nFeedback Report:")
    print(report)
