import streamlit as st
import pandas as pd

# Load CSV file
@st.cache_data
def load_data():
    url = 'https://raw.githubusercontent.com/MidoN37/pharma-quiz-app/main/QUIZ/quiz_data_v2.csv'
    df = pd.read_csv(url)
    return df

df = load_data()

# Extract unique categories
categories = df['Category'].unique()

# Session state to persist quiz data
if 'selected_category' not in st.session_state:
    st.session_state.selected_category = categories[0]
if 'question_index' not in st.session_state:
    st.session_state.question_index = 0
if 'answers' not in st.session_state:
    st.session_state.answers = {}  # question_index: selected_option
if 'show_result' not in st.session_state:
    st.session_state.show_result = False

# Sidebar selection
st.sidebar.title("Quiz Settings")
st.session_state.selected_category = st.sidebar.selectbox("Select Category", categories)

# Filter questions by category
category_df = df[df['Category'] == st.session_state.selected_category].reset_index(drop=True)
total_questions = len(category_df)

# Navigation
def go_to_question(i):
    st.session_state.question_index = i

# Display questions
question = category_df.iloc[st.session_state.question_index]
st.subheader(f"Question {st.session_state.question_index + 1} of {total_questions}")
st.write(question['Question'])

options = [question[f'Option{i}'] for i in range(1, 6)]
correct_option = question['CorrectOption']  # Assume this is Option1, Option2, etc.

# Show radio buttons
selected = st.radio("Select your answer:", options, 
                    index=options.index(st.session_state.answers.get(st.session_state.question_index, options[0]))
                    if st.session_state.question_index in st.session_state.answers else 0,
                    key=f"q{st.session_state.question_index}")

# Save answer
st.session_state.answers[st.session_state.question_index] = selected

# Show result immediately
if selected:
    if selected == question[correct_option]:
        st.success("Correct!")
    else:
        st.error(f"Incorrect! Correct answer is: {question[correct_option]}")

# Navigation buttons
st.markdown("---")
cols = st.columns(total_questions)
for i in range(total_questions):
    btn_color = "green" if i in st.session_state.answers else "gray"
    with cols[i]:
        if st.button(str(i + 1), key=f"nav{i}"):
            go_to_question(i)

# Finish quiz
st.markdown("---")
if st.button("Finish Quiz"):
    st.session_state.show_result = True

if st.session_state.show_result:
    correct = 0
    incorrect = 0
    unanswered = 0

    for i in range(total_questions):
        q = category_df.iloc[i]
        selected = st.session_state.answers.get(i, None)
        if selected is None:
            unanswered += 1
        elif selected == q[q['CorrectOption']]:
            correct += 1
        else:
            incorrect += 1

    st.markdown("## Quiz Results")
    st.write(f"✅ Correct answers: {correct}")
    st.write(f"❌ Incorrect answers: {incorrect}")
    st.write(f"❓ Not answered: {unanswered}")
