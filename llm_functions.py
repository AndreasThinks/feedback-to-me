"""
Functions for processing feedback using LLMs via OpenRouter and LangChain.

Required packages:
    pip install langchain-openai openai pydantic

This module uses LangChain's ChatOpenAI with OpenRouter as the provider,
and structured output with Pydantic models.
"""

import os
from typing import List, Dict, Optional, Union
import json

from pydantic import BaseModel, Field
from langchain.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI


# Configure logger for debugging
from utils import logger

from config import (
    OPENROUTER_API_KEY,
    LLM_MODEL_FAST,
    LLM_MODEL_REASONING,
    LLM_MODEL_FAST_FALLBACK,
    LLM_MODEL_REASONING_FALLBACK
)

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
class AnonymizedTheme(BaseModel):
    original: str = Field(description="The original theme text")
    anonymized: str = Field(description="The anonymized version of the theme, if needed")
    needs_anonymization: bool = Field(description="Whether the theme needs anonymization")
    sentiment: str = Field(description="The sentiment of the theme (positive/negative/neutral)")

class AnonymizedThemesResponse(BaseModel):
    themes: List[AnonymizedTheme] = Field(description="List of themes with anonymization status")

class ThemesResponse(BaseModel):
    positive: List[str]
    negative: List[str]
    neutral: List[str]

def create_feedback_llm(model_name: str, fallback_model: Optional[str] = None, is_fallback: bool = False) -> ChatOpenAI:
    """
    Creates and configures the LangChain ChatOpenAI model for feedback processing via OpenRouter.
    
    Args:
        model_name: The primary model to use (e.g., "google/gemini-2.0-flash-001")
        fallback_model: Optional fallback model to use if primary fails
        is_fallback: Whether this is a fallback attempt (for logging)
    
    Returns:
        ChatOpenAI instance configured for OpenRouter
    """
    model_type = "fallback" if is_fallback else "primary"
    logger.debug(f"Creating LLM instance using {model_type} model: {model_name}")
    
    llm_instance = ChatOpenAI(
        model=model_name,
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        temperature=1,
        max_tokens=8192,
        model_kwargs={
            "top_p": 0.95,
        }
    )
    logger.debug(f"LLM instance created successfully with {model_type} model: {model_name}")
    return llm_instance

def check_theme_anonymity(themes: ThemesResponse) -> AnonymizedThemesResponse:
    """
    Analyzes themes for personally identifiable information and anonymizes if needed.
    Uses the fast model with automatic fallback support.
    
    Args:
        themes: ThemesResponse object containing positive, negative, and neutral themes
        
    Returns:
        AnonymizedThemesResponse containing original and potentially anonymized themes
    """
    try:
        logger.debug("Starting theme anonymity check.")
        
        # Try primary model first
        try:
            llm = create_feedback_llm(LLM_MODEL_FAST)
            result = _check_theme_anonymity_with_llm(llm, themes)
            logger.info(f"Anonymity check completed successfully with primary model: {LLM_MODEL_FAST}")
            return result
        except Exception as e:
            logger.warning(f"Primary model {LLM_MODEL_FAST} failed: {str(e)}. Trying fallback...")
            
            # Fallback to alternative model
            llm = create_feedback_llm(LLM_MODEL_FAST_FALLBACK, is_fallback=True)
            result = _check_theme_anonymity_with_llm(llm, themes)
            logger.info(f"Anonymity check completed successfully with fallback model: {LLM_MODEL_FAST_FALLBACK}")
            return result
        
    except Exception as e:
        logger.error(f"Error during anonymity check (all models failed): {str(e)}")
        return None

