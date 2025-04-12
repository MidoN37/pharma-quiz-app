import streamlit as st
import pandas as pd
import random
from pathlib import Path

# --- Page Config ---
st.set_page_config(layout="wide", page_title="Pharm Quiz")

# --- Project Setup & File Path ---
APP_DIR = Path(__file__).parent
PROJECT_ROOT = APP_DIR
QUIZ_CSV_PATH = PROJECT_ROOT / "QUIZ" / "quiz_data_v2.csv"

# --- Load CSV file ---
@st.cache_data(show_spinner="Loading quiz data...")
def load_data(path):
    """Loads quiz data from CSV."""
    print(f"Attempting to load quiz data from: {path}")
    try:
        if not path.exists():
            st.error(f"Quiz data CSV not found: {path}")
            return None
        try: df = pd.read_csv(path, keep_default_na=False, encoding='utf-8-sig')
        except UnicodeDecodeError: df = pd.read_csv(path, keep_default_na=False, encoding='utf-8')
        print(f"Loaded {len(df)} rows from CSV.")
        # Basic validation of required columns
        required = ['Category', 'Sheet', 'MedicationName', 'Question', 'CorrectAnswer', 'Option_1']
        if not all(col in df.columns for col in required):
             st.error(f"CSV missing required columns. Need at least: {required}")
             return None
        return df
    except Exception as e:
        st.error(f"Failed to load/process Quiz CSV '{path.name}': {e}")
        return None

df_all = load_data(QUIZ_CSV_PATH)

# --- App Initialization ---
if df_all is None:
    st.error("Failed to load quiz data. Cannot start the app.")
    st.stop() # Stop execution if data loading failed

# Extract unique categories only if data loaded
categories = sorted(df_all['Category'].unique()) if df_all is not None else []

# --- Session state ---
if 'selected_category' not in st.session_state:
    # Try setting a default category if available, otherwise None
    st.session_state.selected_category = categories[0] if categories else None
if 'selected_sheet' not in st.session_state:
     # Need to set sheet based on initial category later
     st.session_state.selected_sheet = None
if 'question_index' not in st.session_state:
    st.session_state.question_index = 0
if 'answers' not in st.session_state:
    st.session_state.answers = {}  # {q_index: selected_option_text}
if 'show_result' not in st.session_state:
    st.session_state.show_result = False
if 'current_quiz_df' not in st.session_state: # Store the filtered df for the current quiz
    st.session_state.current_quiz_df = pd.DataFrame()
if 'current_quiz_options' not in st.session_state: # Store shuffled options {q_index: [options]}
    st.session_state.current_quiz_options = {}

# --- Helper Functions ---
def reset_quiz_progress():
    """Resets progress for a new quiz attempt."""
    st.session_state.question_index = 0
    st.session_state.answers = {}
    st.session_state.show_result = False
    st.session_state.current_quiz_options = {} # Clear shuffled options

def filter_and_start_quiz():
    """Filters data based on selections, shuffles, resets progress."""
    cat = st.session_state.selected_category
    sheet = st.session_state.selected_sheet
    if not cat or not sheet:
        st.warning("Please select category and sheet.")
        st.session_state.current_quiz_df = pd.DataFrame() # Clear quiz df
        reset_quiz_progress()
        return

    print(f"Filtering quiz for {cat} - {sheet}")
    # Filter the main DataFrame
    filtered_df = df_all[(df_all['Category'] == cat) & (df_all['Sheet'] == sheet)].copy()
    # Shuffle the filtered DataFrame rows (shuffles question order)
    st.session_state.current_quiz_df = filtered_df.sample(frac=1).reset_index(drop=True)
    reset_quiz_progress() # Reset progress for the new set
    print(f"Quiz started with {len(st.session_state.current_quiz_df)} questions.")

# --- Sidebar Selection ---
st.sidebar.title("Quiz Settings")
# Category selection - default to first category if none selected
selected_cat = st.sidebar.selectbox(
    "Select Category",
    options=categories,
    index=categories.index(st.session_state.selected_category) if st.session_state.selected_category in categories else 0,
    key='sb_cat'
)

