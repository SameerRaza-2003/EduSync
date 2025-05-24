# main.py
import streamlit as st
from auth.google_auth import get_credentials
from agents import gemini_agent # Agent module
from google_api.classroom import get_coursework_with_submissions, get_pending_assignments_for_calendar
from utils.google_services import get_service
from langchain_core.messages import HumanMessage, AIMessage
import logging
import json # For pretty printing dictionaries/lists
import datetime # To get the current date

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

st.set_page_config(page_title="📘 Google Classroom Assistant", layout="wide")
st.title("📘 Google Classroom Assignment Assistant")

# Initialize session state variables
if "creds" not in st.session_state:
    st.session_state.creds = None
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "assignment_summary_context" not in st.session_state:
    st.session_state.assignment_summary_context = "No assignments fetched yet. Please log in or refresh."
if "structured_assignments_for_calendar" not in st.session_state:
    st.session_state.structured_assignments_for_calendar = {}
if "gcr_service" not in st.session_state:
    st.session_state.gcr_service = None
if "calendar_service_main" not in st.session_state:
    st.session_state.calendar_service_main = None


def fetch_and_store_assignments():
    if st.session_state.creds and st.session_state.gcr_service:
        logger.info("MAIN: Attempting to fetch assignments...")
        with st.spinner("🔄 Fetching your Google Classroom assignments..."):
            try:
                summary_str = get_coursework_with_submissions(st.session_state.gcr_service)
                st.session_state.assignment_summary_context = summary_str if summary_str else "No assignment summary found or an error occurred."
                
                structured_data = get_pending_assignments_for_calendar(st.session_state.gcr_service)
                st.session_state.structured_assignments_for_calendar = structured_data if structured_data else {}

                if summary_str or structured_data: # Check if either has data
                    st.success("✅ Assignments fetched and updated!")
                    logger.info("MAIN: Assignments fetched successfully.")
                else:
                    st.warning("⚠️ No assignments found or an issue occurred during fetch.")
                    logger.info("MAIN: No assignments found or an issue during fetch.")

            except Exception as e:
                st.error(f"Failed to fetch assignments: {e}")
                logger.error(f"MAIN: Failed to fetch assignments: {e}", exc_info=True)
                st.session_state.assignment_summary_context = f"Error: Could not fetch assignments. {e}"
                st.session_state.structured_assignments_for_calendar = {}
    else:
        logger.warning("MAIN: Attempted to fetch assignments without credentials or gcr_service.")
        st.warning("Could not fetch assignments: Login or service issue.")

# Authentication
if st.session_state.creds is None:
    st.info("Please log in with Google to access Classroom and Calendar features.")
    if st.button("Login with Google"):
        with st.spinner("🔐 Attempting Google Login..."):
            try:
                creds_obj = get_credentials()
                st.session_state.creds = creds_obj
                
                gcr_s, cal_s = get_service(creds_obj)
                st.session_state.gcr_service = gcr_s
                st.session_state.calendar_service_main = cal_s # Used by main if needed
                
                gemini_agent.set_services(gcr_s, cal_s) # Pass to agent module

                st.success("✅ Login Successful! Initializing assignments...")
                fetch_and_store_assignments() # Fetch assignments immediately
                st.rerun()
            except Exception as e:
                st.error(f"Login Failed: {e}")
                logger.error(f"MAIN: Login Failed: {e}", exc_info=True)
                st.session_state.creds = None # Reset creds on failure
else:
    st.success("✅ Logged in with Google.")
    # Ensure services are set if app reloads and creds exist but module services might be lost
    if not st.session_state.gcr_service or not st.session_state.calendar_service_main:
        logger.info("MAIN: Re-initializing services from stored creds.")
        gcr_s, cal_s = get_service(st.session_state.creds)
        st.session_state.gcr_service = gcr_s
        st.session_state.calendar_service_main = cal_s
        gemini_agent.set_services(gcr_s, cal_s) # Re-pass to agent module
        # Fetch assignments if they haven't been fetched yet in this session
        if st.session_state.assignment_summary_context == "No assignments fetched yet. Please log in or refresh.":
            fetch_and_store_assignments()


