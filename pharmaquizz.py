import streamlit as st
import pandas as pd
import random
import unicodedata
import re # Keep if used elsewhere
from pathlib import Path

# --- Page Config ---
st.set_page_config(layout="wide", page_title="Pharm Quiz")

# --- Project Setup & File Paths ---
try:
    APP_DIR = Path(__file__).parent
except NameError:
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
        # Add optional columns if they don't exist
        for i in range(1, 6):
            col_name = f'Option_{i}'
            if col_name not in df.columns:
                df[col_name] = None # Or pd.NA
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
            return pd.DataFrame(columns=['category', 'filename', 'raw_url'])
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
        # Pre-normalize columns for faster lookup during quiz
        df['_norm_cat'] = df['category'].astype(str).apply(normalize_text)
        df['_norm_filename'] = df['filename'].astype(str).str.extract(r'([^/]+)\.[^.]*$', expand=False).fillna('').apply(normalize_text)
        return df
    except Exception as e:
        st.error(f"Error loading image CSV: {e}")
        return pd.DataFrame(columns=['category', 'filename', 'raw_url'])

# --- Helper: Determine Override URL ---
def get_override_url(category, sheet, med_name):
    base = (
        "https://raw.githubusercontent.com/MidoN37/pharma-data-viewer/refs/heads/master/assets/images"
    )
    cat = str(category).strip() if category else ""
    med = str(med_name).strip() if med_name else ""
    sheet_lower = str(sheet).strip().lower() if sheet else ""

    if cat == "Antibiotiques":
        if sheet_lower == "comprime": return f"{base}/Antibiotiques/Antiobiotiques%20Comprimes.jpg"
        if sheet_lower == "sachet": return f"{base}/Antibiotiques/Antibiotiques%20Sachet.jpg"
        if sheet_lower == "sirop": return f"{base}/Antibiotiques/Antibiotiques%20Sirop.jpg"
    if cat == "Sirop": return f"{base}/Sirops/Sirop%20Tout.jpg"
    if cat == "Suppositoires":
        first = med[0].upper() if med else ''
        if 'A' <= first <= 'N': return f"{base}/Suppositoires/Suppositoires.jpeg"
        elif first: return f"{base}/Suppositoires/Suppositoires%202.jpeg"
    return None

# --- Normalize function for matching ---
def normalize_text(text):
    if not isinstance(text, str): return ""
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    return text.lower().strip()

# --- Get Image URL (handles overrides and lookups) ---
def get_image_url(df_images, category, sheet, med_name):
    override = get_override_url(category, sheet, med_name)
    if override: return override
    if df_images.empty or not med_name or not category: return None

    norm_med = normalize_text(med_name)
    norm_cat = normalize_text(category)

    # Use pre-normalized columns for matching
    img_row = df_images[
        (df_images['_norm_cat'] == norm_cat) &
        (df_images['_norm_filename'] == norm_med)
    ]

    if not img_row.empty:
        return img_row.iloc[0]['raw_url']
    return None

# --- Display Image ---
def display_image(url, container):
    """Displays the image from a URL inside a specific container."""
    if url:
        container.markdown(f'<a href="{url}" target="_blank"><img src="{url}" alt="Medication Image" style="max-width:100%; max-height: 450px; object-fit: contain; margin-top: 20px;"/></a>', unsafe_allow_html=True)
    # else:
    #     container.write("_(No image available)_")

