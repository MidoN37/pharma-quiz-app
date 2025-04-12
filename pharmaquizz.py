# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import random
from pathlib import Path

# --- Page Config ---
st.set_page_config(layout="wide", page_title="Pharm Quiz")

# --- Project Setup & File Path ---
APP_DIR = Path(__file__).parent
PROJECT_ROOT = APP_DIR
# Path to the generated QUIZ CSV file relative to the script
# Assumes QUIZ folder is at the same level as the script
QUIZ_CSV_PATH = PROJECT_ROOT / "QUIZ" / "quiz_data_v2.csv"

# --- Load Quiz Data from CSV ---
@st.cache_data(show_spinner="Loading quiz questions...")
def load_quiz_from_csv(path):
    """Loads quiz questions directly from the pre-generated CSV file."""
    print(f"Attempting to load quiz data from: {path}")
    try:
        if not path.exists():
            st.error(f"Quiz data CSV not found at: {path}. Please run the generation script.")
            return None
        # Read CSV, keep empty values as empty strings rather than NaN by default
        # Ensure correct encoding is used if CSV was saved with utf-8-sig
        try:
            # Try reading with utf-8-sig first (common for Excel exports)
            df = pd.read_csv(path, keep_default_na=False, encoding='utf-8-sig')
        except UnicodeDecodeError:
            # Fallback to standard utf-8 if sig fails
            print("UTF-8-SIG failed, trying standard UTF-8...")
            df = pd.read_csv(path, keep_default_na=False, encoding='utf-8')

        print(f"Loaded {len(df)} questions from CSV.")
        # Convert DataFrame rows to list of dictionaries
        # Ensure Options are collected correctly
        questions = []
        option_cols = [col for col in df.columns if col.startswith('Option_')]
        for _, row in df.iterrows():
            options = [row[col] for col in option_cols if pd.notna(row[col]) and row[col]] # Get non-empty options
            entry = {
                'category': row['Category'],
                'sheet': row['Sheet'],
                'med_name': row['MedicationName'],
                'question': row['Question'],
                'options': options, # List of options from Option_ columns
                'correct_answer': row['CorrectAnswer']
            }
            questions.append(entry)
        return questions
    except Exception as e:
        st.error(f"Failed to load or process Quiz CSV '{path.name}': {e}")
        return None

# Load all questions once
ALL_QUIZ_QUESTIONS = load_quiz_from_csv(QUIZ_CSV_PATH)

# --- Get unique Categories and Sheets from loaded data ---
CATEGORIES = []
SHEETS_BY_CATEGORY = {}
if ALL_QUIZ_QUESTIONS:
    CATEGORIES = sorted(list(set(q['category'] for q in ALL_QUIZ_QUESTIONS)))
    for cat in CATEGORIES:
        SHEETS_BY_CATEGORY[cat] = sorted(list(set(q['sheet'] for q in ALL_QUIZ_QUESTIONS if q['category'] == cat)))


# --- Initialize Session State ---
if 'selected_category' not in st.session_state: st.session_state.selected_category = None
if 'selected_sheet' not in st.session_state: st.session_state.selected_sheet = None
if 'quiz_questions' not in st.session_state: st.session_state.quiz_questions = [] # Holds SHUFFLED questions for current quiz
if 'current_q_index' not in st.session_state: st.session_state.current_q_index = 0
if 'score' not in st.session_state: st.session_state.score = 0
if 'user_answers' not in st.session_state: st.session_state.user_answers = {}
if 'answer_submitted' not in st.session_state: st.session_state.answer_submitted = False
if 'current_options' not in st.session_state: st.session_state.current_options = []
if 'quiz_active' not in st.session_state: st.session_state.quiz_active = False
if 'quiz_complete' not in st.session_state: st.session_state.quiz_complete = False


# --- Helper Functions for State Updates ---
def submit_answer():
    st.session_state.answer_submitted = True
    selected_option = st.session_state.get('quiz_option')
    q_index = st.session_state.current_q_index
    if selected_option is not None and q_index < len(st.session_state.quiz_questions):
         st.session_state.user_answers[q_index] = selected_option
         correct = (selected_option == st.session_state.quiz_questions[q_index]['correct_answer'])
         if correct:
             # Basic scoring, assumes first submission is final
             # Check if already scored this index to prevent double score if review is added
             if st.session_state.user_answers.get(q_index) == st.session_state.quiz_questions[q_index]['correct_answer']:
                 # Avoid incrementing if this correct answer was already recorded? Needs tracking.
                 # Simplest: Only score on the transition via submit_answer
                 # Check if already correct in user_answers *before* this update?
                 # Let's stick to simple increment for now.
                 st.session_state.score += 1


