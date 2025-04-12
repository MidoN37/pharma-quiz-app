# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import os
import numpy as np
import random
from pathlib import Path
import unicodedata
import re

# Need unidecode: pip install unidecode
try:
    from unidecode import unidecode
except ImportError:
    def unidecode(x):
        if 'unidecode_warning_shown' not in st.session_state:
            st.warning("`unidecode` library missing (pip install unidecode).")
            st.session_state.unidecode_warning_shown = True
        return str(x)

# --- Page Config ---
st.set_page_config(layout="wide", page_title="Pharm Quiz")

# --- Project Setup ---
APP_DIR = Path(__file__).parent
PROJECT_ROOT = APP_DIR
QUIZ_CSV_PATH = PROJECT_ROOT / "QUIZ" / "quiz_data_v2.csv" # Path to generated CSV

# --- Load Quiz Data from CSV ---
@st.cache_data(show_spinner="Loading quiz questions...")
def load_quiz_from_csv(path):
    """Loads quiz questions directly from the pre-generated CSV file."""
    print(f"Attempting to load quiz data from: {path}")
    try:
        if not path.exists():
            st.error(f"Quiz data CSV not found at: {path}. Please run the generation script.")
            return None
        try: df = pd.read_csv(path, keep_default_na=False, encoding='utf-8-sig')
        except UnicodeDecodeError: print("UTF-8-SIG failed, trying UTF-8..."); df = pd.read_csv(path, keep_default_na=False, encoding='utf-8')
        print(f"Loaded {len(df)} questions from CSV.")
        questions = []; option_cols = [col for col in df.columns if col.startswith('Option_')];
        for _, row in df.iterrows():
            options = [row[col] for col in option_cols if pd.notna(row[col]) and row[col]]
            entry = {'category': row['Category'], 'sheet': row['Sheet'], 'med_name': row['MedicationName'], 'question': row['Question'], 'options': options, 'correct_answer': row['CorrectAnswer']}
            if all(k in entry and pd.notna(entry[k]) for k in ['category', 'sheet', 'med_name', 'question', 'correct_answer']) and entry['options']: questions.append(entry)
            else: print(f"Skipping invalid row from CSV: {row.to_dict()}")
        print(f"Filtered to {len(questions)} valid questions.")
        return questions
    except Exception as e: st.error(f"Failed to load/process Quiz CSV '{path.name}': {e}"); return None

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
# Needs to be done early, BEFORE functions that might access it are called
if 'selected_category' not in st.session_state: st.session_state.selected_category = None
if 'selected_sheet' not in st.session_state: st.session_state.selected_sheet = None
if 'quiz_questions' not in st.session_state: st.session_state.quiz_questions = []
if 'current_q_index' not in st.session_state: st.session_state.current_q_index = 0
if 'score' not in st.session_state: st.session_state.score = 0
if 'user_answers' not in st.session_state: st.session_state.user_answers = {}
if 'submission_status' not in st.session_state: st.session_state.submission_status = {}
if 'current_options' not in st.session_state: st.session_state.current_options = []
if 'quiz_active' not in st.session_state: st.session_state.quiz_active = False
if 'quiz_complete' not in st.session_state: st.session_state.quiz_complete = False
if 'correctly_answered_indices' not in st.session_state: st.session_state.correctly_answered_indices = set()


# --- Helper Functions for State Updates ---
# DEFINE FUNCTIONS *BEFORE* THEY ARE CALLED IN THE MAIN LAYOUT LOGIC
def reset_quiz_state():
     """Resets all quiz-related progress variables in session state."""
     st.session_state.quiz_questions = []
     st.session_state.current_q_index = 0
     st.session_state.score = 0
     st.session_state.user_answers = {}
     st.session_state.submission_status = {}
     st.session_state.current_options = []
     st.session_state.quiz_active = False
     st.session_state.quiz_complete = False
     st.session_state.correctly_answered_indices = set()
     # Clear dynamic radio key if it exists
     q_index_key = st.session_state.get('current_q_index', 0) # Get current index if possible
     radio_key = f'quiz_option_{q_index_key}'
     if radio_key in st.session_state: del st.session_state[radio_key]
     # Also reset the generic key just in case
     if 'quiz_option' in st.session_state: del st.session_state['quiz_option']