# Update category and reset sheet if category changed
if selected_cat != st.session_state.selected_category:
    st.session_state.selected_category = selected_cat
    st.session_state.selected_sheet = None # Reset sheet when category changes
    st.session_state.current_quiz_df = pd.DataFrame() # Clear current quiz
    reset_quiz_progress()
    st.rerun() # Rerun to update sheet options

# Sheet selection (only if category selected)
selected_sheet = None
available_sheets = []
if st.session_state.selected_category:
    available_sheets = sorted(df_all[df_all['Category'] == st.session_state.selected_category]['Sheet'].unique())
    if len(available_sheets) == 1:
         selected_sheet = available_sheets[0]
         st.sidebar.write(f"Sheet: **{selected_sheet}** (Auto-selected)")
         # Auto-set if not already set or different
         if st.session_state.selected_sheet != selected_sheet:
             st.session_state.selected_sheet = selected_sheet
             # If we want quiz to load automatically on single sheet selection, trigger here
             # filter_and_start_quiz() # Optional: Auto-start
             # st.rerun()
    elif len(available_sheets) > 1:
         # Find index of current sheet selection for default value
         current_sheet_index = 0 # Default to placeholder
         if st.session_state.selected_sheet and st.session_state.selected_sheet in available_sheets:
              current_sheet_index = available_sheets.index(st.session_state.selected_sheet) + 1 # +1 for placeholder

         selected_sheet_choice = st.sidebar.selectbox(
             "Select Sheet:",
             options=[""] + available_sheets,
             index=current_sheet_index,
             format_func=lambda x: "Select Sheet..." if x == "" else x,
             key='sb_sheet'
         )
         if selected_sheet_choice: # If user selected something other than placeholder
             selected_sheet = selected_sheet_choice
             # Update state only if changed
             if st.session_state.selected_sheet != selected_sheet:
                  st.session_state.selected_sheet = selected_sheet
                  st.session_state.current_quiz_df = pd.DataFrame() # Clear old quiz
                  reset_quiz_progress()
                  st.rerun() # Rerun if sheet changed to potentially enable Start button

# --- Start/Restart Button ---
start_disabled = not (st.session_state.selected_category and st.session_state.selected_sheet)
if st.sidebar.button("Load / Restart Quiz", disabled=start_disabled):
    filter_and_start_quiz()
    # Rerun is handled by state change within start_quiz if using buttons there,
    # or implicitly here by button click triggering rerun.

# --- Main Quiz Area ---
st.markdown("---")