def next_question():
    q_index = st.session_state.current_q_index
    num_questions = len(st.session_state.quiz_questions)
    if q_index < num_questions - 1:
        st.session_state.current_q_index += 1
        st.session_state.answer_submitted = False
        st.session_state.current_options = [] # Reshuffle options
        st.session_state.quiz_option = None # Reset radio button selection state
    else:
        # Reached end of quiz
        st.session_state.quiz_complete = True
        st.session_state.quiz_active = False # Turn off quiz display

def reset_quiz_state():
     """Resets session state variables related to quiz progress."""
     st.session_state.quiz_questions = []
     st.session_state.current_q_index = 0
     st.session_state.score = 0
     st.session_state.user_answers = {}
     st.session_state.answer_submitted = False
     st.session_state.current_options = []
     st.session_state.quiz_active = False
     st.session_state.quiz_complete = False
     if 'quiz_option' in st.session_state: del st.session_state['quiz_option']

def start_quiz(category, sheet):
    """Filters pre-loaded questions, sets state to start quiz."""
    print(f"Starting quiz for: {category} - {sheet}")
    reset_quiz_state() # Reset score/progress
    st.session_state.selected_category = category
    st.session_state.selected_sheet = sheet

    # Filter ALL_QUIZ_QUESTIONS for the selected category and sheet
    filtered_questions = [
        q for q in ALL_QUIZ_QUESTIONS
        if q['category'] == category and q['sheet'] == sheet
    ]

    if not filtered_questions:
        st.error(f"No questions found for {category} - {sheet} in the loaded data.")
        return

    random.shuffle(filtered_questions) # Shuffle questions for this quiz session
    st.session_state.quiz_questions = filtered_questions
    st.session_state.quiz_active = True # Activate quiz display
    st.session_state.quiz_complete = False # Ensure complete flag is off
    st.rerun() # Rerun to show the quiz screen


# --- Streamlit App UI ---
st.title("💊 Pharma Quiz 💊")

# --- Quiz Selection Area ---
# This section is shown if a quiz is NOT active AND NOT complete
if not st.session_state.quiz_active and not st.session_state.quiz_complete:
    st.header("Select Quiz")

    if not ALL_QUIZ_QUESTIONS:
        st.error("Quiz data could not be loaded. Please check the CSV file and path.")
    else:
        # Category Selectbox
        selected_category = st.selectbox(
            "Choose a Category:",
            options=[""] + CATEGORIES, # Use categories derived from loaded data
            format_func=lambda x: "Select Category..." if x == "" else x,
            key='cat_select_dd'
        )

        selected_sheet = None
        if selected_category:
            available_sheets_for_cat = SHEETS_BY_CATEGORY.get(selected_category, [])
            if len(available_sheets_for_cat) == 1:
                selected_sheet = available_sheets_for_cat[0]
                st.write(f"Category **{selected_category}** has only one sheet: **{selected_sheet}**")
            elif len(available_sheets_for_cat) > 1:
                selected_sheet = st.selectbox(
                    "Choose a Sheet:",
                    options=[""] + available_sheets_for_cat,
                    format_func=lambda x: "Select Sheet..." if x == "" else x,
                    key='sheet_select_dd'
                )
            else:
                st.warning(f"No valid sheets found for category '{selected_category}'.")

        # Start Quiz Button
        start_disabled = not (selected_category and selected_sheet)
        if st.button("Start Quiz", disabled=start_disabled, key="start_quiz_btn"):
            if selected_category and selected_sheet:
                start_quiz(selected_category, selected_sheet)
            else:
                st.warning("Please select both a category and a sheet.")