def submit_answer():
    """Callback for Submit button. Marks question as submitted and scores if correct."""
    q_index = st.session_state.current_q_index
    # Use the dynamic key to read the radio button's current value
    selected_option = st.session_state.get(f'quiz_option_{q_index}', None) # Read specific key

    if selected_option is not None and q_index < len(st.session_state.quiz_questions):
         st.session_state.user_answers[q_index] = selected_option
         st.session_state.submission_status[q_index] = True

         correct = (selected_option == st.session_state.quiz_questions[q_index]['correct_answer'])
         if correct and q_index not in st.session_state.correctly_answered_indices:
             st.session_state.score += 1
             st.session_state.correctly_answered_indices.add(q_index)


def go_to_question(target_index):
    """Callback for number buttons. Jumps to a specific question."""
    num_questions = len(st.session_state.quiz_questions)
    if 0 <= target_index < num_questions:
        st.session_state.current_q_index = target_index
        # Don't reset submission status on jump
        # Don't reshuffle options on jump
    else:
        print(f"Warning: Invalid jump target index: {target_index}")

def next_question():
    """Moves to the next question index or finishes."""
    q_index = st.session_state.current_q_index
    num_questions = len(st.session_state.quiz_questions)
    if q_index < num_questions - 1:
        go_to_question(q_index + 1) # Use jump function to move index
    else:
        finish_quiz() # Go to results if already on last question

def finish_quiz():
     """Ends the quiz and goes to the results screen."""
     st.session_state.quiz_complete = True
     st.session_state.quiz_active = False
     st.session_state.current_q_index = len(st.session_state.quiz_questions) # Set past end
     st.session_state.current_options = []
     # Clean up last radio key if exists
     q_index_key = st.session_state.get('current_q_index', 0)
     radio_key = f'quiz_option_{q_index_key}'
     if radio_key in st.session_state: del st.session_state[radio_key]

def go_to_sheet_select(category):
    """Sets state for sheet selection screen."""
    st.session_state.selected_category = category
    st.session_state.screen = 'sheet_select' # Corrected screen state name
    reset_quiz_state()

def start_quiz(category, sheet):
    """Filters pre-loaded questions, sets state to start quiz."""
    print(f"Starting quiz for: {category} - {sheet}")
    reset_quiz_state() # Reset score/progress first
    st.session_state.selected_category = category
    st.session_state.selected_sheet = sheet

    # Filter ALL_QUIZ_QUESTIONS for the selected category and sheet
    filtered_questions = [
        q for q in ALL_QUIZ_QUESTIONS
        if q.get('category') == category and q.get('sheet') == sheet # Use .get for safety
    ]

    if not filtered_questions:
        st.error(f"No questions found for {category} - {sheet} in the loaded data.")
        st.session_state.quiz_active = False # Ensure quiz doesn't start
        return # Stop if no questions

    random.shuffle(filtered_questions) # Shuffle questions for this quiz session
    st.session_state.quiz_questions = filtered_questions
    st.session_state.quiz_active = True # Activate quiz display
    st.session_state.quiz_complete = False # Ensure complete flag is off
    # No rerun needed here IF start_quiz is called from a button's on_click
    # If called programmatically (like single sheet case), rerun IS needed after this.


def go_to_category_select():
    """Sets state for category selection screen."""
    st.session_state.screen = 'category_select'
    st.session_state.selected_category = None
    st.session_state.selected_sheet = None
    reset_quiz_state()


# --- Streamlit App UI ---
st.title("💊 Pharma Quiz 💊")

# --- Determine which screen to show based on state ---
current_screen = st.session_state.get('screen', 'category_select')

