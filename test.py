import pandas as pd
import streamlit as st
import duckdb as ddb
from datetime import datetime
import json
import os
import random
import plotly.express as px  # Add this import
from functools import cache

st.set_page_config(layout="wide", page_title="Amateur Radio Study Guide", page_icon="📡")

# Hide just the pages section from sidebar while keeping main navigation
st.markdown("""
<style>
    /* Hide pages from sidebar */
    [data-testid="stSidebarNav"] {display: none;}
    
    /* Keep the main sidebar visible */
    [data-testid="stSidebar"] {display: block;}
</style>
""", unsafe_allow_html=True)

st.title("Basic Amateur Radio Study Guide")

@cache
def read_excel():
    study_guide = pd.read_excel("ham.xlsx", sheet_name="study guide", header=2)
    test = pd.read_excel("ham.xlsx", sheet_name="test")

    sections = study_guide["Section"].unique()
    return study_guide, test, sections


study_guide, test, sections = read_excel()

# st.sidebar.title("Sections")    
# st.write("Select a section to view questions:")
# selected_section = st.sidebar.selectbox("Select a section", sections)

# st.write(study_guide)
# st.write(test)
# Streamlit page selection
page = st.sidebar.radio("Go to", ["Take Test", "Review History", "Study Guide"])

def get_question_pool(test_df):
    # For each section and group, pick one random question
    pool = (
        test_df.groupby(['Section', 'Group'])
        .apply(lambda x: x.sample(1, random_state=None))
        .reset_index(drop=True)
    )
    pool = pool.sample(frac=1, random_state=None).reset_index(drop=True)  # Shuffle
    return pool

def save_test_result(result, email):
    # Normalize email to lowercase
    email = email.lower().strip()
    filename = f"test_results_{email}.json"
    
    # Convert NumPy int64 to native Python int
    result = {
        "timestamp": result["timestamp"],
        "score": int(result["score"]),
        "total": int(result["total"]),
        "answers": [
            {
                "section": str(ans["section"]),
                "group": str(ans["group"]),
                "question": str(ans["question"]),
                "selected": str(ans["selected"]),
                "correct": str(ans["correct"]),
                "is_correct": bool(ans["is_correct"])
            }
            for ans in result["answers"]
        ]
    }
    
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = []
        else:
            data = []
        
        data.append(result)
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Error saving test results: {str(e)}")
        return False