# UI Elements
if st.session_state.creds:
    if st.button("🔄 Refresh Assignments"):
        fetch_and_store_assignments()

    # Optional: Display the fetched summary for user reference or debugging
    with st.expander("View Current Assignment Summary (for context)", expanded=False):
        if st.session_state.assignment_summary_context:
            st.markdown(st.session_state.assignment_summary_context)
        else:
            st.markdown("No assignment summary available.")

# Display chat history
for message_data in st.session_state.chat_messages:
    with st.chat_message(message_data["type"]):
        st.markdown(message_data["content"])

# Gemini Chat Input
user_query = st.chat_input("Ask about your assignments or schedule...")

if user_query and st.session_state.creds:
    st.session_state.chat_messages.append({"type": "human", "content": user_query})
    with st.chat_message("human"):
        st.markdown(user_query)

    # Prepare agent_lc_history
    agent_lc_history = []
    for msg_data in st.session_state.chat_messages[:-1]: 
        if msg_data["type"] == "human":
            agent_lc_history.append(HumanMessage(content=msg_data["content"]))
        elif msg_data["type"] == "ai":
            agent_lc_history.append(AIMessage(content=msg_data["content"]))

    with st.chat_message("ai"):
        with st.spinner("🤖 Gemini is thinking..."):
            response_data = None # To store the full agent response for debugging
            try:
                # Re-ensure agent services are set, in case of module reload issues
                if gemini_agent.calendar_service_agent is None and st.session_state.calendar_service_main:
                    logger.warning("MAIN: Re-setting agent services before invoke call.")
                    gemini_agent.set_services(st.session_state.gcr_service, st.session_state.calendar_service_main)

                assignment_context_payload = st.session_state.assignment_summary_context if st.session_state.assignment_summary_context else "No assignment data available."
                structured_payload = st.session_state.structured_assignments_for_calendar if st.session_state.structured_assignments_for_calendar else {}
                
                # Get the current date
                current_date_str = datetime.date.today().strftime("%Y-%m-%d")

                if not hasattr(gemini_agent, 'agent_executor'):
                    raise AttributeError("CRITICAL: Agent executor not found in gemini_agent. Ensure it's initialized at module load.")

                # --- This is the invoke call for Option A ---
                response_data = gemini_agent.agent_executor.invoke(
                    {
                        "input": user_query, # User's direct query
                        "chat_history": agent_lc_history,
                        "assignment_context": assignment_context_payload,
                        "structured_assignments_for_calendar": structured_payload,
                        "Current Date": current_date_str # Passed as a separate key
                    }
                )
                # --- End of invoke call specific to Option A ---

                ai_response_content = response_data.get('output', "Sorry, I couldn't get a clear response.")
                st.markdown(ai_response_content)
                st.session_state.chat_messages.append({"type": "ai", "content": ai_response_content})

            except Exception as e:
                error_message = f"Agent Error: {e}"
                st.error(error_message) # Show the primary error message in Streamlit
                logger.error(f"MAIN: Agent Error: {e}", exc_info=True) # Log full traceback to console
                st.session_state.chat_messages.append({"type": "ai", "content": error_message})
                
                if response_data and 'intermediate_steps' in response_data:
                    st.error("Intermediate Agent Steps (for debugging):")
                    try:
                        st.json(response_data['intermediate_steps'])
                        logger.info(f"MAIN DEBUG: Intermediate steps on error: {json.dumps(response_data['intermediate_steps'], indent=2)}")
                    except Exception as json_e: # Fallback if intermediate_steps are not directly JSON serializable
                        st.text(str(response_data['intermediate_steps']))
                        logger.info(f"MAIN DEBUG: Intermediate steps (raw on error): {response_data['intermediate_steps']}")
                else:
                    st.warning("No intermediate steps data available in the response to display on error (or error occurred before response_data was set).")

elif user_query and not st.session_state.creds:
    st.warning("Please log in with Google first to use the assistant.")