def _check_theme_anonymity_with_llm(llm: ChatOpenAI, themes: ThemesResponse) -> AnonymizedThemesResponse:
    """
    Internal function to perform anonymity check with a given LLM instance.
    """
    parser = PydanticOutputParser(pydantic_object=AnonymizedThemesResponse)
    format_instructions = parser.get_format_instructions()
    
    prompt = f"""Analyze these feedback themes for personally identifiable information or specific events that could identify individuals.
For each theme:
1. Check for:
   - Names of people, teams, or organizations
   - Specific events or dates
   - Unique situations or projects
   - Client or stakeholder references
2. If found, create an anonymized version that preserves the core feedback while removing identifying details
3. If no identifying information is found, keep the original text

Example transformations:
- Original: "You helped John from Marketing with the Q4 campaign"
  Anonymized: "You provided valuable support to colleagues with major marketing campaigns"
- Original: "Your presentation to Client XYZ was excellent"
  Anonymized: "Your client presentations are excellent"

{format_instructions}

Themes to analyze:
{json.dumps(themes.dict(), indent=2)}"""

    logger.debug("Sending prompt to LLM for anonymity check.")
    messages = [
        ("system", "You are a helpful assistant who helps collect and anonymise 360 feedback requests."),
        ("human", prompt)
    ]
    response = llm.invoke(messages)
    logger.debug("Received response from LLM for anonymity check.")
    
    result = parser.parse(response.content)
    logger.debug("Anonymity check completed successfully.")
    return result

def convert_feedback_text_to_themes(feedback_text: str) -> Optional[Dict[str, List[str]]]:
    """
    Process feedback text using LangChain and OpenRouter to extract themes and sentiments.
    Uses the fast model with automatic fallback support.
    
    Args:
        feedback_text: The raw feedback text to process.
    
    Returns:
        Dictionary containing positive, negative, and neutral theme lists,
        or None if processing fails.
    """
    try:
        logger.debug("Starting to convert feedback text to themes.")
        
        # Try primary model first
        try:
            llm = create_feedback_llm(LLM_MODEL_FAST)
            result = _convert_feedback_with_llm(llm, feedback_text)
            logger.info(f"Feedback conversion completed successfully with primary model: {LLM_MODEL_FAST}")
            return result
        except Exception as e:
            logger.warning(f"Primary model {LLM_MODEL_FAST} failed: {str(e)}. Trying fallback...")
            
            # Fallback to alternative model
            llm = create_feedback_llm(LLM_MODEL_FAST_FALLBACK, is_fallback=True)
            result = _convert_feedback_with_llm(llm, feedback_text)
            logger.info(f"Feedback conversion completed successfully with fallback model: {LLM_MODEL_FAST_FALLBACK}")
            return result
        
    except Exception as e:
        logger.error(f"Error processing feedback (all models failed): {str(e)}")
        return None

def _convert_feedback_with_llm(llm: ChatOpenAI, feedback_text: str) -> Dict[str, List[str]]:
    """
    Internal function to convert feedback to themes with a given LLM instance.
    """
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
    messages = [
        ("system", "You are a helpful assistant who helps collect and anonymise 360 feedback requests."),
        ("human", prompt)
    ]
    response = llm.invoke(messages)
    logger.debug("Received response from LLM for feedback conversion.")
    logger.debug(f"Raw LLM response: {response.content}")
    
    # Parse the structured output using the Pydantic model
    initial_themes = parser.parse(response.content)
    # Ensure all required keys even if empty lists
    for key in ["positive", "negative", "neutral"]:
        if getattr(initial_themes, key) is None:
            setattr(initial_themes, key, [])
    
    # Check themes for PII and anonymize if needed
    logger.debug("Checking themes for personally identifiable information.")
    anonymized_result = check_theme_anonymity(initial_themes)
    
    if anonymized_result:
        # Convert anonymized themes back to the original format
        result = {"positive": [], "negative": [], "neutral": []}
        for theme in anonymized_result.themes:
            theme_text = theme.anonymized if theme.needs_anonymization else theme.original
            result[theme.sentiment].append(theme_text)
        logger.debug("Themes processed and anonymized successfully.")
        return result
    else:
        logger.debug("Anonymization check failed, returning original themes.")
        return initial_themes.dict()

