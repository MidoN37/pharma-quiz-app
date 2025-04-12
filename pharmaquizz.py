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
    def unidecode(x): # Simple fallback
        if 'unidecode_warning_shown' not in st.session_state:
            st.warning("`unidecode` library missing (pip install unidecode). Accent handling less robust.")
            st.session_state.unidecode_warning_shown = True
        return str(x)

# --- Page Config ---
st.set_page_config(layout="wide", page_title="Pharm Quiz")

# --- Project Setup ---
APP_DIR = Path(__file__).parent
PROJECT_ROOT = APP_DIR
# Path to the generated QUIZ CSV file relative to the script
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
        try:
            df = pd.read_csv(path, keep_default_na=False, encoding='utf-8-sig')
        except UnicodeDecodeError:
            print("UTF-8-SIG failed, trying standard UTF-8...")
            df = pd.read_csv(path, keep_default_na=False, encoding='utf-8')

        print(f"Loaded {len(df)} questions from CSV.")
        questions = []
        option_cols = [col for col in df.columns if col.startswith('Option_')]
        for _, row in df.iterrows():
            options = [row[col] for col in option_cols if pd.notna(row[col]) and row[col]]
            entry = {
                'category': row['Category'],
                'sheet': row['Sheet'],
                'med_name': row['MedicationName'],
                'question': row['Question'],
                'options': options,
                'correct_answer': row['CorrectAnswer']
            }
            # Basic validation: Ensure essential fields exist and options are present
            if all(k in entry and pd.notna(entry[k]) for k in ['category', 'sheet', 'med_name', 'question', 'correct_answer']) and entry['options']:
                questions.append(entry)
            else:
                 print(f"Skipping invalid row from CSV: {row.to_dict()}") # Log invalid rows

        print(f"Filtered to {len(questions)} valid questions.")
        return questions
    except Exception as e:
        st.error(f"Failed to load or process Quiz CSV '{path.name}': {e}")
        return None

# Load all questions once
ALL_QUIZ_QUESTIONS = load_quiz_from_csv(QUIZ_CSV_PATH)

# --- Get unique Categories and Sheets ---
CATEGORIES = []
SHEETS_BY_CATEGORY = {}
if ALL_QUIZ_QUESTIONS:
    CATEGORIES = sorted(list(set(q['category'] for q in ALL_QUIZ_QUESTIONS)))
    for cat in CATEGORIES:
        SHEETS_BY_CATEGORY[cat] = sorted(list(set(q['sheet'] for q in ALL_QUIZ_QUESTIONS if q['category'] == cat)))


# --- Initialize Session State ---
# General quiz flow states
if 'selected_category' not in st.session_state: st.session_state.selected_category = None
if 'selected_sheet' not in st.session_state: st.session_state.selected_sheet = None
if 'quiz_active' not in st.session_state: st.session_state.quiz_active = False
if 'quiz_complete' not in st.session_state: st.session_state.quiz_complete = False
# Quiz specific data/progress
if 'quiz_questions' not in st.session_state: st.session_state.quiz_questions = [] # Holds SHUFFLED questions for current quiz
if 'current_q_index' not in st.session_state: st.session_state.current_q_index = 0
if 'score' not in st.session_state: st.session_state.score = 0
if 'user_answers' not in st.session_state: st.session_state.user_answers = {} # Tracks {q_index: answer}
if 'submission_status' not in st.session_state: st.session_state.submission_status = {} # Tracks {q_index: True/False} Tracks if answer submitted FOR REVIEW purposes
if 'current_options' not in st.session_state: st.session_state.current_options = [] # Shuffled options for current q
if 'correctly_answered_indices' not in st.session_state: st.session_state.correctly_answered_indices = set() # Tracks indices scored correct


# --- Helper Functions for State Updates ---
def submit_answer():
    """Callback for Submit button. Marks question as submitted and scores if correct."""
    q_index = st.session_state.current_q_index
    selected_option = st.session_state.get(f'quiz_option_{q_index}') # Use index in key

    if selected_option is not None and q_index < len(st.session_state.quiz_questions):
         st.session_state.user_answers[q_index] = selected_option # Store the answer
         st.session_state.submission_status[q_index] = True # Mark as submitted

         # Score only if correct AND not already scored correctly in this session
         correct = (selected_option == st.session_state.quiz_questions[q_index]['correct_answer'])
         if correct and q_index not in st.session_state.correctly_answered_indices:
             st.session_state.score += 1
             st.session_state.correctly_answered_indices.add(q_index)


