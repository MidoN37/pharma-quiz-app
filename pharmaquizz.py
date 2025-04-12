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
try: from unidecode import unidecode
except ImportError:
    def unidecode(x):
        if 'unidecode_warning_shown' not in st.session_state: st.warning("`unidecode` missing."); st.session_state.unidecode_warning_shown = True
        return str(x)

# --- Page Config ---
st.set_page_config(layout="wide", page_title="Pharm Quiz")

# --- Project Setup ---
APP_DIR = Path(__file__).parent
PROJECT_ROOT = APP_DIR
EXCEL_DATA_ROOT = PROJECT_ROOT / "excel_data"
QUIZ_CSV_PATH = PROJECT_ROOT / "QUIZ" / "quiz_data_v2.csv" # Path to generated CSV

# --- Configuration ---
# Use categories matching folder names
CATEGORY_SUBDIRS = ["Antibiotiques", "Comprimés", "Comprimes antalgiques", "Cremes - Pommades", "Gouttes", "Injections", "Ovules vaginaux", "Pulvérisations", "Sachets", "Sirop", "Suppositoires"]
# Define expected header variations
MED_NAME_COLS = ['Spécialité', 'Nom', 'Médicament', 'Antibiotiques sachet', 'Antibiotiques sirop', 'Antibiotiques comprimé', 'Comprimés', 'ANTALGIQUES', 'Cremes', 'Gouttes', 'Injections', 'Ovules vaginaux', 'Pulvérisations', 'Sachets', 'Sirop', 'Suppositoires']
COMPOSITION_COLS = ['Composition', 'Composant(s)', 'Actif(s)', 'Compositions']
INDICATION_COLS = ['Indication(s)', 'Indications', 'Usage(s)', 'Indiquations', 'Indications (Usage simple pour un patient non-médical)', 'Classe thérapeutique']

# --- Populate Category Path Map (for Excel if needed - not used by quiz from CSV) ---
# This map isn't actually used if we only read the final CSV, but harmless to keep for now
category_excel_path_map = {}
for sub_dir in CATEGORY_SUBDIRS:
    normalized_subdir_name = sub_dir
    if normalized_subdir_name == "Cremes - Pommades": excel_filename = "Pommade - Cremes.xlsx"
    else: excel_filename = f"{normalized_subdir_name}.xlsx"
    excel_file_path = EXCEL_DATA_ROOT / normalized_subdir_name / excel_filename
    category_excel_path_map[normalized_subdir_name] = str(excel_file_path)
category_names = CATEGORY_SUBDIRS


# --- Helper Functions ---
def normalize_text(text):
    """Lowercase, NFC normalize, remove accents, basic cleanup."""
    if not isinstance(text, str): text = str(text)
    try:
        normalized = unicodedata.normalize('NFC', text); ascii_text = unidecode(normalized)
    except Exception: ascii_text = text
    cleaned = re.sub(r'[^\w\s\-]+', '', ascii_text).lower().strip(); cleaned = re.sub(r'\s+', ' ', cleaned);
    return cleaned

def find_column_by_keyword(header_series, keywords):
    """Finds column NAME by keyword in a header row (pandas Series). Case-insensitive."""
    # --- START Function Body ---
    if header_series is None or header_series.empty: return None
    header_values_lower = header_series.astype(str).str.lower().str.strip().tolist()
    original_headers = header_series.astype(str).tolist()

    # Prioritize exact keyword match
    for keyword in keywords:
        kw_lower = keyword.lower().strip()
        if kw_lower in header_values_lower:
            try:
                 idx = header_values_lower.index(kw_lower)
                 return original_headers[idx]; # Return original header name
            except ValueError:
                 pass; # Should not happen if 'in' is true, but safe practice

    # Then check if keyword is contained within a header cell
    for keyword in keywords:
        kw_lower = keyword.lower().strip()
        try:
            for i, header in enumerate(header_values_lower):
                if kw_lower in header:
                    return original_headers[i]; # Return original header name
        except Exception:
            pass; # Ignore errors during substring check
    return None # No match found
    # --- END Function Body ---

# --- Data Loading and Preparation ---
@st.cache_data(show_spinner="Loading medication data...")
def load_and_prepare_sheet_data(excel_path_str, sheet_name):

# --- Load ALL Quiz Data From CSV (Cached) ---
@st.cache_data(show_spinner="Loading quiz questions...")
def load_quiz_from_csv(path):
    """Loads quiz questions directly from the pre-generated CSV file."""
    print(f"Attempting to load quiz data from: {path}")
    try:
        if not path.exists(): st.error(f"Quiz CSV not found: {path}. Run generator script."); return None
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
        if not questions: st.warning(f"CSV '{path.name}' loaded but no valid questions found.")
        return questions
    except Exception as e: st.error(f"Failed to load/process Quiz CSV '{path.name}': {e}"); return None

