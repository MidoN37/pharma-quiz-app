import streamlit as st
import pandas as pd
import random
import unicodedata
import re
from pathlib import Path

# --- Page Config ---
st.set_page_config(layout="wide", page_title="Pharm Quiz")

# --- Project Setup & File Paths ---
APP_DIR = Path(__file__).parent
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
            df = pd.read_csv(path, keep_default_na=False, encoding='utf-8-sig')
        except UnicodeDecodeError:
            df = pd.read_csv(path, keep_default_na=False, encoding='utf-8')
        required = ['Category', 'Sheet', 'MedicationName', 'Question', 'CorrectAnswer']
        if not all(col in df.columns for col in required):
            st.error(f"CSV missing required columns. Need at least: {required}")
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
            return pd.DataFrame()
        df = pd.read_csv(path, encoding='utf-8-sig')
        required = ['category', 'filename', 'raw_url']
        if not all(col in df.columns for col in required):
            st.error(f"Image CSV missing required columns. Required: {required}")
            return pd.DataFrame()
        return df
    except Exception as e:
        st.error(f"Error loading image CSV: {e}")
        return pd.DataFrame()

# --- Main Execution ---
if __name__ == "__main__":
    # Load data
    df_all = load_quiz_data(QUIZ_CSV_PATH)
    df_images = load_image_data(IMAGE_CSV_PATH)
    if df_all is None:
        st.stop()

    # Initialize session state defaults
    categories = sorted(df_all['Category'].unique())
    st.session_state.setdefault('selected_category', categories[0] if categories else None)
    st.session_state.setdefault('selected_sheet', None)
    st.session_state.setdefault('question_index', 0)
    st.session_state.setdefault('answers', {})
    st.session_state.setdefault('show_result', False)
    st.session_state.setdefault('current_quiz_df', pd.DataFrame())
    st.session_state.setdefault('current_quiz_options', {})

    # Sidebar: Category Selection
    st.sidebar.title("Quiz Settings")
    selected_cat = st.sidebar.selectbox(
        "Select Category",
        options=categories,
        index=categories.index(st.session_state.selected_category) if st.session_state.selected_category in categories else 0,
        key='sb_cat'
    )
    if selected_cat != st.session_state.selected_category:
        st.session_state.selected_category = selected_cat
        st.session_state.selected_sheet = None
        st.session_state.current_quiz_df = pd.DataFrame()
        st.session_state.question_index = 0
        st.session_state.answers = {}
        st.session_state.show_result = False
        st.session_state.current_quiz_options = {}
        st.rerun()

    # Sidebar: Sheet Selection
    available_sheets = sorted(
        df_all[df_all['Category'] == st.session_state.selected_category]['Sheet'].unique()
    )
    if len(available_sheets) > 1:
        selected_sheet = st.sidebar.selectbox(
            "Select Sheet",
            options=[""] + available_sheets,
            index=(available_sheets.index(st.session_state.selected_sheet) + 1)
                  if st.session_state.selected_sheet in available_sheets else 0,
            format_func=lambda x: "Select Sheet..." if x == "" else x,
            key='sb_sheet'
        )
        if selected_sheet and selected_sheet != st.session_state.selected_sheet:
            st.session_state.selected_sheet = selected_sheet
            st.session_state.current_quiz_df = pd.DataFrame()
            st.session_state.question_index = 0
            st.session_state.answers = {}
            st.session_state.show_result = False
            st.session_state.current_quiz_options = {}
            st.rerun()
    elif len(available_sheets) == 1:
        st.session_state.selected_sheet = available_sheets[0]
        st.sidebar.write(f"Sheet: **{available_sheets[0]}** (Auto-selected)")

    # Sidebar: Load / Restart Quiz Button
    start_disabled = not (st.session_state.selected_category and st.session_state.selected_sheet)
    if st.sidebar.button("Load / Restart Quiz", disabled=start_disabled):
        filtered = df_all[
            (df_all['Category'] == st.session_state.selected_category) &
            (df_all['Sheet'] == st.session_state.selected_sheet)
        ].copy()
        st.session_state.current_quiz_df = filtered.sample(frac=1).reset_index(drop=True)
        st.session_state.question_index = 0
        st.session_state.answers = {}
        st.session_state.show_result = False
        st.session_state.current_quiz_options = {}
        st.rerun()

    st.markdown("---")

    # --- Quiz Display & Navigation ---
    if not st.session_state.current_quiz_df.empty and not st.session_state.show_result:
        df = st.session_state.current_quiz_df
        total = len(df)
        idx = st.session_state.question_index
        question = df.iloc[idx]

        st.subheader(f"Question {idx + 1} of {total}")
        st.write(question['Question'])

        # Display Image If Available
        if not df_images.empty:
            med = question['MedicationName'].strip().lower()
            cat = st.session_state.selected_category.strip().lower()
            img_row = df_images[
                (df_images['category'].str.strip().str.lower() == cat) &
                (df_images['filename'].apply(lambda f: Path(f).stem.lower()) == med)
            ]
            if not img_row.empty:
                url = img_row.iloc[0]['raw_url']
                if pd.notna(url) and url:
                    st.image(url, caption=f"Image of {question['MedicationName']}", use_column_width=True)

        # Navigation Buttons
        prev_col, next_col = st.columns([1, 1])
        with prev_col:
            if st.button("⬅️ Previous", disabled=(idx <= 0)):
                st.session_state.question_index -= 1
                st.rerun()
        with next_col:
            if st.button("Next ➡️", disabled=(idx >= total - 1)):
                st.session_state.question_index += 1
                st.rerun()

        st.markdown("---")
        st.write("**Go to question:**")
        cols_nav = st.columns(min(total, 10))
        for i in range(total):
            col = cols_nav[i % len(cols_nav)]
            label = str(i + 1)
            if i in st.session_state.answers:
                is_correct = (st.session_state.answers[i] == df.iloc[i]['CorrectAnswer'])
                label += " ✅" if is_correct else " ❌"
            if col.button(label, key=f"nav_{i}"):
                st.session_state.question_index = i
                st.rerun()

        opt_cols = [f'Option_{i}' for i in range(1, 6) if f'Option_{i}' in question and question[f'Option_{i}']]
        opts = [question[col] for col in opt_cols] + [question['CorrectAnswer']]
        opts = list(pd.Series(opts).drop_duplicates().dropna())
        random.shuffle(opts)

        selected = st.radio("Your answer:", opts,
                            index=opts.index(st.session_state.answers.get(idx))
                                  if idx in st.session_state.answers and st.session_state.answers[idx] in opts else 0)
        if st.button("Submit Answer"):
            st.session_state.answers[idx] = selected
            if selected == question['CorrectAnswer']:
                st.success("Correct!")
            else:
                st.error(f"Incorrect! The correct answer is: {question['CorrectAnswer']}")

        st.markdown("---")
        if st.button("Finish Quiz and See Results"):
            st.session_state.show_result = True
            st.rerun()

    elif st.session_state.show_result:
        df = st.session_state.current_quiz_df
        total = len(df)
        correct = sum(1 for i in range(total) if st.session_state.answers.get(i) == df.iloc[i]['CorrectAnswer'])
        incorrect = sum(1 for i in range(total) if i in st.session_state.answers and \
                        st.session_state.answers[i] != df.iloc[i]['CorrectAnswer'])
        unanswered = total - len(st.session_state.answers)

        st.subheader("Quiz Results")
        st.write(f"✅ Correct: {correct}")
        st.write(f"❌ Incorrect: {incorrect}")
        st.write(f"❓ Unanswered: {unanswered}")
        st.metric("Score", f"{correct}/{total}", f"{round(correct/total*100) if total>0 else 0}%")

        if st.button("Start New Quiz"):
            st.session_state.question_index = 0
            st.session_state.answers = {}
            st.session_state.show_result = False
            st.rerun()

        with st.expander("Review Your Answers"):
            for i in range(total):
                q = df.iloc[i]
                sel = st.session_state.answers.get(i, "Not Answered")
                corr_ans = q['CorrectAnswer']
                icon = "✅" if sel == corr_ans else ("❌" if sel != "Not Answered" else "❓")
                st.markdown(f"**Q{i+1}:** {q['Question']}")
                st.write(f"Your answer: {sel} {icon}")
                if sel != corr_ans and sel != "Not Answered":
                    st.write(f"Correct answer: {corr_ans}")
                st.divider()
    else:
        st.info("Please select a category and sheet, then click 'Load / Restart Quiz'.")