# == Category Selection Screen ==
if current_screen == 'category_select':
    st.header("Select Quiz Category")
    st.write("Choose a pharmaceutical category.")
    cols = st.columns(4)
    col_idx = 0
    if not CATEGORIES: st.error("No categories found in loaded data.")
    else:
        for category_name in CATEGORIES:
             # Check if this category has available sheets
             if category_name in SHEETS_BY_CATEGORY and SHEETS_BY_CATEGORY[category_name]:
                 button_col = cols[col_idx % len(cols)];
                 with button_col: st.button(category_name, key=f"cat_{category_name}", on_click=go_to_sheet_select, args=(category_name,));
                 col_idx += 1;
        if col_idx == 0: st.warning("No categories with quiz data available.")

# == Sheet Selection Screen ==
elif current_screen == 'sheet_select':
    category = st.session_state.selected_category
    st.header(f"Category: {category}")
    st.button("⬅️ Back to Categories", key="back_cat", on_click=go_to_category_select)
    st.markdown("---")

    available_sheets_for_cat = SHEETS_BY_CATEGORY.get(category, [])

    if not available_sheets_for_cat:
        st.warning(f"No valid sheets found for category '{category}'.")
        # Optionally provide button to go back
        st.button("Go Back", on_click=go_to_category_select)
    elif len(available_sheets_for_cat) == 1:
        selected_sheet = available_sheets_for_cat[0]
        st.info(f"Starting quiz for the only available sheet: {selected_sheet}...")
        # Set state and trigger rerun - quiz generation happens on next screen load
        st.session_state.selected_sheet = selected_sheet;
        st.session_state.screen = 'quiz';
        # Call reset here explicitly before rerun maybe?
        reset_quiz_state() # Ensure clean slate before quiz screen
        st.rerun();
    else:
        st.subheader(f"Select Sheet:")
        cols_sheet = st.columns(4); col_idx_sheet = 0;
        for sheet_name in available_sheets_for_cat:
             button_col_sheet = cols_sheet[col_idx_sheet % len(cols_sheet)];
             with button_col_sheet:
                 # Use partial or lambda if args needed directly for on_click
                 st.button(sheet_name, key=f"sheet_{category}_{sheet_name}", on_click=start_quiz, args=(category, sheet_name,))
             col_idx_sheet += 1

