import pandas as pd
import streamlit as st
import duckdb as ddb
from datetime import datetime
import json
import os
import random
import plotly.express as px  # Add this import
from functools import cache
from storage import StorageManager
from dotenv import load_dotenv

load_dotenv()



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
page = st.sidebar.radio("Go to", ["Home", "Take Test", "Review History", "Study Guide"])

def get_question_pool(test_df):
    # For each section and group, pick one random question
    pool = (
        test_df.groupby(['Section', 'Group'])
        .apply(lambda x: x.sample(1, random_state=None))
        .reset_index(drop=True)
    )
    pool = pool.sample(frac=1, random_state=None).reset_index(drop=True)  # Shuffle
    return pool

# Initialize storage manager
storage_mgr = StorageManager(os.getenv('AZURE_STORAGE_CONNECTION_STRING'))

print(dir(storage_mgr))
print(storage_mgr.list_users())

def save_test_result(result, email):
    try:
        def convert_to_serializable(obj):
            if isinstance(obj, (datetime, pd.Timestamp)):
                return obj.isoformat()
            elif hasattr(obj, 'item'):  # numpy types
                return obj.item()
            elif pd.isna(obj):  # pandas NA/NaN
                return None
            elif hasattr(obj, '__dict__'):  # custom objects
                return str(obj)
            return obj

        # Deep copy and convert the result dictionary
        processed_result = {
            "timestamp": convert_to_serializable(result["timestamp"]),
            "score": int(result["score"]),
            "total": int(result["total"]),
            "answers": []
        }

        # Process each answer
        for answer in result["answers"]:
            processed_answer = {}
            for key, value in answer.items():
                processed_answer[key] = convert_to_serializable(value)
            processed_result["answers"].append(processed_answer)

        # Save the processed result
        storage_mgr.save_test_result(email.lower().strip(), processed_result)
        return True
    except Exception as e:
        st.error(f"Error saving results: {str(e)}")
        return False

if page == "Home":
    st.markdown("""
## Welcome to the Amateur Radio Study Guide!

This application helps you prepare for your Basic Amateur Radio License exam in Canada. Here's how to use each section:

### 📝 Take Test
- Simulates the actual exam environment
- 100 questions selected from the question bank
- Questions are randomly selected from all sections/groups
- Immediate feedback on your answers
- Save your results to track progress over time
- Pass mark is 70%, Honours at 80%

### 📊 Review History
- View your test history and progress
- See your performance trends over time
- Analyze your strengths and weaknesses by section
- Track which questions you've seen and which you haven't
- Focus on areas that need improvement

### 📚 Study Guide (under construction)
- Browse all questions by section and group
- Review specific topics
- See correct answers for all questions
- Practice areas where you need improvement

### 📈 Features
- Performance tracking across all attempts
- Detailed analytics of your progress
- Section-by-section breakdown
- Question coverage analysis
- Visual heatmap of your performance

### 🎯 Getting Started
1. Take a practice test to assess your current knowledge
2. Review your results to identify weak areas
3. Use the Study Guide to focus on those areas
4. Track your progress in Review History
5. Repeat until you consistently score above 70%

### About Basic Amateur Radio License
The Basic qualification is the entry-level amateur radio operator certificate in Canada. 
You need to score at least 70% to pass, and 80% or higher grants you additional operating privileges (Honours).

Good luck with your studies! 📡
                
73,

VA3 ECC

Jonathan
""")

    # Add contact/about section at the bottom
    st.markdown("---")
    with st.expander("About This Project"):
        st.markdown("""
        This study tool was created to help amateur radio enthusiasts prepare for their Basic qualification exam. 
        It uses the official Industry Canada question bank and simulates the actual exam environment.
        
        **Features:**
        - Full question bank coverage
        - Realistic exam simulation
        - Progress tracking
        - Performance analytics
        - Focused study recommendations
        
        For more information about amateur radio licensing in Canada, visit the 
        [Innovation, Science and Economic Development Canada website](https://www.ic.gc.ca/eic/site/025.nsf/eng/home).
        
        Created by VA3 ECC
                    
        Created and used to pass with honours on 2025/06/03
        """)