# --- Main Execution ---
if __name__ == "__main__":
    df_all = load_quiz_data(QUIZ_CSV_PATH)
    df_images = load_image_data(IMAGE_CSV_PATH)

    if df_all is None:
        st.error("Quiz data could not be loaded. Stopping application.")
        st.stop()

    # Initialize session state keys reliably
    default_values = {
        'selected_category': None, 'selected_sheet': None, 'question_index': 0,
        'answers': {}, 'show_result': False, 'current_quiz_df': pd.DataFrame(),
        'current_quiz_options': {}, 'quiz_loaded': False
    }
    for key, default_value in default_values.items():
        st.session_state.setdefault(key, default_value)

    # --- Sidebar ---
    st.sidebar.title("Quiz Settings")
    categories = sorted(df_all['Category'].unique()) if not df_all.empty else []
    current_selection_cat = st.session_state.selected_category
    if current_selection_cat not in categories and categories:
        current_selection_cat = categories[0]
    selected_cat = st.sidebar.selectbox(
        "Select Category", options=categories,
        index=categories.index(current_selection_cat) if current_selection_cat in categories else 0,
        key='sb_cat'
    )
    if selected_cat != st.session_state.selected_category:
        st.session_state.selected_category = selected_cat
        st.session_state.update({
            'selected_sheet': None, 'current_quiz_df': pd.DataFrame(), 'question_index': 0,
            'answers': {}, 'show_result': False, 'current_quiz_options': {}, 'quiz_loaded': False
        })
        st.rerun()

    if st.session_state.selected_category:
        available_sheets = sorted(df_all[df_all['Category'] == st.session_state.selected_category]['Sheet'].unique())
        if len(available_sheets) == 1 and st.session_state.selected_sheet != available_sheets[0]:
             st.session_state.selected_sheet = available_sheets[0]
             st.session_state.update({
                 'current_quiz_df': pd.DataFrame(), 'question_index': 0, 'answers': {},
                 'show_result': False, 'current_quiz_options': {}, 'quiz_loaded': False
             })
             # No rerun needed here usually

        if len(available_sheets) > 1:
            sheet_options = ["-- Select Sheet --"] + available_sheets
            current_selection_sheet = st.session_state.selected_sheet
            try:
                current_index_sheet = sheet_options.index(current_selection_sheet) if current_selection_sheet else 0
            except ValueError:
                current_index_sheet = 0
            selected_sheet_option = st.sidebar.selectbox(
                "Select Sheet", options=sheet_options, index=current_index_sheet, key='sb_sheet'
            )
            new_selected_sheet = selected_sheet_option if selected_sheet_option != "-- Select Sheet --" else None
            if new_selected_sheet != st.session_state.selected_sheet:
                st.session_state.selected_sheet = new_selected_sheet
                st.session_state.update({
                    'current_quiz_df': pd.DataFrame(), 'question_index': 0, 'answers': {},
                    'show_result': False, 'current_quiz_options': {}, 'quiz_loaded': False
                })
                st.rerun()
        elif len(available_sheets) == 1:
            st.sidebar.write(f"Sheet: **{available_sheets[0]}** (Auto-selected)")
        else:
            st.sidebar.warning("No sheets found for this category.")
            st.session_state.selected_sheet = None

    start_disabled = not (st.session_state.selected_category and st.session_state.selected_sheet)
    if st.sidebar.button("Load / Restart Quiz", disabled=start_disabled, type="primary"):
        if st.session_state.selected_category and st.session_state.selected_sheet:
            filtered = df_all[
                (df_all['Category'] == st.session_state.selected_category) &
                (df_all['Sheet'] == st.session_state.selected_sheet)
            ].copy()
            if not filtered.empty:
                st.session_state.current_quiz_df = filtered.sample(frac=1).reset_index(drop=True)
                st.session_state.update({
                    'question_index': 0, 'answers': {}, 'show_result': False,
                    'current_quiz_options': {}, 'quiz_loaded': True
                })
                st.rerun()
            else:
                st.sidebar.error("No questions found for this selection.")
                st.session_state.quiz_loaded = False
        else:
             st.sidebar.error("Please select both category and sheet.")
             st.session_state.quiz_loaded = False
    st.sidebar.markdown("---")

    # --- Main Quiz Area ---
    st.title("💊 Pharm Quiz App")
    st.markdown("---")

    if st.session_state.quiz_loaded and not st.session_state.show_result:
        df = st.session_state.current_quiz_df
        total_questions = len(df)
        current_q_index = st.session_state.question_index

        if 0 <= current_q_index < total_questions:
            question_data = df.iloc[current_q_index]
            med_name = question_data.get('MedicationName', '') # Get med_name early

            # --- Determine Image URL FIRST ---
            image_url = get_image_url(df_images, st.session_state.selected_category, st.session_state.selected_sheet, med_name)

            # --- Create Columns for Layout ---
            left_col, right_col = st.columns([2, 1]) # Content on left (wider), Image on right

            # --- Right Column: Image ---
            with right_col:
                display_image(image_url, st) # Pass st (or right_col) to display_image

            # --- Left Column: Question Content ---
            with left_col:
                # Display Question Number
                st.subheader(f"Question {current_q_index + 1} of {total_questions}")

                # Display Question Text (Removed Category/Sheet/Medication explicit labels)
                st.markdown(f"**Question:**")
                st.markdown(f"#### {question_data['Question']}") # Make question slightly larger


                # --- Generate and Display Options (Logic remains the same) ---
                if current_q_index not in st.session_state.current_quiz_options:
                    correct_answer = question_data['CorrectAnswer']
                    # Ensure options columns exist before accessing
                    options = []
                    for i in range(1, 6):
                        col_name = f'Option_{i}'
                        if col_name in question_data and pd.notna(question_data[col_name]) and question_data[col_name]:
                             options.append(question_data[col_name])

                    all_options = list(pd.Series(options + [correct_answer]).drop_duplicates().dropna())
                    random.shuffle(all_options)
                    st.session_state.current_quiz_options[current_q_index] = all_options
                else:
                    all_options = st.session_state.current_quiz_options[current_q_index]

                # --- Display Radio Buttons ---
                previous_answer = st.session_state.answers.get(current_q_index)
                default_index = None
                if previous_answer is not None:
                    try:
                        default_index = all_options.index(previous_answer)
                    except ValueError:
                        default_index = None # Answer not in current options (safety)

                user_choice = st.radio(
                    "Select your answer:",
                    options=all_options,
                    index=default_index,
                    key=f"q_{current_q_index}_options"
                )

                # --- Submit Button and Feedback Area ---
                submit_pressed = st.button("Submit Answer", key=f"submit_{current_q_index}")

                # Display feedback below the submit button IN the left column
                if current_q_index in st.session_state.answers:
                    stored_answer = st.session_state.answers[current_q_index]
                    correct_answer = question_data['CorrectAnswer']
                    if stored_answer == correct_answer:
                        st.success("Correct! ✅")
                    else:
                        st.error(f"Incorrect! The correct answer is: **{correct_answer}** ❌")

                if submit_pressed:
                    st.session_state.answers[current_q_index] = user_choice
                    st.rerun() # Rerun to show feedback and update nav icons

            # --- Navigation and Finish Buttons (BELOW the columns) ---
            st.markdown("---") # Separator below columns
            nav_col1, nav_col2 = st.columns(2)
            with nav_col1:
                if st.button("⬅️ Previous", disabled=current_q_index <= 0, use_container_width=True):
                    st.session_state.question_index -= 1
                    st.rerun()
            with nav_col2:
                if st.button("Next ➡️", disabled=current_q_index >= total_questions - 1, use_container_width=True):
                    st.session_state.question_index += 1
                    st.rerun()

            st.markdown("---")
            st.write("**Go to question:**")
            num_nav_cols = min(total_questions, 10)
            nav_cols = st.columns(num_nav_cols)
            for i in range(total_questions):
                nav_col = nav_cols[i % num_nav_cols]
                q_label = str(i + 1)
                q_state_icon = ""
                if i in st.session_state.answers:
                    is_correct = st.session_state.answers[i] == df.iloc[i]['CorrectAnswer']
                    q_state_icon = " ✅" if is_correct else " ❌"
                btn_type = "primary" if i == current_q_index else "secondary"
                if nav_col.button(f"{q_label}{q_state_icon}", key=f"nav_{i}", type=btn_type, use_container_width=True):
                    st.session_state.question_index = i
                    st.rerun()

            st.markdown("---")
            if st.button("🏁 Finish Quiz and See Results", use_container_width=True):
                st.session_state.show_result = True
                st.rerun()

        else:
            st.warning("Invalid question index. Restarting quiz selection.")
            st.session_state.question_index = 0
            st.session_state.quiz_loaded = False
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
                if answers[i] == df.iloc[i]['CorrectAnswer']: correct_count += 1
                else: incorrect_count += 1
        unanswered_count = total - len(answered_indices)

        res_col1, res_col2, res_col3, res_col4 = st.columns(4)
        res_col1.metric("✅ Correct", correct_count)
        res_col2.metric("❌ Incorrect", incorrect_count)
        res_col3.metric("❓ Unanswered", unanswered_count)
        score_percent = (correct_count / total * 100) if total > 0 else 0
        res_col4.metric("🏆 Score", f"{correct_count}/{total}", f"{score_percent:.1f}%")

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("🚀 Start New Quiz (Same Settings)", use_container_width=True):
                st.session_state.current_quiz_df = df.sample(frac=1).reset_index(drop=True) # Reshuffle
                st.session_state.update({
                    'question_index': 0, 'answers': {}, 'show_result': False,
                    'current_quiz_options': {}, 'quiz_loaded': True
                })
                st.rerun()
        with btn_col2:
            if st.button("⚙️ Change Settings and Start New Quiz", use_container_width=True):
                st.session_state.update({
                    'question_index': 0, 'answers': {}, 'show_result': False,
                    'current_quiz_df': pd.DataFrame(), 'current_quiz_options': {}, 'quiz_loaded': False
                })
                st.rerun()

        # --- Review Answers Expander ---
        with st.expander("🧐 Review Your Answers", expanded=False):
            if total == 0: st.write("No questions were loaded for review.")
            else:
                for i in range(total):
                    question_data = df.iloc[i]
                    user_answer = answers.get(i, "Not Answered")
                    correct_answer = question_data['CorrectAnswer']
                    is_correct = user_answer == correct_answer
                    status_icon = ""
                    if i in answered_indices: status_icon = "✅" if is_correct else "❌"
                    else: status_icon = "❓"

                    # --- Layout for Review Items (Optional: could also use columns here) ---
                    st.markdown(f"**Question {i+1}:** {question_data['Question']}")

                    # Display Image in review
                    med_name = question_data.get('MedicationName', '')
                    # Need a container (like st itself) to pass to display_image
                    review_img_container = st.container() # Create a container for the image
                    image_url = get_image_url(df_images, st.session_state.selected_category, st.session_state.selected_sheet, med_name)
                    display_image(image_url, review_img_container) # Display image inside the container

                    st.write(f"Your answer: **{user_answer}** {status_icon}")
                    if not is_correct and i in answered_indices:
                        st.write(f"Correct answer: **{correct_answer}**")
                    elif user_answer == "Not Answered":
                        st.write(f"Correct answer: **{correct_answer}**")
                    st.divider()

    # --- Initial State Message ---
    elif not st.session_state.quiz_loaded:
        st.info("👋 Welcome! Please select a category and sheet from the sidebar, then click 'Load / Restart Quiz'.")