def go_to_question(target_index):
    """Callback for number buttons. Jumps to a specific question."""
    num_questions = len(st.session_state.quiz_questions)
    if 0 <= target_index < num_questions:
        st.session_state.current_q_index = target_index
        # When jumping, DO NOT reset submission status (allow review)
        # When jumping, DO NOT reshuffle options
        # Resetting the radio button key might cause issues if user jumps away and back
        # Instead, rely on the radio widget reading the correct index based on user_answers
        # st.session_state.current_options = [] # Don't reshuffle on jump
        # if f'quiz_option_{target_index}' in st.session_state: del st.session_state[f'quiz_option_{target_index}'] # Avoid direct deletion
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
     # Don't reset score/answers here, needed for results page
     # Optionally reset current_q_index, current_options etc.
     st.session_state.current_q_index = len(st.session_state.quiz_questions) # Set past end
     st.session_state.current_options = []
     if f'quiz_option_{st.session_state.current_q_index}' in st.session_state: del st.session_state[f'quiz_option_{st.session_state.current_q_index}']


def reset_and_select_category():
     """Resets all state and goes back to category selection."""
     st.session_state.selected_category = None
     st.session_state.selected_sheet = None
     st.session_state.quiz_questions = []
     st.session_state.current_q_index = 0
     st.session_state.score = 0
     st.session_state.user_answers = {}
     st.session_state.submission_status = {}
     st.session_state.current_options = []
     st.session_state.quiz_active = False
     st.session_state.quiz_complete = False
     st.session_state.correctly_answered_indices = set()
     # Clear potentially dynamic radio keys if needed (complex)
     # for key in list(st.session_state.keys()):
     #    if key.startswith("quiz_option_"): del st.session_state[key]


def start_quiz(category, sheet):
    """Filters pre-loaded questions, sets state to start quiz."""
    print(f"Starting quiz for: {category} - {sheet}")
    reset_quiz_state() # Reset previous quiz state first
    st.session_state.selected_category = category
    st.session_state.selected_sheet = sheet

    # Filter ALL_QUIZ_QUESTIONS for the selected category and sheet
    filtered_questions = [
        q for q in ALL_QUIZ_QUESTIONS
        if q['category'] == category and q['sheet'] == sheet
    ]

    if not filtered_questions:
        st.error(f"No questions found for {category} - {sheet} in the loaded data.")
        st.session_state.quiz_active = False # Ensure quiz doesn't start
        return # Stop if no questions

    random.shuffle(filtered_questions) # Shuffle questions for this session
    st.session_state.quiz_questions = filtered_questions
    st.session_state.quiz_active = True # Activate quiz display
    st.session_state.quiz_complete = False
    # No rerun needed here, state change will trigger it


# --- Streamlit App UI ---
st.title("💊 Pharma Quiz 💊")

# --- Quiz Selection Area ---
# Show selection only if quiz is NOT active AND NOT complete
if not st.session_state.quiz_active and not st.session_state.quiz_complete:
    st.header("Select Quiz")

    if not ALL_QUIZ_QUESTIONS:
        st.error("Quiz data could not be loaded. Please check 'QUIZ/quiz_data_v2.csv'.")
    else:
        # Category Selectbox
        selected_category = st.selectbox(
            "Choose a Category:", options=[""] + CATEGORIES,
            format_func=lambda x: "Select Category..." if x == "" else x, key='cat_select_dd'
        )
        selected_sheet = None
        if selected_category:
            available_sheets_for_cat = SHEETS_BY_CATEGORY.get(selected_category, [])
            if len(available_sheets_for_cat) == 1:
                selected_sheet = available_sheets_for_cat[0]; st.write(f"Sheet: **{selected_sheet}**")
            elif len(available_sheets_for_cat) > 1:
                selected_sheet = st.selectbox("Choose a Sheet:", options=[""] + available_sheets_for_cat, format_func=lambda x: "Select Sheet..." if x == "" else x, key='sheet_select_dd')
            else: st.warning(f"No valid sheets found for '{selected_category}'.")

        # Start Quiz Button
        start_disabled = not (selected_category and selected_sheet)
        if st.button("Start Quiz", disabled=start_disabled, key="start_quiz_btn"):
            if selected_category and selected_sheet: start_quiz(selected_category, selected_sheet)
            else: st.warning("Please select Category and Sheet.")

    st.markdown("---") # Separator below selection


