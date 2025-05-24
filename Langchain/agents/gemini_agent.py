# agents/gemini_agent.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field, ValidationError
from google_api.calendar import create_calendar_events
import logging
import json
import ast
from typing import Union

logger = logging.getLogger(__name__)

calendar_service_agent = None

def set_services(gcr_s, cal_s):
    global calendar_service_agent
    calendar_service_agent = cal_s
    if calendar_service_agent:
        logger.info("SUCCESS: Calendar service initialized in gemini_agent.")
    else:
        logger.error("FAILURE: Calendar service is None after set_services call in gemini_agent.")

class AddToCalendarInput(BaseModel):
    assignments_to_add: dict = Field(description="A dictionary of assignments to add to the calendar, sourced from the 'structured_assignments_for_calendar' context. Keys are course names, values are dicts with a 'not_submitted' key holding a list of assignment objects (each with 'title', 'due_date', 'due_time').")

@tool(args_schema=AddToCalendarInput, description="Adds provided assignment data to the Google Calendar. Use the structured assignment data provided in the context.")
def add_assignments_to_google_calendar(assignments_to_add: Union[dict, str]) -> str:
    global calendar_service_agent
    logger.info(f"Tool add_assignments_to_google_calendar: Raw input type for assignments_to_add: {type(assignments_to_add)}")
    logger.info(f"Tool add_assignments_to_google_calendar: Raw input value (first 500 chars): {str(assignments_to_add)[:500]}")

    parsed_assignments_data = None
    if isinstance(assignments_to_add, str):
        logger.info("Tool: assignments_to_add is a string, attempting to parse.")
        try:
            parsed_assignments_data = ast.literal_eval(assignments_to_add)
            if not isinstance(parsed_assignments_data, dict):
                logger.error(f"Tool: ast.literal_eval parsed string to {type(parsed_assignments_data)}, not dict.")
                return "Error: Tool received assignment data as a string, and parsing it did not result in a dictionary."
            logger.info("Tool: Successfully parsed string input to dictionary using ast.literal_eval.")
        except (ValueError, SyntaxError, TypeError) as e_ast:
            logger.error(f"Tool: Failed to parse assignments_to_add string with ast.literal_eval: {e_ast}. Trying json.loads.")
            try:
                parsed_assignments_data = json.loads(assignments_to_add)
                if not isinstance(parsed_assignments_data, dict):
                    logger.error(f"Tool: json.loads parsed string to {type(parsed_assignments_data)}, not dict.")
                    return "Error: Tool received assignment data as a string, and parsing it via JSON did not result in a dictionary."
                logger.info("Tool: Successfully parsed string input to dictionary using json.loads.")
            except json.JSONDecodeError as e_json:
                logger.error(f"Tool: Failed to parse assignments_to_add string as JSON: {e_json}")
                return f"Error: The assignment data was a string but could not be parsed into a dictionary. Snippet: {assignments_to_add[:100]}"
    elif isinstance(assignments_to_add, dict):
        parsed_assignments_data = assignments_to_add
        logger.info("Tool: assignments_to_add is already a dictionary.")
    else:
        logger.error(f"Tool: assignments_to_add is an unexpected type: {type(assignments_to_add)}")
        return f"Error: Tool received unexpected data type for assignments: {type(assignments_to_add)}"

    if parsed_assignments_data is None:
         return "Error: Could not obtain a valid dictionary from the assignments_to_add input."

    try:
        validated_input = AddToCalendarInput(assignments_to_add=parsed_assignments_data)
        final_assignments_data = validated_input.assignments_to_add
        logger.info("Tool: Parsed/validated assignments_to_add data structure is a dict.")
    except ValidationError as ve:
        logger.error(f"Tool: Pydantic validation failed for the (parsed) assignments_to_add data: {ve}")
        return f"Error: The assignment data, even after parsing, does not match the expected structure: {ve}"

    if calendar_service_agent is None:
        logger.error("Tool Error: Google Calendar service not initialized.")
        return "Error: Google Calendar service not initialized for the agent."
    
    if not final_assignments_data:
        logger.warning("Tool Warning: final_assignments_data dict is empty after validation.")
        return "Error: The assignment data dictionary is effectively empty or invalid."
    
    try:
        result_message = create_calendar_events(pending_assignments=final_assignments_data, service=calendar_service_agent)
        logger.info(f"Tool Success: create_calendar_events returned: {result_message}")
        return f"Calendar update process finished: {result_message}"
    except Exception as e:
        logger.error(f"Tool Error during create_calendar_events: {e}", exc_info=True)
        return f"An error occurred while adding assignments to calendar: {str(e)}"