if page == "Take Test":
    col1, col2, col4 = st.columns([5, 1, 3])
    col1.header("Multiple Choice Test")
    if col4.button("Restart Test", key="restart_top"):
        # Clear all session state keys
        keys_to_delete = [k for k in st.session_state.keys() if k.startswith(("shuffled_options_", "submitted_", "answered_"))]
        for k in keys_to_delete + ['question_pool', 'current_q', 'correct', 'incorrect', 'answers']:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

    if 'question_pool' not in st.session_state:
        st.session_state.question_pool = get_question_pool(test)
        st.session_state.current_q = 0
        st.session_state.correct = 0
        st.session_state.incorrect = 0
        st.session_state.answers = []

    pool = st.session_state.question_pool
    q_idx = st.session_state.current_q
    if q_idx < len(pool) and q_idx < 100:
        row = pool.iloc[q_idx]
        
        # Create a key for storing shuffled options
        options_key = f"shuffled_options_{q_idx}"
        
        # Only create and shuffle options if not already in session state
        if options_key not in st.session_state:
            options = [
                row['correct_answer_english'],
                row['incorrect_answer_1_english'],
                row['incorrect_answer_2_english'],
                row['incorrect_answer_3_english'],
            ]
            random.shuffle(options)
            st.session_state[options_key] = options
        
        # Reorganize the question header and metrics
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
        col1.metric("Question", f"{q_idx+1}/{min(100, len(pool))}")
        col2.metric("Correct", st.session_state.correct)
        col3.metric("Incorrect", st.session_state.incorrect)
        
        # Calculate percentage if any questions have been answered
        total_answered = st.session_state.correct + st.session_state.incorrect
        if total_answered > 0:
            percentage = round((st.session_state.correct / total_answered) * 100)
            if percentage >= 80:
                col4.metric("Score", f"{percentage}%", delta="Honours", delta_color="normal")
            elif percentage >= 70:
                col4.metric("Score", f"{percentage}%", delta="Pass", delta_color="normal")
            else:
                col4.metric("Score", f"{percentage}%", delta="Fail", delta_color="inverse")
        else:
            col4.metric("Score", "0%", delta="--", delta_color="off")
        
        st.info(f"Section: {row['Section']} - {row['Section Name']} | Question: {row['question_id']}")
        st.markdown(f"**{row['question_english']}**")
        
        # Replace the radio button and submission section with:
        submitted = st.session_state.get(f"submitted_{q_idx}", False)
        
        # Disable radio button if already submitted
        answer = st.radio(
            "Choose an answer:", 
            st.session_state[options_key], 
            key=q_idx,
            disabled=submitted
        )
        
        col1, col2 = st.columns([2, 5])  # Adjust ratio as needed
        
        # Only show Submit Answer if not yet submitted
        if not submitted:
            if col1.button("Submit Answer", key=f"submit_{q_idx}"):
                st.session_state[f"submitted_{q_idx}"] = True
                is_correct = answer == row['correct_answer_english']
                if is_correct:
                    st.success("✅ Correct!")
                else:
                    st.error(f"❌ Incorrect. The correct answer is: {row['correct_answer_english']}")
                
                if f"answered_{q_idx}" not in st.session_state:
                    st.session_state[f"answered_{q_idx}"] = True
                    st.session_state.answers.append({
                        "section": row['Section'],
                        "group": row['Group'],
                        "question": row['question_english'],
                        "selected": answer,
                        "correct": row['correct_answer_english'],
                        "is_correct": is_correct
                    })
                    if is_correct:
                        st.session_state.correct += 1
                    else:
                        st.session_state.incorrect += 1
                st.rerun()
        else:
            # Show the feedback and Next Question button
            is_correct = answer == row['correct_answer_english']
            if is_correct:
                st.success("✅ Correct!")
            else:
                st.error(f"❌ Incorrect. The correct answer is: {row['correct_answer_english']}")
            
            if col2.button("Next Question", key=f"next_{q_idx}"):
                st.session_state.current_q += 1
                st.rerun()
    else:
        # Show test completion section
        total_questions = min(100, len(pool))
        percentage = round((st.session_state.correct / total_questions) * 100)
        
        # Display results
        st.success(f"Test complete! Score: {st.session_state.correct}/{total_questions} ({percentage}%)")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        email = col1.text_input("Enter your email address to save results:", key="save_email")
        
        if col2.button("Save Test Results"):
            if not email:
                st.error("Please enter an email address to save your results.")
            else:
                result = {
                    "timestamp": datetime.now().isoformat(),
                    "score": st.session_state.correct,
                    "total": total_questions,
                    "answers": st.session_state.answers
                }
                if save_test_result(result, email):
                    st.success("Test results saved successfully!")
        
        if col3.button("Restart Test"):
            # Clear all session state keys
            keys_to_delete = [k for k in st.session_state.keys() if k.startswith(("shuffled_options_", "submitted_", "answered_"))]
            for k in keys_to_delete + ['question_pool', 'current_q', 'correct', 'incorrect', 'answers']:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