# == Quiz Screen ==
elif current_screen == 'quiz':
    # Check if questions are loaded, if not, try loading them
    if not st.session_state.get('quiz_questions'):
        print(f"DEBUG: Quiz questions empty on entering Quiz Screen for {st.session_state.selected_category}-{st.session_state.selected_sheet}, attempting load...")
        start_quiz(st.session_state.selected_category, st.session_state.selected_sheet) # Try loading again

    # Now display quiz UI using questions from session state
    questions_to_run = st.session_state.get('quiz_questions', [])
    st.header(f"Quiz: {st.session_state.selected_category} - {st.session_state.selected_sheet}")
    col_top1, col_top2, col_top3 = st.columns([1.5, 1.5, 5]);
    with col_top1: st.button("⬅️ Stop & Change Quiz", key="stop_quiz", on_click=reset_and_select_category)
    with col_top2: st.button("Finish Early", key="finish_quiz", on_click=finish_quiz)
    st.markdown("---")
    print(f"DEBUG: Rendering Quiz Screen. Questions in state: {len(questions_to_run)}")

    if not questions_to_run: st.warning("No questions available for this section.")
    else:
        num_questions = len(questions_to_run); q_index = st.session_state.current_q_index;
        if q_index >= num_questions: # Quiz finished condition
             st.session_state.quiz_complete = True; st.session_state.quiz_active = False; st.rerun();
        else:
            current_q = questions_to_run[q_index]; st.subheader(f"Question {q_index + 1}/{num_questions}"); st.markdown(f"**{current_q['question']}**");
            options_key = f"options_{q_index}"; # Use dynamic key for options per question
            if options_key not in st.session_state: options = current_q['options'][:]; random.shuffle(options); st.session_state[options_key] = options;
            options_to_display = st.session_state[options_key]; question_submitted = st.session_state.submission_status.get(q_index, False); disable_radio = question_submitted;
            current_selection = st.session_state.user_answers.get(q_index, None); current_index = None;
            if current_selection is not None and current_selection in options_to_display:
                 # Correctly indented try/except block
                 try:
                     current_index = options_to_display.index(current_selection)
                 except ValueError:
                     current_index = None # Handle case where selection isn't in options (shouldn't happen often)

            # Use unique key for radio button tied to question index
            radio_key = f'quiz_option_{q_index}'
            user_choice = st.radio("Select:", options=options_to_display, index=current_index, key=radio_key, disabled=disable_radio, label_visibility="collapsed");

            col_btn1, col_btn2 = st.columns([0.2, 0.8]);
            with col_btn1:
                if not question_submitted: submit_button = st.button("Submit", key=f"submit_{q_index}", on_click=submit_answer, disabled=(st.session_state.get(radio_key) is None));
            if question_submitted:
                 with col_btn2: button_label = "Next >>" if q_index < num_questions - 1 else "See Results"; next_button = st.button(button_label, key=f"next_{q_index}", on_click=next_question);
            if question_submitted: # Feedback
                st.markdown("---"); user_ans = st.session_state.user_answers.get(q_index, None); correct_ans = current_q['correct_answer'];
                if user_ans is not None:
                    if user_ans == correct_ans: st.success(f"**Correct!** {correct_ans}");
                    else: st.error(f"**Incorrect.** You: {user_ans}"); st.info(f"**Correct:** {correct_ans}");

            # --- Question Navigation Buttons ---
            st.markdown("---"); st.write("**Navigate Questions:**");
            cols_per_row = 10; num_rows = (num_questions + cols_per_row - 1) // cols_per_row; nav_cols = st.columns(cols_per_row);
            for i in range(num_questions):
                 col = nav_cols[i % cols_per_row]; q_num = i + 1; button_type = "primary" if i == q_index else "secondary";
                 is_submitted = st.session_state.submission_status.get(i, False);
                 button_label = str(q_num); # Default label is number
                 if is_submitted: is_correct = st.session_state.user_answers.get(i) == questions_to_run[i]['correct_answer']; button_label = f"{q_num} {'✅' if is_correct else '❌'}";
                 with col: st.button(button_label, key=f"nav_{i}", on_click=go_to_question, args=(i,), type=button_type, use_container_width=True);

    # Sidebar score display during quiz
    st.sidebar.header("Score"); current_score = max(0, st.session_state.get('score', 0)); total_qs_in_state = len(st.session_state.get('quiz_questions', []));
    st.sidebar.metric("Current Score", f"{current_score} / {total_qs_in_state if total_qs_in_state > 0 else 'N/A'}");


# == Results Screen ==
elif current_screen == 'results': # Check using variable
    st.header("🎉 Quiz Complete! 🎉"); category = st.session_state.selected_category; sheet = st.session_state.selected_sheet;
    st.markdown(f"Category: **{category}** | Sheet: **{sheet}**") if category and sheet else None;
    num_questions = len(st.session_state.get('quiz_questions', [])); final_score = min(st.session_state.get('score', 0), num_questions);
    st.subheader(f"Your Final Score: {final_score} / {num_questions}");
    if num_questions > 0: percentage = round((final_score / num_questions) * 100); st.metric(label="Percentage", value=f"{percentage}%");
    else: st.write("No questions completed.");

    col1, col2 = st.columns(2);
    with col1: st.button("Take Another Quiz", key="restart", on_click=reset_and_select_category); # Reset and go to category select

    with st.expander("Review Your Answers"):
         questions_answered = st.session_state.get('quiz_questions', []); answers_given = st.session_state.get('user_answers', {});
         if not questions_answered: st.write("No answers recorded.")
         else:
             for i, q in enumerate(questions_answered):
                 user_ans = answers_given.get(i, "Not Answered"); correct_ans = q['correct_answer']; is_correct = (user_ans == correct_ans); feedback_icon = "✅" if is_correct else "❌";
                 st.markdown(f"**Q{i+1}:** `{q['med_name']}` - {q['question']}"); st.write(f"   Your answer: {user_ans} {feedback_icon}");
                 if not is_correct and user_ans != "Not Answered": st.write(f"   Correct answer: {correct_ans}");
                 st.divider();