# --- Quiz Display Area ---
elif st.session_state.quiz_active:
    st.header(f"Quiz: {st.session_state.selected_category} - {st.session_state.selected_sheet}")
    # Place Stop and Finish buttons at the top
    col_top1, col_top2, col_top3 = st.columns([1.5, 1.5, 5]) # Adjust ratios
    with col_top1: st.button("⬅️ Stop & Change Quiz", key="stop_quiz", on_click=reset_and_select_category) # Reset all state
    with col_top2: st.button("Finish Quiz Now", key="finish_quiz", on_click=finish_quiz) # Go to results
    st.markdown("---")

    questions_to_run = st.session_state.quiz_questions
    num_questions = len(questions_to_run)
    q_index = st.session_state.current_q_index # Current question index

    if not questions_to_run: st.warning("No questions loaded for this quiz.")
    elif q_index >= num_questions: st.error("Quiz index out of bounds. Resetting."); reset_quiz_state(); st.rerun(); # Should not happen
    else:
        # --- Display Current Question ---
        current_q = questions_to_run[q_index];
        st.subheader(f"Question {q_index + 1}/{num_questions}");
        st.markdown(f"**{current_q['question']}**");

        # Get options, shuffle ONCE per question index if not already done for this index
        options_key = f"options_{q_index}"
        if options_key not in st.session_state:
            options = current_q['options'][:]; random.shuffle(options);
            st.session_state[options_key] = options # Store shuffled options for this index
        options_to_display = st.session_state[options_key]

        # Determine if submitted and get previous answer if any
        question_submitted = st.session_state.submission_status.get(q_index, False)
        disable_radio = question_submitted
        current_selection = st.session_state.user_answers.get(q_index, None) # Get previous answer for this index
        current_index = None
        if current_selection is not None and current_selection in options_to_display:
             try: current_index = options_to_display.index(current_selection);
             except ValueError: current_index = None;

        # Display Radio using unique key per question index
        user_choice = st.radio("Select:", options=options_to_display, index=current_index, key=f'quiz_option_{q_index}', disabled=disable_radio, label_visibility="collapsed");

        # --- Buttons: Submit / Next ---
        col_btn1, col_btn2 = st.columns([0.2, 0.8]);
        with col_btn1:
            # Show Submit only if this question hasn't been submitted yet
            if not question_submitted:
                submit_button = st.button("Submit", key=f"submit_{q_index}", on_click=submit_answer, disabled=(st.session_state.get(f'quiz_option_{q_index}') is None));
        if question_submitted:
             # Show Next only after submission
             with col_btn2:
                  button_label = "Next >>" if q_index < num_questions - 1 else "See Results";
                  next_button = st.button(button_label, key=f"next_{q_index}", on_click=next_question);

        # --- Feedback (shown only after submission) ---
        if question_submitted:
            st.markdown("---"); user_ans = st.session_state.user_answers.get(q_index, None); correct_ans = current_q['correct_answer'];
            if user_ans is not None:
                if user_ans == correct_ans: st.success(f"**Correct!** {correct_ans}");
                else: st.error(f"**Incorrect.** You answered: {user_ans}"); st.info(f"**Correct answer:** {correct_ans}");

        # --- Question Navigation Buttons ---
        st.markdown("---")
        st.write("**Navigate Questions:**")
        # Display buttons in columns
        cols_per_row = 10 # Adjust how many buttons per row
        num_rows = (num_questions + cols_per_row - 1) // cols_per_row
        nav_cols = st.columns(cols_per_row)
        for i in range(num_questions):
             col = nav_cols[i % cols_per_row]
             q_num = i + 1
             button_type = "primary" if i == q_index else "secondary" # Highlight current question
             is_submitted = st.session_state.submission_status.get(i, False)
             is_correct = st.session_state.user_answers.get(i) == questions_to_run[i]['correct_answer'] if is_submitted else False

             # Button label shows status
             if is_submitted: button_label = f"{q_num} {'✅' if is_correct else '❌'}"
             else: button_label = str(q_num)

             with col:
                  st.button(button_label, key=f"nav_{i}", on_click=go_to_question, args=(i,), type=button_type, use_container_width=True)


    # --- Sidebar score display ---
    st.sidebar.header("Score")
    current_score = max(0, st.session_state.get('score', 0)); total_qs_in_state = len(st.session_state.get('quiz_questions', []));
    st.sidebar.metric("Current Score", f"{current_score} / {total_qs_in_state if total_qs_in_state > 0 else 'N/A'}");


# --- Results Display Area ---
elif st.session_state.quiz_complete:
    st.header("🎉 Quiz Complete! 🎉");
    category = st.session_state.selected_category; sheet = st.session_state.selected_sheet;
    st.markdown(f"Category: **{category}** | Sheet: **{sheet}**") if category and sheet else None # Show context
    num_questions = len(st.session_state.get('quiz_questions', [])); final_score = min(st.session_state.get('score', 0), num_questions);
    st.subheader(f"Your Final Score: {final_score} / {num_questions}");
    if num_questions > 0: percentage = round((final_score / num_questions) * 100); st.metric(label="Percentage", value=f"{percentage}%");
    else: st.write("No questions completed.");

    col1, col2 = st.columns(2);
    with col1: st.button("Take Another Quiz", key="restart", on_click=reset_and_select_category); # Full reset

    with st.expander("Review Your Answers"):
         questions_answered = st.session_state.get('quiz_questions', []); answers_given = st.session_state.get('user_answers', {});
         if not questions_answered: st.write("No answers recorded.")
         else:
             for i, q in enumerate(questions_answered):
                 user_ans = answers_given.get(i, "Not Answered"); correct_ans = q['correct_answer']; is_correct = (user_ans == correct_ans); feedback_icon = "✅" if is_correct else "❌";
                 st.markdown(f"**Q{i+1}:** `{q['med_name']}` - {q['question']}"); st.write(f"   Your answer: {user_ans} {feedback_icon}");
                 if not is_correct and user_ans != "Not Answered": st.write(f"   Correct answer: {correct_ans}");
                 st.divider();