# --- Quiz Display Area ---
elif st.session_state.quiz_active:
    st.header(f"Quiz: {st.session_state.selected_category} - {st.session_state.selected_sheet}")
    st.button("⬅️ Stop Quiz / Change Selection", key="stop_quiz", on_click=reset_quiz_state) # Reset all
    st.markdown("---")

    questions_to_run = st.session_state.quiz_questions
    num_questions = len(questions_to_run)
    q_index = st.session_state.current_q_index

    if not questions_to_run: # Should not happen if quiz_active is True, but safety check
        st.error("Error: Quiz questions not loaded.")
    elif q_index >= num_questions:
         # Should be caught by next_question setting quiz_complete, but handle just in case
         st.session_state.quiz_complete = True
         st.session_state.quiz_active = False
         st.rerun()
    else:
        # Display current question UI
        current_q = questions_to_run[q_index];
        st.subheader(f"Question {q_index + 1}/{num_questions}");
        st.markdown(f"**{current_q['question']}**");

        # Shuffle options only if not already set for this question index
        if not st.session_state.current_options:
             options = current_q['options'][:] # Get a copy
             random.shuffle(options)
             st.session_state.current_options = options
        options_to_display = st.session_state.current_options
        disable_radio = st.session_state.answer_submitted;

        current_selection = st.session_state.get('quiz_option')
        current_index = None
        if current_selection is not None and current_selection in options_to_display:
            try: current_index = options_to_display.index(current_selection)
            except ValueError: current_index = None

        user_choice = st.radio("Select:", options=options_to_display, index=current_index, key='quiz_option', disabled=disable_radio, label_visibility="collapsed");

        # Submit/Next Buttons
        col1, col2 = st.columns([0.2, 0.8]);
        with col1:
            if not st.session_state.answer_submitted: submit_button = st.button("Submit", key=f"submit_{q_index}", on_click=submit_answer, disabled=(user_choice is None));
        if st.session_state.answer_submitted:
             with col2: button_label = "Next >>" if q_index < num_questions - 1 else "Finish"; next_button = st.button(button_label, key=f"next_{q_index}", on_click=next_question);

        # Feedback
        if st.session_state.answer_submitted:
            st.markdown("---"); user_ans = st.session_state.user_answers.get(q_index, None); correct_ans = current_q['correct_answer'];
            if user_ans is not None:
                if user_ans == correct_ans: st.success(f"**Correct!** {correct_ans}");
                else: st.error(f"**Incorrect.** You: {user_ans}"); st.info(f"**Correct:** {correct_ans}");

    # Sidebar score display during quiz
    st.sidebar.header("Score")
    current_score = max(0, st.session_state.get('score', 0))
    total_qs_in_state = len(st.session_state.get('quiz_questions', []))
    st.sidebar.metric("Current Score", f"{current_score} / {total_qs_in_state if total_qs_in_state > 0 else 'N/A'}");


# --- Results Display Area ---
elif st.session_state.quiz_complete:
    st.header("🎉 Quiz Complete! 🎉");
    category = st.session_state.selected_category
    sheet = st.session_state.selected_sheet
    st.markdown(f"Category: **{category}** | Sheet: **{sheet}**") # Show context
    num_questions = len(st.session_state.get('quiz_questions', []));
    final_score = min(st.session_state.get('score', 0), num_questions); # Cap score at max questions
    st.subheader(f"Your Final Score: {final_score} / {num_questions}");
    if num_questions > 0: percentage = round((final_score / num_questions) * 100); st.metric(label="Percentage", value=f"{percentage}%");
    else: st.write("No questions were in this quiz.");

    # Buttons layout
    col1, col2 = st.columns(2);
    with col1:
        st.button("Take Another Quiz", key="restart", on_click=reset_quiz_state) # Reset state and stay on same screen (will show selection)

    # Review Answers Expander
    with st.expander("Review Your Answers"):
         questions_answered = st.session_state.get('quiz_questions', []); answers_given = st.session_state.get('user_answers', {});
         if not questions_answered: st.write("No answers recorded.")
         else:
             for i, q in enumerate(questions_answered):
                 user_ans = answers_given.get(i, "Not Answered"); correct_ans = q['correct_answer']; is_correct = (user_ans == correct_ans); feedback_icon = "✅" if is_correct else "❌";
                 st.markdown(f"**Q{i+1}:** `{q['med_name']}` - {q['question']}"); st.write(f"   Your answer: {user_ans} {feedback_icon}");
                 if not is_correct and user_ans != "Not Answered": st.write(f"   Correct answer: {correct_ans}");
                 st.divider();