# Check if a quiz is loaded and ready
if not st.session_state.current_quiz_df.empty and not st.session_state.show_result:
    category_df = st.session_state.current_quiz_df
    total_questions = len(category_df)
    q_index = st.session_state.question_index

    # Ensure index is valid
    if q_index >= total_questions:
        st.warning("Quiz index out of bounds. Resetting.")
        reset_quiz_progress()
        st.rerun()

    question = category_df.iloc[q_index]
    st.subheader(f"Question {q_index + 1} of {total_questions}")
    st.write(question['Question'])

    # Get/Shuffle Options for the current question index
    options_key = q_index # Use index as key
    if options_key not in st.session_state.current_quiz_options:
        option_cols = [f'Option_{i}' for i in range(1, 6) if f'Option_{i}' in question and pd.notna(question[f'Option_{i}']) and question[f'Option_{i}']]
        options = [question[col] for col in option_cols]
        random.shuffle(options)
        st.session_state.current_quiz_options[options_key] = options
    options_to_display = st.session_state.current_quiz_options[options_key]

    # --- CORRECTED Correct Answer Logic ---
    correct_answer_text = question['CorrectAnswer']

    # --- Show Radio Buttons ---
    # Find index of previous answer if exists
    previous_answer = st.session_state.answers.get(q_index, None)
    current_index = None
    if previous_answer is not None and previous_answer in options_to_display:
         try: current_index = options_to_display.index(previous_answer)
         except ValueError: current_index = None

    selected = st.radio("Select your answer:", options_to_display,
                        index=current_index, # Pre-select previous answer if exists
                        key=f"q{q_index}") # Unique key for radio

    # Save answer immediately on interaction (radio button change triggers rerun)
    if selected != previous_answer: # Only update if it changed
         st.session_state.answers[q_index] = selected
         # Force rerun to potentially show feedback if desired immediately?
         # Or wait for explicit submit/nav? Let's wait.
         # st.rerun()

    # --- Immediate Feedback (Optional) ---
    show_feedback = True # Set to False if you want feedback only on Finish
    if show_feedback and selected: # Show if an answer is selected
        if selected == correct_answer_text:
            st.success("Correct!")
        else:
            st.error(f"Incorrect! Correct answer: {correct_answer_text}")

    # --- Navigation Buttons ---
    st.markdown("---")
    st.write("**Navigate Questions:**")
    cols_per_row = 10
    nav_cols = st.columns(min(total_questions, cols_per_row))
    for i in range(total_questions):
        col_idx_nav = i % min(total_questions, cols_per_row)
        col = nav_cols[col_idx_nav]
        q_num = i + 1
        button_type = "primary" if i == q_index else "secondary"
        # Style based on answer status
        label_suffix = ""
        if i in st.session_state.answers:
             is_correct = (st.session_state.answers[i] == category_df.iloc[i]['CorrectAnswer'])
             label_suffix = " ✅" if is_correct else " ❌"

        with col:
            if st.button(f"{q_num}{label_suffix}", key=f"nav{i}", type=button_type, use_container_width=True):
                # Update index directly, rerun will handle display
                st.session_state.question_index = i
                st.rerun() # Rerun needed after navigation button click

    # --- Finish quiz button ---
    st.markdown("---")
    if st.button("Finish Quiz and See Results"):
        st.session_state.show_result = True
        st.rerun() # Rerun to show results

elif st.session_state.show_result:
    # --- Results Display ---
    category_df = st.session_state.current_quiz_df # Use df from state
    total_questions = len(category_df)
    correct = 0
    incorrect = 0
    unanswered = 0

    if total_questions > 0:
         for i in range(total_questions):
             q = category_df.iloc[i]
             selected = st.session_state.answers.get(i, None)
             # Compare selected text with correct answer text
             if selected is None:
                 unanswered += 1
             elif selected == q['CorrectAnswer']: # Compare directly with CorrectAnswer column
                 correct += 1
             else:
                 incorrect += 1

         st.markdown("## Quiz Results")
         st.markdown(f"Category: **{st.session_state.selected_category}** | Sheet: **{st.session_state.selected_sheet}**")
         st.write(f"✅ Correct answers: {correct}")
         st.write(f"❌ Incorrect answers: {incorrect}")
         st.write(f"❓ Not answered: {unanswered}")
         score = correct # Simple score = number correct
         if total_questions > 0:
             percentage = round((score / total_questions) * 100)
             st.metric(label="Final Score", value=f"{score}/{total_questions}", delta=f"{percentage}%")

         # Button to start over
         if st.button("Start New Quiz"):
             reset_quiz_progress() # Keep category/sheet selection
             st.session_state.current_quiz_df = pd.DataFrame() # Clear quiz df
             st.rerun()

         # Review Answers
         with st.expander("Review Your Answers"):
            for i in range(total_questions):
                q = category_df.iloc[i]
                selected = st.session_state.answers.get(i, "Not Answered")
                correct_ans = q['CorrectAnswer']
                is_correct = (selected == correct_ans)
                feedback_icon = "✅" if is_correct else ("❌" if selected != "Not Answered" else "❓")
                st.markdown(f"**Q{i+1}:** `{q['MedicationName']}` - {q['Question']}")
                st.write(f"   Your answer: {selected} {feedback_icon}")
                if not is_correct and selected != "Not Answered":
                    st.write(f"   Correct answer: {correct_ans}")
                st.divider()
    else:
        st.warning("No quiz was loaded to show results.")
        if st.button("Select New Quiz"):
            reset_quiz_progress()
            st.rerun()


# Show selection prompt if nothing else is active
elif not st.session_state.selected_category or not st.session_state.selected_sheet:
     st.info("Please select a category and sheet, then click 'Load / Restart Quiz'.")