LLM_MODEL_NAME = "gemini-1.5-flash"

try:
    llm = ChatGoogleGenerativeAI(
        model=LLM_MODEL_NAME,
        temperature=0.2,
        convert_system_message_to_human=False
    )
    logger.info(f"LLM initialized successfully with model {LLM_MODEL_NAME}")
except Exception as e:
    logger.error(f"CRITICAL: Failed to initialize LLM: {e}", exc_info=True)
    raise

tools_list = [add_assignments_to_google_calendar]

MEMORY_KEY = "chat_history"

# --- CORRECTED SYSTEM PROMPT ---
# This prompt expects 'input', 'chat_history', 'assignment_context', 'Current Date',
# and 'structured_assignments_for_calendar' (implicitly available for tool use guidance)
# It does NOT expect 'Course Name' as a separate top-level variable.
prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful Google Classroom and Calendar assistant.
You will be provided with the Current Date: {Current Date}.
The user's direct query will be in '{input}'.
Context about their assignments will be in '{assignment_context}'.
Structured data for calendar operations is available under 'structured_assignments_for_calendar' in the input dictionary.

Instructions:
1.  Use the '{assignment_context}' and '{Current Date}' to answer questions about assignments (e.g., "what are my assignments?", "what's due today?", "what was due yesterday?").
    When referencing the current day, use the '{Current Date}' provided.
    If you are answering from the context, you can say so. For example: "Based on your last fetched assignments and today's date ({Current Date}): ..."

2.  If the user asks to add assignments to the calendar, you MUST use the 'add_assignments_to_google_calendar' tool.
    When you decide to call this tool, the 'assignments_to_add' argument for the tool MUST BE EXACTLY the content of the 'structured_assignments_for_calendar' variable that is provided to you in the overall input.
    The tool expects 'assignments_to_add' as a JSON dictionary object. Do NOT provide it as a string.
    Example of the structure for 'assignments_to_add':
    {{"Course Name 1": {{"not_submitted": [{{"title": "HW1", "due_date": "YYYY-MM-DD", "due_time": "HH:MM"}}]}}, "Course Name 2": ...}}

Assignment Summary Context to refer to:
{assignment_context}
"""),
    MessagesPlaceholder(variable_name=MEMORY_KEY), # For conversational history
    ("user", "{input}"), # The user's actual typed query
    MessagesPlaceholder(variable_name="agent_scratchpad") # For agent's intermediate steps
])
# --- END OF CORRECTED SYSTEM PROMPT ---

try:
    # create_tool_calling_agent will build the runnable that passes the correct inputs to the prompt
    agent_runnable = create_tool_calling_agent(llm, tools_list, prompt)
    logger.info("Agent runnable created successfully using create_tool_calling_agent.")

    agent_executor = AgentExecutor(
        agent=agent_runnable,
        tools=tools_list,
        verbose=True,
        handle_parsing_errors="I encountered an issue processing that request. Please try rephrasing. (Agent Error)",
        max_iterations=5,
        return_intermediate_steps=True
    )
    logger.info("Agent executor initialized with create_tool_calling_agent.")

except ImportError as ie:
    logger.error(f"ImportError: Failed to import create_tool_calling_agent. Error: {ie}", exc_info=True)
    raise
except Exception as e:
    logger.error(f"CRITICAL: Failed to initialize agent executor: {e}", exc_info=True)
    raise