elif page == "Take Test":
    col1, col2, col4 = st.columns([5, 1, 3])
    col1.header("Multiple Choice Test")
    
    # Initialize session state if needed
    if 'question_pool' not in st.session_state:
        st.session_state.question_pool = get_question_pool(test)  # Default to random test
        st.session_state.current_q = 0
        st.session_state.correct = 0
        st.session_state.incorrect = 0
        st.session_state.answers = []
    
    # Add personalized test options
    with st.expander("Personalized Test Options", expanded=False):
        email_for_test = st.text_input("Enter your email for a personalized test:", key="personalized_test_email")
        if email_for_test:
            test_type = st.radio(
                "Choose your test type:",
                ["New Questions Only", "Practice Weak Areas", "Standard Random Test"],
                help="""
                - New Questions Only: Questions you haven't seen before
                - Practice Weak Areas: Questions you've scored < 70% on
                - Standard Random Test: Random selection from all questions
                """
            )
            
            # Add Start Test button
            if st.button("Start Personalized Test", key="start_personalized"):
                st.session_state.current_q = 0
                st.session_state.correct = 0
                st.session_state.incorrect = 0
                st.session_state.answers = []
                
                if test_type != "Standard Random Test":
                    try:
                        # Get user's history
                        results = storage_mgr.get_test_results(email_for_test.lower().strip())
                        if results:
                            all_answers = [ans for res in results for ans in res['answers']]
                            df_all = pd.DataFrame(all_answers) if all_answers else pd.DataFrame()
                            
                            if test_type == "New Questions Only":
                                # Get questions user hasn't seen
                                answered_questions = set(df_all['question'].unique()) if not df_all.empty else set()
                                available_questions = test[~test['question_english'].isin(answered_questions)].copy()
                                
                                if len(available_questions) >= 100:
                                    st.success(f"Found {len(available_questions)} unasked questions available!")
                                    st.session_state.question_pool = get_question_pool(available_questions)
                                else:
                                    st.warning(f"Only {len(available_questions)} unasked questions available. Adding some random questions to complete the test.")
                                    # Add random questions to make up the difference
                                    additional_questions = test.sample(n=100-len(available_questions))
                                    combined_questions = pd.concat([available_questions, additional_questions])
                                    st.session_state.question_pool = get_question_pool(combined_questions)
                            
                            elif test_type == "Practice Weak Areas":
                                if not df_all.empty:
                                    # Calculate performance by question
                                    question_stats = df_all.groupby('question')['is_correct'].agg(['mean', 'count']).reset_index()
                                    weak_questions = question_stats[question_stats['mean'] < 0.7]['question']
                                    
                                    # Get questions user performed poorly on
                                    weak_pool = test[test['question_english'].isin(weak_questions)].copy()
                                    
                                    if len(weak_pool) >= 50:
                                        st.success(f"Found {len(weak_pool)} questions you can improve on!")
                                        st.session_state.question_pool = get_question_pool(weak_pool)
                                    else:
                                        st.warning(f"Only {len(weak_pool)} questions found for practice. Adding some random questions to complete the test.")
                                        # Add random questions to make up the difference
                                        additional_questions = test.sample(n=100-len(weak_pool))
                                        combined_questions = pd.concat([weak_pool, additional_questions])
                                        st.session_state.question_pool = get_question_pool(combined_questions)
                                else:
                                    st.info("No test history found. Using standard random test.")
                                    st.session_state.question_pool = get_question_pool(test)
                        else:
                            if test_type == "New Questions Only":
                                st.success("No test history found - all questions will be new!")
                            else:
                                st.info("No test history found. Using standard random test.")
                            st.session_state.question_pool = get_question_pool(test)
                    except Exception as e:
                        st.error(f"Error loading test history: {str(e)}")
                        st.session_state.question_pool = get_question_pool(test)
                else:
                    st.session_state.question_pool = get_question_pool(test)
                st.rerun()
    
    # Add Restart button for the main test
    if col4.button("Restart Test", key="restart_top"):
        for k in st.session_state.keys():
            if k.startswith(("shuffled_options_", "submitted_", "answered_")):
                del st.session_state[k]
        st.session_state.question_pool = get_question_pool(test)  # Reset to random test
        st.session_state.current_q = 0
        st.session_state.correct = 0
        st.session_state.incorrect = 0
        st.session_state.answers = []
        st.rerun()

    # Show test interface (existing code)
    if st.session_state.question_pool is not None:
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
            
            st.info(f"**{row['Section Name']} - {row['Section']}** | Question: {row['question_id']}")
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
    st.header("Review History")
    
    email = st.text_input("Enter your email address to view your history:", key="view_email")
    
    if email:
        try:
            results = storage_mgr.get_test_results(email.lower().strip())
            if not results:
                st.info(f"No test history found for {email}")
            else:
                # Add summary metrics at the top
                if results:
                    col1, col2, col3, col4, col5 = st.columns(5)
                    col1.metric("Total Tests", len(results))
                    col2.metric("Average Score", f"{sum(r['score'] for r in results)/len(results):.1f}%")
                    col3.metric("Best Score", f"{max(r['score'] for r in results)}%")
                    col4.metric("Latest Score", f"{results[-1]['score']}%")
                    # Add Last 5 Average
                    last_5_avg = sum(r['score'] for r in results[-5:])/min(len(results), 5)
                    col5.metric("Last 5 Average", f"{last_5_avg:.1f}%")
                
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
                        line_color="green",
                        annotation_text="Pass (70%)",
                        annotation_position="right",
                        layer="below"  # Add this line to put it behind bars
                    )
                    fig.add_hline(
                        y=80, 
                        line_dash="solid", 
                        line_color="blue",
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
                    st.subheader("Section/Group Breakdown - Heatmap")
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
                    
                    # Convert group column to integer for proper sorting
                    df_all['group'] = pd.to_numeric(df_all['group'])
                    
                    recent_answers = [ans for res in recent_results for ans in res['answers']]
                    df_recent = pd.DataFrame(recent_answers)
                    # st.write(recent_answers)

                    pivot_table = df_recent.pivot_table(
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
                                    "Score: %{z:.1f}%<br>" +
                                    "<extra>Click to see questions</extra>"
                    )
                    fig.update_layout(dragmode="select")
                    
                    # Display the plot and capture clicks
                    clicked = st.plotly_chart(
                        fig, 
                        use_container_width=True,
                        # on_select="click",  # Capture click events
                        key="heatmap",
                        selection_mode=('box'),
                        
                        on_select="rerun"
                        
                    )
                    st.markdown("_Draw a rectangle above to see questions._ </br> _Top left of the rectangle will be the questions displayed below_", 
                                unsafe_allow_html=True)
                    # click_data = st.session_state.get("plotly_clickData")
                    # st.write(clicked)
                    if clicked is not None and "box" in clicked.get("selection").keys():  # Check if there was a valid click event
                        # st.write("Tru fasd")
                        try:
                            clicked_section = 1 + round(clicked.get("selection")["box"][0]["y"][0],0)
                            clicked_group =  round(clicked.get("selection")["box"][0]["x"][0],0)
                            
                            clicked_group = int(clicked_group) if int(clicked_group) > 0 else 1
                            clicked_group = f"{clicked_group}"
                            clicked_section = f"B-00{int(clicked_section)}"
                            

                            questions = test[
                                    (test["Section"] == str(clicked_section)) & 
                                    (test["Group"] == int(clicked_group))
                                ]
                            ex = st.container(border=False)
                            
                            with ex.expander(f"Show Questions for Section {clicked_section}, Group {clicked_group} - {len(questions)} Questions", expanded=False):
                                for _, q in questions.iterrows():
                                        st.markdown(f"""
                                        ---
                                        **Question Id {q['question_id']}**  
                                        **Question:** {q['question_english']}  
                                        **Answer:** {q['correct_answer_english']}
                                        """)
                        except:
                            pass
                                   
                    
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

                    # Question Coverage Analysis
                    st.subheader("Question Coverage Analysis")

                    # Get all unique questions answered by user
                    answered_questions = df_all[['section', 'group', 'question']].drop_duplicates()

                    # Create a dataframe of all possible questions from test bank
                    all_questions = test[['Section', 'Group', 'question_id', 'question_english']].copy()
                    all_questions.columns = ['section', 'group', 'question_id', 'question']

                    # Group by section and group to get totals
                    question_coverage = all_questions.groupby(['section', 'group']).agg({
                        'question': 'count'
                    }).reset_index()
                    question_coverage.columns = ['section', 'group', 'total_questions']

                    # Get count of answered questions by section and group
                    answered_counts = answered_questions.groupby(['section', 'group']).size().reset_index()
                    answered_counts.columns = ['section', 'group', 'answered_questions']

                    # Merge the counts
                    coverage_stats = question_coverage.merge(
                        answered_counts, 
                        on=['section', 'group'], 
                        how='left'
                    ).fillna(0)

                    coverage_stats['answered_questions'] = coverage_stats['answered_questions'].astype(int)
                    coverage_stats['remaining_questions'] = coverage_stats['total_questions'] - coverage_stats['answered_questions']
                    coverage_stats['coverage_percent'] = (coverage_stats['answered_questions'] / coverage_stats['total_questions'] * 100).round(1)

                    # Calculate overall statistics
                    total_questions_overall = coverage_stats['total_questions'].sum()
                    total_answered_overall = coverage_stats['answered_questions'].sum()
                    total_unanswered = total_questions_overall - total_answered_overall
                    overall_coverage = (total_answered_overall / total_questions_overall * 100).round(1)

                    # Display overall summary
                    st.info(
                        f"Overall Question Coverage: "
                        f"{total_answered_overall:,} of {total_questions_overall:,} questions answered "
                        f"({overall_coverage}% complete). "
                        f"**{total_unanswered:,} questions remaining.**"
                    )

                    # Display coverage statistics (existing code)
                    st.dataframe(
                        coverage_stats[[
                            'section', 'group', 'total_questions', 'answered_questions', 
                            'remaining_questions', 'coverage_percent'
                        ]].sort_values(['section', 'group']),
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            'section': 'Section',
                            'group': 'Group',
                            'total_questions': 'Total Questions',
                            'answered_questions': 'Questions Answered',
                            'remaining_questions': 'Questions Remaining',
                            'coverage_percent': st.column_config.NumberColumn(
                                'Coverage %',
                                format="%.1f%%"
                            )
                        }
                    )

                    # Add section to show unanswered questions
                    with st.expander("View Unanswered Questions", expanded=False):
                        # Get list of answered question texts
                        answered_texts = set(answered_questions['question'].unique())
                        
                        # Filter for unanswered questions - include full question details
                        unanswered = test[
                            ~test['question_english'].isin(answered_texts)
                        ][['Section', 'Group', 'question_id', 'question_english', 'correct_answer_english']]
                        unanswered.columns = ['section', 'group', 'question_id', 'question', 'answer']
                        
                        if not unanswered.empty:
                            # Add section/group selector for unanswered questions
                            col1, col2 = st.columns(2)
                            
                            # Get unique sections that have unanswered questions
                            sections_with_unanswered = sorted(unanswered['section'].unique())
                            selected_section = col1.selectbox(
                                "Select Section:", 
                                sections_with_unanswered,
                                key="unanswered_section"
                            )
                            
                            # Filter groups based on selected section
                            groups_in_section = sorted(unanswered[unanswered['section'] == selected_section]['group'].unique())
                            selected_group = col2.selectbox(
                                "Select Group:",
                                groups_in_section,
                                key="unanswered_group"
                            )
                            
                            # Get questions for selected section/group
                            filtered_questions = unanswered[
                                (filtered_questions['section'] == selected_section) & 
                                (filtered_questions['group'] == selected_group)
                            ]
                            
                            if not filtered_questions.empty:
                                st.write(f"Found {len(filtered_questions)} unanswered questions:")
                                for _, q in filtered_questions.iterrows():
                                    st.markdown(f"""
                                    ---
                                    **Question {q['question_id']}**  
                                    **Question:** {q['question']}  
                                    **Answer:** {q['answer']}
                                    """)
                            else:
                                st.info("No unanswered questions in this section/group!")
                        else:
                            st.success("You have answered all questions in the test bank!")

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
        except Exception as e:
            st.error(f"Error loading results: {str(e)}")