elif page == "Review History":
    st.header("Test History")
    
    email = st.text_input("Enter your email address to view your history:", key="view_email")
    
    if email:
        email = email.lower().strip()
        filename = f"test_results_{email}.json"
        
        if os.path.exists(filename):
            with open(filename, "r") as f:
                results = json.load(f)
            
            # Create bar chart of scores over time
            if results:
                
                scores_df = pd.DataFrame([
                    {
                        'timestamp': pd.to_datetime(res['timestamp']),
                        'score': res['score'],
                        'test_number': f"Test {i+1}"
                    } for i, res in enumerate(results)
                ])
                scores_df = scores_df.sort_values('timestamp')
                
                # Create color array based on scores
                scores_df['color'] = scores_df['score'].apply(
                    lambda x: 'lightblue' if x >= 80 
                    else 'lightgreen' if x >= 70 
                    else 'lightcoral'
                )
                
                fig = px.bar(
                    scores_df,
                    x='test_number',
                    y='score',
                    labels={'test_number': 'Test Number', 'score': 'Score (%)'},
                    title='Test Scores Over Time',
                    hover_data={'timestamp': '|%Y-%m-%d %H:%M:%S'},
                    text='score',  # Add this line to show data labels
                    color='color',  # Use our color column
                    color_discrete_map="identity"  # Use the colors as defined
                )
                
                # Add reference lines first (they'll be in the background)
                fig.add_hline(
                    y=70, 
                    line_dash="solid", 
                    line_color="red",
                    annotation_text="Pass (70%)",
                    annotation_position="right",
                    layer="below"  # Add this line to put it behind bars
                )
                fig.add_hline(
                    y=80, 
                    line_dash="dash", 
                    line_color="green",
                    annotation_text="Honours (80%)",
                    annotation_position="right",
                    layer="below"  # Add this line to put it behind bars
                )
                
                # Update layout after adding reference lines
                fig.update_layout(
                    yaxis_range=[0, 100],
                    showlegend=False
                )
                fig.update_traces(
                    textposition='inside',  # Place labels inside the bars
                    texttemplate='%{text}%'  # Add % symbol to labels
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            # Existing code for heatmap and other visualizations...
            # Overall summary stats
            all_answers = [ans for res in results for ans in res['answers']]
            df_all = pd.DataFrame(all_answers)
            
            if not df_all.empty:
                # Add test selection slider
                total_tests = len(results)
                if total_tests > 1:
                    num_tests = st.slider(
                        "Number of recent tests to analyze:",
                        min_value=1,
                        max_value=total_tests,
                        value=total_tests,
                        help="Select how many of your most recent tests to include in the analysis"
                    )
                else:
                    num_tests = 1
                    st.info("Only one test result available.")
                
                # Filter answers to include only the selected number of recent tests
                recent_results = results[-num_tests:]  # Get most recent tests
                
                # Create heatmap of section/group performance
                st.subheader("Section/Group Breakdown - Heatmap")
                # Convert group column to integer for proper sorting
                df_all['group'] = pd.to_numeric(df_all['group'])
                
                pivot_table = df_all.pivot_table(
                    values='is_correct',
                    index='section',
                    columns='group',
                    aggfunc='mean'
                ) * 100
                
                # Sort columns (groups) numerically
                pivot_table = pivot_table.reindex(sorted(pivot_table.columns, key=int), axis=1)
                
                # Create 2D array of text annotations that matches the pivot table data exactly
                annotation_text = []
                for idx in pivot_table.index:
                    row_annotations = []
                    for col in pivot_table.columns:
                        val = pivot_table.loc[idx, col]
                        row_annotations.append(f"{int(val)}" if not pd.isna(val) else "")
                    annotation_text.append(row_annotations)
                
                # Use Streamlit's native heatmap via plotly
                fig = px.imshow(
                    pivot_table,
                    labels=dict(x="Group", y="Section", color="% Correct"),
                    aspect="auto",
                    color_continuous_scale=["red", "orange", "yellow", "green", "blue"],
                    range_color=[0, 100]
                )
                
                # Add text annotations after creating the figure
                fig.update_traces(
                    text=annotation_text,
                    texttemplate="%{text}",
                    textfont={"size": 10},
                    hoverongaps=False,
                    hovertemplate="Section: %{y}<br>" +
                                "Group: %{x}<br>" +
                                "Score: %{z:.1f}%<br><extra></extra>"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Summary statistics table
                st.subheader("Section/Group Performance")
                stats = df_all.groupby(['section', 'group'])['is_correct'].agg([
                    ('correct', 'sum'),
                    ('total', 'count'),
                    ('percent', lambda x: (x.mean() * 100).round(1))
                ]).reset_index()
                stats['Summary'] = stats.apply(
                    lambda x: f"{int(x['correct'])}/{int(x['total'])} ({x['percent']}%)", 
                    axis=1
                )
                st.dataframe(
                    stats[['section', 'group', 'Summary', 'percent']].sort_values('percent', ascending=False),
                    hide_index=True,
                    use_container_width=True
                )
                
                # Individual test selection
                st.subheader("Individual Test Results")
                test_options = [
                    f"Test on {res['timestamp']} - Score: {res['score']}/{res['total']} ({round(res['score']/res['total']*100)}%)"
                    for res in results
                ]
                selected_test = st.selectbox("Select a test to review:", test_options)
                
                # Show details of selected test
                test_idx = test_options.index(selected_test)
                res = results[::-1][test_idx]  # Get selected test
                
                # Show test details in a clean table
                df = pd.DataFrame(res['answers'])
                df['Result'] = df['is_correct'].map({True: '✅ Correct', False: '❌ Incorrect'})
                st.dataframe(
                    df[["section", "group", "question", "Result", "selected", "correct"]],
                    hide_index=True,
                    use_container_width=True
                )
        else:
            st.info(f"No test history found for {email}")
    else:
        st.info("Please enter your email address to view your test history.")

elif page == "Study Guide":
    st.header("Study Guide")
    
    with st.expander("Browse Questions", expanded=True):
        section = st.selectbox("Select Section", test["Section"].unique(), key="browse_section")
        groups = test[test["Section"] == section]["Group"].unique()
        group = st.selectbox("Select Group (optional)", ["All"] + list(groups), key="browse_group")
        
        # Filter questions based on selection
        if group == "All":
            questions = test[test["Section"] == section]
        else:
            questions = test[(test["Section"] == section) & (test["Group"] == group)]
        
        # Display questions as cards in rows of 3
        for i in range(0, len(questions), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(questions):
                    row = questions.iloc[i + j]
                    with cols[j]:
                        st.markdown("---")
                        st.markdown(f"**Question {row['question_id']}**")
                        st.markdown(f"{row['question_english']}")
                        st.markdown(f"**Answer:** {row['correct_answer_english']}")
                        st.markdown("---")
    
    with st.expander("Areas Needing Practice", expanded=True):
        # Load test history
        filename = "test_results.json"
        if os.path.exists(filename):
            with open(filename, "r") as f:
                results = json.load(f)
            
            # Calculate performance stats
            all_answers = [ans for res in results for ans in res['answers']]
            if all_answers:
                df_all = pd.DataFrame(all_answers)
                stats = df_all.groupby(['section', 'group'])['is_correct'].agg([
                    ('correct', 'sum'),
                    ('total', 'count'),
                    ('percent', lambda x: (x.mean() * 100).round(1))
                ]).reset_index()
                
                # Add threshold selector
                threshold = st.select_slider(
                    "Show topics below score threshold:",
                    options=[50, 70, 80],
                    value=70
                )
                
                # Filter areas needing practice
                needs_practice = stats[stats['percent'] < threshold].sort_values(['section', 'group'])
                if not needs_practice.empty:
                    st.warning(f"Topics scoring below {threshold}%!")
                    
                    # Create section dropdown
                    practice_sections = needs_practice['section'].unique()
                    selected_practice_section = st.selectbox(
                        "Select Section to Practice:", 
                        practice_sections,
                        key="practice_section"
                    )
                    
                    # Filter groups for selected section
                    section_groups = needs_practice[
                        needs_practice['section'] == selected_practice_section
                    ]['group'].unique()
                    
                    # Create group dropdown
                    selected_practice_group = st.selectbox(
                        "Select Group to Practice:",
                        section_groups,
                        key="practice_group"
                    )
                    
                    # Show performance for selected section/group
                    group_stats = needs_practice[
                        (needs_practice['section'] == selected_practice_section) &
                        (needs_practice['group'] == selected_practice_group)
                    ].iloc[0]
                    
                    st.info(
                        f"Current Performance for {selected_practice_section} - Group {selected_practice_group}: "
                        f"{int(group_stats['correct'])}/{int(group_stats['total'])} "
                        f"({group_stats['percent']}%)"
                    )
                    
                    # Get and display questions for selected section/group
                    practice_questions = test[
                        (test['Section'] == selected_practice_section) &
                        (test['Group'] == selected_practice_group)
                    ].copy()  # Make a copy to avoid SettingWithCopyWarning
                    
                    if len(practice_questions) > 0:
                        # Calculate performance for each question if it exists in history
                        question_stats = df_all[
                            (df_all['section'] == selected_practice_section) &
                            (df_all['group'] == selected_practice_group)
                        ].groupby('question').agg({
                            'is_correct': ['count', 'mean']
                        }).reset_index()
                        question_stats.columns = ['question', 'attempts', 'success_rate']
                        
                        st.markdown("### Practice Questions")
                        for i in range(0, len(practice_questions), 3):
                            cols = st.columns(3)
                            for j in range(3):
                                if i + j < len(practice_questions):
                                    row = practice_questions.iloc(i + j)
                                    with cols[j]:
                                        # Get stats for this question if available
                                        q_stats = question_stats[
                                            question_stats['question'] == row['question_english']
                                        ]
                                        
                                        performance = ""
                                        if not q_stats.empty:
                                            correct_rate = q_stats['success_rate'].iloc[0] * 100
                                            attempts = int(q_stats['attempts'].iloc[0])
                                            performance = f"\n\n*Performance: {correct_rate:.0f}% ({attempts} attempts)*"
                                        
                                        st.markdown(f"""
                                        ---
                                        **Question {row['question_id']}**
                                        
                                        {row['question_english']}
                                        
                                        **Answer:** {row['correct_answer_english']}{performance}
                                        ---
                                        """)
                    else:
                        st.warning("No questions found for this section and group combination")
                else:
                    st.success(f"No topics below {threshold}%!")
            else:
                st.info("No test history available for analysis.")
        else:
            st.info("No test history found. Take some tests to see performance analysis.")