# Load all questions once
ALL_QUIZ_QUESTIONS = load_quiz_from_csv(QUIZ_CSV_PATH)

# --- Get unique Categories and Sheets from loaded data ---
CATEGORIES = []
SHEETS_BY_CATEGORY = {}
if ALL_QUIZ_QUESTIONS:
    CATEGORIES = sorted(list(set(q['category'] for q in ALL_QUIZ_QUESTIONS)))
    for cat in CATEGORIES: SHEETS_BY_CATEGORY[cat] = sorted(list(set(q['sheet'] for q in ALL_QUIZ_QUESTIONS if q['category'] == cat)))
else:
     st.error("Could not load any questions from CSV. Cannot proceed.")
     # Optionally stop execution if critical data is missing
     # st.stop()


# --- Initialize Session State ---
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
def submit_answer():
    q_index = st.session_state.current_q_index
    # Use dynamic key for radio button value
    radio_key = f'quiz_option_{q_index}'
    selected_option = st.session_state.get(radio_key)

    if selected_option is not None and q_index < len(st.session_state.quiz_questions):
         st.session_state.user_answers[q_index] = selected_option
         st.session_state.submission_status[q_index] = True
         correct = (selected_option == st.session_state.quiz_questions[q_index]['correct_answer'])
         if correct and q_index not in st.session_state.correctly_answered_indices:
             st.session_state.score += 1
             st.session_state.correctly_answered_indices.add(q_index)
    # No rerun here - handled by button interaction

def go_to_question(target_index):
    num_questions = len(st.session_state.quiz_questions)
    if 0 <= target_index < num_questions:
        st.session_state.current_q_index = target_index
    else: print(f"Warning: Invalid jump target index: {target_index}")
    # No rerun here

def next_question():
    q_index = st.session_state.current_q_index
    num_questions = len(st.session_state.quiz_questions)
    if q_index < num_questions - 1:
        st.session_state.current_q_index += 1 # Directly increment index
        st.session_state.submission_status[q_index+1] = st.session_state.submission_status.get(q_index+1, False) # Keep next q submission status
        st.session_state.current_options = [] # Force reshuffle for next question
        # Radio key for next question will be generated dynamically
    else:
        finish_quiz() # Go to results if already on last question
    # No rerun needed immediately, state change triggers it if necessary via button click

# --- CORRECTED finish_quiz function ---
def finish_quiz():
     """Ends the quiz and sets state for results screen."""
     print("DEBUG: finish_quiz called") # Debug
     st.session_state.quiz_complete = True
     st.session_state.quiz_active = False
     # Set index past end to stop quiz loop cleanly
     st.session_state.current_q_index = len(st.session_state.get('quiz_questions', []))
     # No need to reset options/radio state here, results screen doesn't use them
     # st.rerun() # Avoid explicit rerun in callback

def reset_quiz_state():
     """Resets session state variables related to quiz progress AND selection."""
     print("DEBUG: reset_quiz_state called") # Debug
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
     # Clear dynamic radio keys (best effort)
     keys_to_delete = [k for k in st.session_state if k.startswith('quiz_option_')]
     for k in keys_to_delete: del st.session_state[k]


def start_quiz(category, sheet):
    """Filters pre-loaded questions, sets state to start quiz."""
    print(f"Starting quiz for: {category} - {sheet}")
    reset_quiz_state() # Reset previous quiz state first
    st.session_state.selected_category = category
    st.session_state.selected_sheet = sheet

    filtered_questions = [q for q in ALL_QUIZ_QUESTIONS if q.get('category') == category and q.get('sheet') == sheet]

    if not filtered_questions:
        st.error(f"No questions found for {category} - {sheet} in the loaded data.")
        st.session_state.quiz_active = False; return;

    random.shuffle(filtered_questions)
    st.session_state.quiz_questions = filtered_questions
    st.session_state.quiz_active = True # Activate quiz display
    st.session_state.quiz_complete = False
    print(f"DEBUG: Quiz started. Questions loaded: {len(st.session_state.quiz_questions)}")
    # st.rerun() # REMOVED - Let button click trigger rerun

def reset_and_select_category():
     """Resets all state and goes back to category selection screen."""
     # This function essentially does the same as reset_quiz_state and ensures selection is clear
     reset_quiz_state()
     st.session_state.selected_category = None # Ensure category is cleared too
     st.session_state.selected_sheet = None
     # No explicit screen variable needed now
     # st.rerun() # Rerun triggered by button click automatically


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

        # Start Quiz Button -> Calls start_quiz on click
        start_disabled = not (selected_category and selected_sheet)
        if st.button("Start Quiz", disabled=start_disabled, key="start_quiz_btn"):
            if selected_category and selected_sheet:
                 start_quiz(selected_category, selected_sheet)
                 # Rerun is handled implicitly by button click causing state change
            else: st.warning("Please select Category and Sheet.")

    st.markdown("---")