elif page == "Study Guide":
    st.header("Study Guide")
    
    # Add email input at the top
    
    
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
    
    # Only show practice areas if email is provided
    
    with st.expander("Areas Needing Practice", expanded=True):
        email = st.text_input("Enter your email to see personalized recommendations:", key="study_guide_email")
        if email:
            try:
                # Load test history from storage
                results = storage_mgr.get_test_results(email.lower().strip())
                
                if results:
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
                            
                            # Create section dropdown with scores
                            practice_sections = needs_practice['section'].unique()
                            section_options = [
                                f"{section} ({needs_practice[needs_practice['section'] == section]['percent'].mean():.1f}%)"
                                for section in practice_sections
                            ]
                            selected_practice_section_full = st.selectbox(
                                "Select Section to Practice:", 
                                section_options,
                                key="practice_section"
                            )
                            selected_practice_section = practice_sections[section_options.index(selected_practice_section_full)]

                            # Filter groups for selected section and create group dropdown with scores
                            section_groups_df = needs_practice[needs_practice['section'] == selected_practice_section]
                            section_groups = section_groups_df['group'].unique()
                            group_options = [
                                f"Group {group} ({section_groups_df[section_groups_df['group'] == group]['percent'].iloc[0]:.1f}%)"
                                for group in section_groups
                            ]
                            selected_practice_group_full = st.selectbox(
                                "Select Group to Practice:",
                                group_options,
                                key="practice_group"
                            )
                            selected_practice_group = section_groups[group_options.index(selected_practice_group_full)]
                            
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
                            
                            # Get and display questions for practice
                            practice_questions = test[
                                (test['Section'] == selected_practice_section) &
                                (test['Group'] == int(selected_practice_group))
                            ]
                            
                            if not practice_questions.empty:
                                st.markdown("### Practice Questions")
                                for _, q in practice_questions.iterrows():
                                   
                                    st.markdown(f"""
                                    **Question:** {q['question_english']}  
                                    **Answer:** {q['correct_answer_english']}
                                    """)
                            else:
                                st.warning("No questions found for this section and group combination")
                        else:
                            st.success(f"No topics below {threshold}%!")
                    else:
                        st.info("No test history available for analysis.")
                else:
                    st.info(f"No test history found for {email}. Take some tests to see performance analysis.")
            except Exception as e:
                st.error(f"Error loading results: {str(e)}")
        else:
            st.info("Enter your email above to see personalized practice recommendations based on your test history.")
