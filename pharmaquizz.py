import streamlit as st
import pandas as pd
import random
import unicodedata # Keep if used elsewhere, seems unused here
import re # Keep if used elsewhere, seems unused here
from pathlib import Path

# --- Page Config ---
st.set_page_config(layout="wide", page_title="Pharm Quiz")

# --- Project Setup & File Paths ---
# Use absolute path resolution relative to the script file
try:
    APP_DIR = Path(__file__).parent
except NameError: # Handle cases where __file__ is not defined (e.g., running in some environments)
    APP_DIR = Path.cwd()
PROJECT_ROOT = APP_DIR
QUIZ_CSV_PATH = PROJECT_ROOT / "QUIZ" / "quiz_data_v2.csv"
IMAGE_CSV_PATH = PROJECT_ROOT / "QUIZ" / "github_image_urls_CATEGORIZED.csv"

# --- Load Quiz Data ---
@st.cache_data(show_spinner="Loading quiz data...")
def load_quiz_data(path):
    try:
        if not path.exists():
            st.error(f"Quiz data CSV not found: {path}")
            return None
        try:
            # Try utf-8 first as it's more common, fallback to utf-8-sig
            df = pd.read_csv(path, keep_default_na=False, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(path, keep_default_na=False, encoding='utf-8-sig')
        except Exception as e:
             st.error(f"Failed to load quiz CSV with specified encodings: {e}")
             return None

        required = ['Category', 'Sheet', 'MedicationName', 'Question', 'CorrectAnswer']
        if not all(col in df.columns for col in required):
            st.error(f"CSV missing required columns. Need at least: {required}. Found: {list(df.columns)}")
            return None
        return df
    except Exception as e:
        st.error(f"Failed to load/parse quiz CSV: {e}")
        return None

# --- Load Image URL Data ---
@st.cache_data(show_spinner="Loading image data...")
def load_image_data(path):
    try:
        if not path.exists():
            st.warning(f"Image data CSV not found: {path}. Images based on MedicationName might not load.")
            return pd.DataFrame(columns=['category', 'filename', 'raw_url']) # Return empty DF with expected cols
        try:
            df = pd.read_csv(path, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(path, encoding='utf-8-sig')
        except Exception as e:
             st.error(f"Failed to load image CSV with specified encodings: {e}")
             return pd.DataFrame(columns=['category', 'filename', 'raw_url'])

        required = ['category', 'filename', 'raw_url']
        if not all(col in df.columns for col in required):
            st.error(f"Image CSV missing required columns. Required: {required}. Found: {list(df.columns)}")
            return pd.DataFrame(columns=['category', 'filename', 'raw_url'])
        return df
    except Exception as e:
        st.error(f"Error loading image CSV: {e}")
        return pd.DataFrame(columns=['category', 'filename', 'raw_url'])

# --- Helper: Determine Override URL ---
def get_override_url(category, sheet, med_name):
    base = (
        "https://raw.githubusercontent.com/MidoN37/pharma-data-viewer/refs/heads/master/assets/images"
    )
    # Handle potential None or non-string inputs gracefully
    cat = str(category).strip() if category else ""
    med = str(med_name).strip() if med_name else ""
    sheet_lower = str(sheet).strip().lower() if sheet else ""

    # Antibiotiques overrides by sheet
    if cat == "Antibiotiques":
        if sheet_lower == "comprime":
            return f"{base}/Antibiotiques/Antiobiotiques%20Comprimes.jpg"
        if sheet_lower == "sachet":
            return f"{base}/Antibiotiques/Antibiotiques%20Sachet.jpg"
        if sheet_lower == "sirop":
            return f"{base}/Antibiotiques/Antibiotiques%20Sirop.jpg"
    # Sirop category override
    if cat == "Sirop":
        return f"{base}/Sirops/Sirop%20Tout.jpg"
    # Suppositoires override by first letter
    if cat == "Suppositoires":
        first = med[0].upper() if med else ''
        if 'A' <= first <= 'N':
            return f"{base}/Suppositoires/Suppositoires.jpeg"
        elif first: # Check if first character exists before comparing
             return f"{base}/Suppositoires/Suppositoires%202.jpeg"
        # else: # Optional: handle case where med name is empty or doesn't start with a letter
        #     return None # Or a default suppository image?

    return None # No override found

# --- Normalize function for matching ---
def normalize_text(text):
    """Normalize text by lowercasing, removing accents, and extra whitespace."""
    if not isinstance(text, str):
        return ""
    # NFKD decomposition separates characters from accents
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    text = text.lower().strip()
    # Optional: remove punctuation or specific characters if needed
    # text = re.sub(r'[^\w\s]', '', text)
    return text

# --- Get Image URL (handles overrides and lookups) ---
def get_image_url(df_images, category, sheet, med_name):
    """Gets the appropriate image URL, checking overrides first."""
    override = get_override_url(category, sheet, med_name)
    if override:
        return override

    if df_images.empty or not med_name or not category:
        return None

    # Normalize for robust matching
    norm_med = normalize_text(med_name)
    norm_cat = normalize_text(category)

    # Prepare image dataframe for matching (normalize once if possible, maybe cache this?)
    # Adding a temporary normalized column for matching
    df_images['_norm_cat'] = df_images['category'].apply(normalize_text)
    # Extract filename without extension and normalize
    df_images['_norm_filename'] = df_images['filename'].str.extract(r'([^/]+)\.[^.]*$', expand=False).fillna('').apply(normalize_text)


    # Find matching rows
    img_row = df_images[
        (df_images['_norm_cat'] == norm_cat) &
        (df_images['_norm_filename'] == norm_med)
    ]

    # Clean up temporary columns if needed, though leaving them might be fine
    # df_images.drop(columns=['_norm_cat', '_norm_filename'], inplace=True)

    if not img_row.empty:
        return img_row.iloc[0]['raw_url']

    return None

# --- Display Image ---
def display_image(url):
    """Displays the image from a URL using Markdown."""
    if url:
        st.markdown(f'<a href="{url}" target="_blank"><img src="{url}" alt="Medication Image" style="max-width:100%; max-height: 400px; object-fit: contain;"/></a>', unsafe_allow_html=True)
    # else:
    #     st.write("_(No image available)_") # Optional placeholder

# --- Main Execution ---
if __name__ == "__main__":
    df_all = load_quiz_data(QUIZ_CSV_PATH)
    df_images = load_image_data(IMAGE_CSV_PATH) # Load images once

    if df_all is None:
        st.error("Quiz data could not be loaded. Stopping application.")
        st.stop()

    # Initialize session state keys reliably
    default_values = {
        'selected_category': None,
        'selected_sheet': None,
        'question_index': 0,
        'answers': {}, # Stores user's selected answer for each question index
        'show_result': False,
        'current_quiz_df': pd.DataFrame(),
        'current_quiz_options': {}, # *** NEW: Stores shuffled options for each question index
        'quiz_loaded': False # Flag to indicate if a quiz is active
    }
    for key, default_value in default_values.items():
        st.session_state.setdefault(key, default_value)

    # --- Sidebar ---
    st.sidebar.title("Quiz Settings")

    categories = sorted(df_all['Category'].unique()) if not df_all.empty else []

    # Use the session state value directly if it exists, otherwise default
    current_selection_cat = st.session_state.selected_category
    if current_selection_cat not in categories and categories:
        current_selection_cat = categories[0] # Default to first if invalid or None

    selected_cat = st.sidebar.selectbox(
        "Select Category",
        options=categories,
        index=categories.index(current_selection_cat) if current_selection_cat in categories else 0,
        key='sb_cat' # Keep key if needed for other logic, though direct state access is often cleaner
    )

    # --- State Reset Logic ---
    # Check if category selection changed
    if selected_cat != st.session_state.selected_category:
        st.session_state.selected_category = selected_cat
        # Reset dependent states
        st.session_state.selected_sheet = None
        st.session_state.current_quiz_df = pd.DataFrame()
        st.session_state.question_index = 0
        st.session_state.answers = {}
        st.session_state.show_result = False
        st.session_state.current_quiz_options = {}
        st.session_state.quiz_loaded = False
        st.rerun() # Rerun to update sheet options and main page

    # --- Sheet Selection ---
    if st.session_state.selected_category:
        available_sheets = sorted(df_all[df_all['Category'] == st.session_state.selected_category]['Sheet'].unique())

        # Auto-select sheet if only one is available
        if len(available_sheets) == 1 and st.session_state.selected_sheet != available_sheets[0]:
             st.session_state.selected_sheet = available_sheets[0]
             # Reset quiz state if sheet changes automatically
             st.session_state.current_quiz_df = pd.DataFrame()
             st.session_state.question_index = 0
             st.session_state.answers = {}
             st.session_state.show_result = False
             st.session_state.current_quiz_options = {}
             st.session_state.quiz_loaded = False
             # No rerun needed here usually, sidebar write updates fine. If issues, add rerun.


        if len(available_sheets) > 1:
            # Prepare options for sheet selection, adding a placeholder
            sheet_options = ["-- Select Sheet --"] + available_sheets
            current_selection_sheet = st.session_state.selected_sheet
            # Ensure the current selection is valid, otherwise default to placeholder
            try:
                current_index_sheet = sheet_options.index(current_selection_sheet) if current_selection_sheet else 0
            except ValueError:
                current_index_sheet = 0 # Default to placeholder if state holds an invalid value

            selected_sheet_option = st.sidebar.selectbox(
                "Select Sheet",
                options=sheet_options,
                index=current_index_sheet,
                key='sb_sheet'
            )

            # Update state only if a valid sheet (not the placeholder) is chosen and it's different
            new_selected_sheet = selected_sheet_option if selected_sheet_option != "-- Select Sheet --" else None
            if new_selected_sheet != st.session_state.selected_sheet:
                st.session_state.selected_sheet = new_selected_sheet
                # Reset quiz state when sheet changes
                st.session_state.current_quiz_df = pd.DataFrame()
                st.session_state.question_index = 0
                st.session_state.answers = {}
                st.session_state.show_result = False
                st.session_state.current_quiz_options = {}
                st.session_state.quiz_loaded = False
                st.rerun()

        elif len(available_sheets) == 1:
            st.sidebar.write(f"Sheet: **{available_sheets[0]}** (Auto-selected)")
            # Ensure state reflects auto-selection (already done above)
        else:
            st.sidebar.warning("No sheets found for this category.")
            st.session_state.selected_sheet = None # Ensure it's None if no sheets

    # --- Load/Restart Button ---
    start_disabled = not (st.session_state.selected_category and st.session_state.selected_sheet)
    if st.sidebar.button("Load / Restart Quiz", disabled=start_disabled, type="primary"):
        if st.session_state.selected_category and st.session_state.selected_sheet:
            filtered = df_all[
                (df_all['Category'] == st.session_state.selected_category) &
                (df_all['Sheet'] == st.session_state.selected_sheet)
            ].copy() # Use copy to avoid SettingWithCopyWarning if modifying later

            if not filtered.empty:
                st.session_state.current_quiz_df = filtered.sample(frac=1).reset_index(drop=True)
                # Reset all quiz-specific states
                st.session_state.question_index = 0
                st.session_state.answers = {}
                st.session_state.show_result = False
                st.session_state.current_quiz_options = {} # Clear stored options
                st.session_state.quiz_loaded = True # Mark quiz as loaded
                st.rerun() # Start the quiz display
            else:
                st.sidebar.error("No questions found for this selection.")
                st.session_state.quiz_loaded = False
        else:
             st.sidebar.error("Please select both category and sheet.")
             st.session_state.quiz_loaded = False


    st.sidebar.markdown("---") # Use sidebar markdown

    # --- Main Quiz Area ---
    st.title("💊 Pharm Quiz App")
    st.markdown("---")

    # Quiz flow: Only proceed if a quiz is loaded and results are not shown
    if st.session_state.quiz_loaded and not st.session_state.show_result:
        df = st.session_state.current_quiz_df
        total_questions = len(df)
        current_q_index = st.session_state.question_index

        # Check if index is valid (it should be, but safety check)
        if 0 <= current_q_index < total_questions:
            question_data = df.iloc[current_q_index]

            # Display Question Number
            st.subheader(f"Question {current_q_index + 1} of {total_questions}")

            # Display Image (using the helper function)
            med_name = question_data.get('MedicationName', '')
            image_url = get_image_url(df_images, st.session_state.selected_category, st.session_state.selected_sheet, med_name)
            display_image(image_url)


            # Display Question Text
            st.write(f"**Category:** {st.session_state.selected_category} | **Sheet:** {st.session_state.selected_sheet}")
            if med_name: # Display med name if available
                 st.write(f"**Medication:** {med_name}")
            st.markdown(f"**Question:** {question_data['Question']}")


            # --- Generate and Display Options (Crucial Change) ---
            # Check if options for this question are already generated and shuffled in session state
            if current_q_index not in st.session_state.current_quiz_options:
                # Generate options only ONCE per question load
                correct_answer = question_data['CorrectAnswer']
                options = [question_data.get(f'Option_{i}') for i in range(1, 6)]
                options = [opt for opt in options if pd.notna(opt) and opt] # Filter out empty/NaN options

                # Combine options and correct answer, ensure uniqueness
                all_options = list(pd.Series(options + [correct_answer]).drop_duplicates().dropna())

                # Shuffle the options ONCE
                random.shuffle(all_options)

                # Store the shuffled options in session state for this question index
                st.session_state.current_quiz_options[current_q_index] = all_options
            else:
                # Retrieve the already shuffled options from session state
                all_options = st.session_state.current_quiz_options[current_q_index]

            # --- Display Radio Buttons (Crucial Change) ---
            # Determine the default selection index for radio button
            previous_answer = st.session_state.answers.get(current_q_index)
            try:
                 # If an answer was previously submitted, find its index in the *current* options list
                 default_index = all_options.index(previous_answer) if previous_answer is not None else None
            except ValueError:
                 # Handle case where a saved answer might not be in the current options (shouldn't happen with this logic, but safe)
                 default_index = None


            # Use index=None for no default selection if not answered before
            # Add a unique key based on the question index to prevent state conflicts
            user_choice = st.radio(
                "Select your answer:",
                options=all_options,
                index=default_index, # Set to None for no initial selection or index of previous answer
                key=f"q_{current_q_index}_options" # Unique key for the radio widget
            )

            # --- Submit Button and Answer Handling ---
            submit_col, feedback_col = st.columns([1, 3]) # Allocate space

            with submit_col:
                 submit_pressed = st.button("Submit Answer", key=f"submit_{current_q_index}")

            with feedback_col:
                 # Display feedback ONLY if the answer for *this specific question* has been submitted
                 if current_q_index in st.session_state.answers:
                     stored_answer = st.session_state.answers[current_q_index]
                     correct_answer = question_data['CorrectAnswer']
                     if stored_answer == correct_answer:
                         st.success("Correct! ✅")
                     else:
                         st.error(f"Incorrect! The correct answer is: **{correct_answer}** ❌")
                 # else: # Optional: Placeholder while not submitted
                 #     st.empty() # Or st.write("Select an answer and click Submit.")


            # Process submission *after* rendering the radio button and button
            if submit_pressed:
                 # Store the selected answer when submit is pressed
                 st.session_state.answers[current_q_index] = user_choice
                 # Rerun to display feedback immediately and lock the radio button state visually
                 st.rerun()


            st.markdown("---") # Separator

            # --- Navigation Buttons ---
            col1, col2, col3 = st.columns([1, 1, 5]) # Adjust ratios as needed
            with col1:
                if st.button("⬅️ Previous", disabled=current_q_index <= 0):
                    st.session_state.question_index -= 1
                    st.rerun()
            with col2:
                if st.button("Next ➡️", disabled=current_q_index >= total_questions - 1):
                    st.session_state.question_index += 1
                    st.rerun()
            # col3 remains empty or for future use

            st.markdown("---")

            # --- Go To Question Navigation ---
            st.write("**Go to question:**")
            # Dynamically adjust columns based on total questions
            num_nav_cols = min(total_questions, 10) # Max 10 columns for navigation buttons
            nav_cols = st.columns(num_nav_cols)

            for i in range(total_questions):
                nav_col = nav_cols[i % num_nav_cols] # Cycle through columns
                q_label = str(i + 1)
                q_state_icon = ""
                if i in st.session_state.answers:
                    # Check correctness based on stored answer and actual correct answer
                    is_correct = st.session_state.answers[i] == df.iloc[i]['CorrectAnswer']
                    q_state_icon = " ✅" if is_correct else " ❌"

                # Determine button type: primary if current question, secondary otherwise
                btn_type = "primary" if i == current_q_index else "secondary"

                if nav_col.button(f"{q_label}{q_state_icon}", key=f"nav_{i}", type=btn_type):
                    st.session_state.question_index = i
                    st.rerun()

            st.markdown("---") # Separator

            # --- Finish Quiz Button ---
            if st.button("🏁 Finish Quiz and See Results"):
                st.session_state.show_result = True
                st.rerun()

        else:
            # Handle invalid question index (e.g., after data reload)
            st.warning("Invalid question index. Restarting quiz selection.")
            st.session_state.question_index = 0
            st.session_state.quiz_loaded = False # Force reload
            st.rerun()


    # --- Results Page ---
    elif st.session_state.show_result:
        st.subheader("📊 Quiz Results")
        df = st.session_state.current_quiz_df
        total = len(df)
        answers = st.session_state.answers

        correct_count = 0
        incorrect_count = 0
        answered_indices = set(answers.keys())

        for i in range(total):
            if i in answered_indices:
                if answers[i] == df.iloc[i]['CorrectAnswer']:
                    correct_count += 1
                else:
                    incorrect_count += 1

        unanswered_count = total - len(answered_indices)

        # Display Summary Stats
        res_col1, res_col2, res_col3, res_col4 = st.columns(4)
        res_col1.metric("✅ Correct", correct_count)
        res_col2.metric("❌ Incorrect", incorrect_count)
        res_col3.metric("❓ Unanswered", unanswered_count)
        score_percent = (correct_count / total * 100) if total > 0 else 0
        res_col4.metric("🏆 Score", f"{correct_count}/{total}", f"{score_percent:.1f}%")

        if st.button("🚀 Start New Quiz (Same Settings)"):
             # Reset only quiz progress, keep category/sheet
            st.session_state.current_quiz_df = df.sample(frac=1).reset_index(drop=True) # Reshuffle
            st.session_state.question_index = 0
            st.session_state.answers = {}
            st.session_state.show_result = False
            st.session_state.current_quiz_options = {} # Clear stored options
            st.session_state.quiz_loaded = True # It's loaded again
            st.rerun()

        if st.button("⚙️ Change Settings and Start New Quiz"):
             # Reset everything except potentially category/sheet selection if desired
             # For a full reset feeling:
            st.session_state.question_index = 0
            st.session_state.answers = {}
            st.session_state.show_result = False
            st.session_state.current_quiz_df = pd.DataFrame()
            st.session_state.current_quiz_options = {}
            st.session_state.quiz_loaded = False
             # Optional: reset category/sheet too if you want user to re-select
            # st.session_state.selected_category = None
            # st.session_state.selected_sheet = None
            st.rerun()


        # --- Review Answers Expander ---
        with st.expander("🧐 Review Your Answers", expanded=False):
            if total == 0:
                st.write("No questions were loaded for review.")
            else:
                for i in range(total):
                    question_data = df.iloc[i]
                    user_answer = answers.get(i, "Not Answered")
                    correct_answer = question_data['CorrectAnswer']
                    is_correct = user_answer == correct_answer
                    status_icon = ""
                    if i in answered_indices:
                        status_icon = "✅" if is_correct else "❌"
                    else:
                        status_icon = "❓"


                    st.markdown(f"**Question {i+1}:** {question_data['Question']}")

                     # Display Image in review
                    med_name = question_data.get('MedicationName', '')
                    image_url = get_image_url(df_images, st.session_state.selected_category, st.session_state.selected_sheet, med_name)
                    display_image(image_url) # Use the consistent function


                    st.write(f"Your answer: **{user_answer}** {status_icon}")
                    if not is_correct and i in answered_indices: # Show correct only if answered and wrong
                        st.write(f"Correct answer: **{correct_answer}**")
                    elif user_answer == "Not Answered":
                        st.write(f"Correct answer: **{correct_answer}**") # Also show if unanswered

                    st.divider() # Use st.divider for visual separation


    # --- Initial State Message ---
    elif not st.session_state.quiz_loaded:
        st.info("👋 Welcome! Please select a category and sheet from the sidebar, then click 'Load / Restart Quiz'.")
