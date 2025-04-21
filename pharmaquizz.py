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

# --- Helper: Determine Override URL ---
def get_override_url(category, sheet, med_name):
    base = (
        "https://raw.githubusercontent.com/MidoN37/pharma-data-viewer/refs/heads/master/assets/images"
    )
    cat = category.strip()
    med = med_name.strip()
    # Antibiotiques overrides by sheet
    if cat == "Antibiotiques":
        if sheet.lower() == "comprime":
            return f"{base}/Antibiotiques/Antiobiotiques%20Comprimes.jpg"
        if sheet.lower() == "sachet":
            return f"{base}/Antibiotiques/Antibiotiques%20Sachet.jpg"
        if sheet.lower() == "sirop":
            return f"{base}/Antibiotiques/Antibiotiques%20Sirop.jpg"
    # Sirop category override
    if cat == "Sirop":
        return f"{base}/Sirops/Sirop%20Tout.jpg"
    # Suppositoires override by first letter
    if cat == "Suppositoires":
        first = med[0].upper() if med else ''
        if 'A' <= first <= 'N':
            return f"{base}/Suppositoires/Suppositoires.jpeg"
        else:
            return f"{base}/Suppositoires/Suppositoires%202.jpeg"
    return None

# --- Main Execution ---
if __name__ == "__main__":
    df_all = load_quiz_data(QUIZ_CSV_PATH)
    df_images = load_image_data(IMAGE_CSV_PATH)
    if df_all is None:
        st.stop()

    categories = sorted(df_all['Category'].unique())
    st.session_state.setdefault('selected_category', categories[0] if categories else None)
    st.session_state.setdefault('selected_sheet', None)
    st.session_state.setdefault('question_index', 0)
    st.session_state.setdefault('answers', {})
    st.session_state.setdefault('show_result', False)
    st.session_state.setdefault('current_quiz_df', pd.DataFrame())
    st.session_state.setdefault('current_quiz_options', {})

    # Sidebar
    st.sidebar.title("Quiz Settings")
    selected_cat = st.sidebar.selectbox(
        "Select Category", options=categories, key='sb_cat'
    )
    if selected_cat != st.session_state.selected_category:
        st.session_state.update({
            'selected_category': selected_cat,
            'selected_sheet': None,
            'current_quiz_df': pd.DataFrame(),
            'question_index': 0,
            'answers': {},
            'show_result': False,
            'current_quiz_options': {}
        })
        st.rerun()

    available_sheets = sorted(df_all[df_all['Category'] == st.session_state.selected_category]['Sheet'].unique())
    if len(available_sheets) > 1:
        selected_sheet = st.sidebar.selectbox(
            "Select Sheet", options=[""] + available_sheets, key='sb_sheet'
        )
        if selected_sheet and selected_sheet != st.session_state.selected_sheet:
            st.session_state.update({
                'selected_sheet': selected_sheet,
                'current_quiz_df': pd.DataFrame(),
                'question_index': 0,
                'answers': {},
                'show_result': False,
                'current_quiz_options': {}
            })
            st.rerun()
    elif available_sheets:
        st.session_state['selected_sheet'] = available_sheets[0]
        st.sidebar.write(f"Sheet: **{available_sheets[0]}** (Auto-selected)")

    start_disabled = not (st.session_state.selected_category and st.session_state.selected_sheet)
    if st.sidebar.button("Load / Restart Quiz", disabled=start_disabled):
        filtered = df_all[
            (df_all['Category'] == st.session_state.selected_category) &
            (df_all['Sheet'] == st.session_state.selected_sheet)
        ]
        st.session_state['current_quiz_df'] = filtered.sample(frac=1).reset_index(drop=True)
        st.session_state.update({'question_index': 0, 'answers': {}, 'show_result': False, 'current_quiz_options': {}})
        st.rerun()

    st.markdown("---")
    # Quiz flow
    if not st.session_state.current_quiz_df.empty and not st.session_state.show_result:
        df = st.session_state.current_quiz_df
        total, idx = len(df), st.session_state.question_index
        q = df.iloc[idx]
        # Order: number, image, text, options, submit, nav, go-to, finish
        st.subheader(f"Question {idx+1} of {total}")
        # Image override or default
        override = get_override_url(st.session_state.selected_category, st.session_state.selected_sheet, q['MedicationName'])
        if override:
            st.markdown(f'<a href="{override}" target="_blank"><img src="{override}" alt="Image" style="max-width:100%"/></a>', unsafe_allow_html=True)
        else:
            # default lookup
            if not df_images.empty:
                med, cat = q['MedicationName'], st.session_state.selected_category
                img_row = df_images[(df_images['category'].str.lower()==cat.lower()) &
                                     (df_images['filename'].str.extract(r'(.+)\.') .iloc[:,0].str.lower()==med.lower())]
                if not img_row.empty:
                    url = img_row.iloc[0]['raw_url']
                    st.markdown(f'<a href="{url}" target="_blank"><img src="{url}" alt="Image" style="max-width:100%"/></a>', unsafe_allow_html=True)
        st.write(q['Question'])
        opts = [q.get(f'Option_{i}') for i in range(1,6) if pd.notna(q.get(f'Option_{i}')) and q.get(f'Option_{i}')]
        opts += [q['CorrectAnswer']]
        opts = list(pd.Series(opts).drop_duplicates())
        random.shuffle(opts)
        sel = st.radio("Your answer:", opts, index=opts.index(st.session_state.answers.get(idx)) if idx in st.session_state.answers else 0)
        if st.button("Submit Answer"):
            st.session_state.answers[idx] = sel
            if sel == q['CorrectAnswer']:
                st.success("Correct!")
            else:
                st.error(f"Incorrect! The correct answer is: {q['CorrectAnswer']}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Previous", disabled=idx<=0):
                st.session_state.question_index -= 1; st.rerun()
        with col2:
            if st.button("Next ➡️", disabled=idx>=total-1):
                st.session_state.question_index += 1; st.rerun()
        st.markdown("---")
        st.write("**Go to question:**")
        cols_nav = st.columns(min(total,10))
        for i in range(total):
            label = str(i+1)
            if i in st.session_state.answers:
                ok = st.session_state.answers[i]==df.iloc[i]['CorrectAnswer']
                label += " ✅" if ok else " ❌"
            if cols_nav[i%len(cols_nav)].button(label, key=f"nav{i}"):
                st.session_state.question_index = i; st.rerun()
        st.markdown("---")
        if st.button("Finish Quiz and See Results"):
            st.session_state.show_result = True; st.rerun()
    elif st.session_state.show_result:
        df = st.session_state.current_quiz_df; total=len(df)
        corr = sum(st.session_state.answers.get(i)==df.iloc[i]['CorrectAnswer'] for i in range(total))
        inc = sum(i in st.session_state.answers and st.session_state.answers[i]!=df.iloc[i]['CorrectAnswer'] for i in range(total))
        unans = total - len(st.session_state.answers)
        st.subheader("Quiz Results")
        st.write(f"✅ Correct: {corr}")
        st.write(f"❌ Incorrect: {inc}")
        st.write(f"❓ Unanswered: {unans}")
        st.metric("Score", f"{corr}/{total}", f"{round(corr/total*100) if total>0 else 0}%")
        if st.button("Start New Quiz"):
            st.session_state.update({'question_index':0,'answers':{},'show_result':False}); st.rerun()
        with st.expander("Review Your Answers"):
            for i in range(total):
                q=df.iloc[i]; sel=st.session_state.answers.get(i,"Not Answered"); ans=q['CorrectAnswer']
                # image in review
                override=get_override_url(st.session_state.selected_category,st.session_state.selected_sheet,q['MedicationName'])
                if override:
                    st.markdown(f'<a href="{override}" target="_blank"><img src="{override}" alt="Image" style="max-width:100%"/></a>',unsafe_allow_html=True)
                elif not df_images.empty:
                    img_row=df_images[(df_images['category'].str.lower()==st.session_state.selected_category.lower()) & (df_images['filename'].str.extract(r'(.+)\.') .iloc[:,0].str.lower()==q['MedicationName'].lower())]
                    if not img_row.empty:
                        st.markdown(f'<a href="{img_row.iloc[0]['raw_url']}" target="_blank"><img src="{img_row.iloc[0]['raw_url']}" alt="Image" style="max-width:100%"/></a>',unsafe_allow_html=True)
                st.markdown(f"**Q{i+1}:** {q['Question']}")
                st.write(f"Your answer: {sel} {'✅' if sel==ans else ('❌' if sel!='Not Answered' else '❓')}" )
                if sel!=ans:
                    st.write(f"Correct answer: {ans}")
                st.divider()
    else:
        st.info("Please select a category and sheet, then click 'Load / Restart Quiz'.")