def generate_completed_feedback_report(feedback_input: str) -> tuple[str, str]:
    """
    Takes formatted feedback data and generates a comprehensive feedback report using OpenRouter.
    Uses the reasoning model with automatic fallback support.

    Args:
        feedback_input: Formatted string containing feedback data with quality ratings and themed feedback.

    Returns:
        A tuple of:
            1) The prompt sent to the LLM
            2) The markdown-formatted feedback report string.
    """
    try:
        logger.debug("Starting generation of complete feedback report.")

        # Create a structured prompt emphasizing the layout and confidentiality
        prompt = f"""
You are a professional coach specializing in personal development. Your task is to create a well-structured, concise, and constructive feedback report in **markdown format**, based on the feedback information provided below.

## Important Instructions

1. **High-Level Focus**:
   - Concentrate on trends, themes, and major takeaways. Avoid excessive detail or raw data references.
2. **Numerical Ratings** (if applicable):
   - Examine how scores might differ by role (peers, managers, etc.) or by theme.
   - Identify meaningful gaps or variations to guide actionable feedback.
3. **Actionable Feedback**:
   - Use a **Continue / Stop / Start** framework to give clear recommendations for growth.
   - Prioritize professional, constructive, and supportive language.
4. **Confidentiality & Anonymity**:
   - Do not reference any specific individuals or the underlying data sources.
   - Do not reveal how or why the report is generated; just present it as a synthesized coaching document.
5. **Report Structure**:
   - **Introduction**: Brief, positive opening to set the tone.
   - **Key Trends & Takeaways**: High-level overview of strengths and areas for growth.
   - **Detailed Observations**: Summarize 2–3 main themes (e.g., Communication, Leadership, etc.). Include role-based variations if relevant, always protecting anonymity.
   - **Action Plan**:
       - **Continue**: Reinforce current strengths and positive behaviors.
       - **Stop**: Identify counterproductive behaviors or habits.
       - **Start**: Suggest new approaches or habits for improvement.
   - **Conclusion**: A short, encouraging wrap-up with final thoughts on development.

Below is the feedback data for your analysis. Please generate a **markdown-formatted report** following the structure above. Do not provide any text beyond the markdown report itself.

Feedback Data:
{feedback_input}

Remember, do not disclose anything about the data source or generation process. Speak directly to the recipient as their coach, focusing on personal development.
Remember to output ONLY MARKDOWN, directly. 

Start your report with this line
**Introduction:**
"""

        # Try primary model first
        try:
            logger.debug(f"Attempting report generation with primary model: {LLM_MODEL_REASONING}")
            llm = create_feedback_llm(LLM_MODEL_REASONING)
            markdown_output = _generate_report_with_llm(llm, prompt)
            logger.info(f"Report generation completed successfully with primary model: {LLM_MODEL_REASONING}")
            return prompt, markdown_output
        except Exception as e:
            logger.warning(f"Primary model {LLM_MODEL_REASONING} failed: {str(e)}. Trying fallback...")
            
            # Fallback to alternative model
            llm = create_feedback_llm(LLM_MODEL_REASONING_FALLBACK, is_fallback=True)
            markdown_output = _generate_report_with_llm(llm, prompt)
            logger.info(f"Report generation completed successfully with fallback model: {LLM_MODEL_REASONING_FALLBACK}")
            return prompt, markdown_output

    except Exception as e:
        logger.error(f"Error generating feedback report (all models failed): {str(e)}")
        return "Error: Unable to generate feedback report. Please try again later.", ""

def _generate_report_with_llm(llm: ChatOpenAI, prompt: str) -> str:
    """
    Internal function to generate report with a given LLM instance.
    """
    logger.debug("Sending prompt to LLM for feedback report generation.")
    
    messages = [
        ("system", "You are a professional coach specializing in personal development."),
        ("human", prompt)
    ]
    response = llm.invoke(messages)
    
    logger.debug("Received response from LLM for feedback report generation.")
    logger.debug("Feedback report generated successfully.")
    
    # Clean up or post-process the markdown if needed
    markdown_output = clean_markdown(response.content)
    
    return markdown_output