# --- Quiz Display Area ---
elif st.session_state.quiz_active:
    st.header(f"Quiz: {st.session_state.selected_category} - {st.session_state.selected_sheet}")
    col_top1, col_top2, col_top3 = st.columns([1.5, 1.5, 5]);
    # Use reset_and_select_category for Stop button
    with col_top1: st.button("⬅️ Stop & Change Quiz", key="stop_quiz", on_click=reset_and_select_category)
    with col_top2: st.button("Finish Quiz Now", key="finish_quiz", on_click=finish_quiz)
    st.markdown("---")

    questions_to_run = st.session_state.quiz_questions
    num_questions = len(questions_to_run)
    q_index = st.session_state.current_q_index
    print(f"DEBUG: Rendering Quiz Screen. Index: {q_index}, Total Qs: {num_questions}") # Debug

    if not questions_to_run: st.warning("No questions loaded.")
    # Check if index is past the end (quiz finished)
    elif q_index >= num_questions:
        st.info("Quiz finished! Processing results...") # Should transition to results screen
        st.session_state.quiz_active = False
        st.session_state.quiz_complete = True
        st.rerun() # Explicit rerun needed here to force screen change
    else:
        # Display current question UI
        current_q = questions_to_run[q_index]; st.subheader(f"Question {q_index + 1}/{num_questions}"); st.markdown(f"**{current_q['question']}**");
        options_key = f"options_{q_index}";
        if options_key not in st.session_state: options = current_q['options'][:]; random.shuffle(options); st.session_state[options_key] = options;
        options_to_display = st.session_state[options_key]; question_submitted = st.session_state.submission_status.get(q_index, False); disable_radio = question_submitted;
        current_selection = st.session_state.user_answers.get(q_index, None); current_index = None;
        radio_key = f'quiz_option_{q_index}' # Unique key for radio
        if current_selection is not None and current_selection in options_to_display: try: current_index = options_to_display.index(current_selection); except ValueError: current_index = None;

        user_choice = st.radio("Select:", options=options_to_display, index=current_index, key=radio_key, disabled=disable_radio, label_visibility="collapsed");

        # Submit/Next Buttons
        col_btn1, col_btn2 = st.columns([0.2, 0.8]);
        with col_btn1:
            if not question_submitted: submit_button = st.button("Submit", key=f"submit_{q_index}", on_click=submit_answer, disabled=(st.session_state.get(radio_key) is None));
        if question_submitted:
             with col_btn2: button_label = "Next >>" if q_index < num_questions - 1 else "See Results"; next_button = st.button(button_label, key=f"next_{q_index}", on_click=next_question);
        # Feedback
        if question_submitted:
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
             button_label = str(q_num);
             if is_submitted: is_correct = st.session_state.user_answers.get(i) == questions_to_run[i]['correct_answer']; button_label = f"{q_num} {'✅' if is_correct else '❌'}";
             with col: st.button(button_label, key=f"nav_{i}", on_click=go_to_question, args=(i,), type=button_type, use_container_width=True);

    # Sidebar score display
    st.sidebar.header("Score"); current_score = max(0, st.session_state.get('score', 0)); total_qs_in_state = len(st.session_state.get('quiz_questions', []));
    st.sidebar.metric("Current Score", f"{current_score} / {total_qs_in_state if total_qs_in_state > 0 else 'N/A'}");


# --- Results Display Area ---
elif st.session_state.quiz_complete:
    st.header("🎉 Quiz Complete! 🎉"); category = st.session_state.selected_category; sheet = st.session_state.selected_sheet;
    st.markdown(f"Category: **{category}** | Sheet: **{sheet}**") if category and sheet else None;
    num_questions = len(st.session_state.get('quiz_questions', [])); final_score = min(st.session_state.get('score', 0), num_questions);
    st.subheader(f"Your Final Score: {final_score} / {num_questions}");
    if num_questions > 0: percentage = round((final_score / num_questions) * 100); st.metric(label="Percentage", value=f"{percentage}%");
    else: st.write("No questions completed.");

    col1, col2 = st.columns(2);
    with col1:
        # Use reset_and_select_category to go back to the start screen
        st.button("Take Another Quiz", key="restart", on_click=reset_and_select_category);

    with st.expander("Review Your Answers"):
         questions_answered = st.session_state.get('quiz_questions', []); answers_given = st.session_state.get('user_answers', {});
         if not questions_answered: st.write("No answers recorded.")
         else:
             for i, q in enumerate(questions_answered):
                 user_ans = answers_given.get(i, "Not Answered"); correct_ans = q['correct_answer']; is_correct = (user_ans == correct_ans); feedback_icon = "✅" if is_correct else "❌";
                 st.markdown(f"**Q{i+1}:** `{q['med_name']}` - {q['question']}"); st.write(f"   Your answer: {user_ans} {feedback_icon}");
                 if not is_correct and user_ans != "Not Answered": st.write(f"   Correct answer: {correct_ans}");
                 st.divider();