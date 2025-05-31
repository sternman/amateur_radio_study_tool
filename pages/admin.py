import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
from glob import glob
from functools import cache

@cache
def read_excel():
    study_guide = pd.read_excel("ham.xlsx", sheet_name="study guide", header=2)
    test = pd.read_excel("ham.xlsx", sheet_name="test")
    sections = study_guide["Section"].unique()
    return study_guide, test, sections

# Get test data
study_guide, test, sections = read_excel()

# Hide the page from navigation
st.set_page_config(
    layout="wide", 
    page_title="Admin Dashboard", 
    page_icon="🔒",
   
)

st.title("Admin Dashboard")

# Get all test result files
test_files = glob("test_results_*.json")
test_files = [os.path.basename(f) for f in test_files]
emails = [f.replace("test_results_", "").replace(".json", "") for f in test_files]

if not emails:
    st.warning("No test results found")
else:
    selected_email = st.selectbox("Select user to review:", emails)
    
    filename = f"test_results_{selected_email}.json"
    
    with open(filename, "r") as f:
        results = json.load(f)
    
    # Add after loading results
    if results:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Tests", len(results))
        col2.metric("Average Score", f"{sum(r['score'] for r in results)/len(results):.1f}%")
        col3.metric("Best Score", f"{max(r['score'] for r in results)}%")
        col4.metric("Latest Score", f"{results[-1]['score']}%")
    
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
        
        # Add before creating scores_df
        date_range = st.date_input(
            "Filter by date range",
            value=(scores_df['timestamp'].min().date(), scores_df['timestamp'].max().date()),
            key="date_filter"
        )
        if len(date_range) == 2:
            start_date, end_date = date_range
            scores_df = scores_df[
                (scores_df['timestamp'].dt.date >= start_date) & 
                (scores_df['timestamp'].dt.date <= end_date)
            ]
        
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
            title=f'Test Scores Over Time - {selected_email}',
            hover_data={'timestamp': '|%Y-%m-%d %H:%M:%S'},
            text='score',
            color='color',
            color_discrete_map="identity"
        )
        
        fig.add_hline(
            y=70, 
            line_dash="solid", 
            line_color="red",
            annotation_text="Pass (70%)",
            annotation_position="right",
            layer="below"
        )
        fig.add_hline(
            y=80, 
            line_dash="dash", 
            line_color="green",
            annotation_text="Honours (80%)",
            annotation_position="right",
            layer="below"
        )
        
        fig.update_layout(
            yaxis_range=[0, 100],
            showlegend=False
        )
        fig.update_traces(
            textposition='inside',
            texttemplate='%{text}%'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Overall summary stats
        all_answers = [ans for res in results for ans in res['answers']]
        df_all = pd.DataFrame(all_answers)
        
        if not df_all.empty:
            # Create heatmap of section/group performance
            st.subheader("Section/Group Breakdown - Heatmap")
            df_all['group'] = pd.to_numeric(df_all['group'])
            
            pivot_table = df_all.pivot_table(
                values='is_correct',
                index='section',
                columns='group',
                aggfunc='mean'
            ) * 100
            
            pivot_table = pivot_table.reindex(sorted(pivot_table.columns, key=int), axis=1)
            
            annotation_text = []
            for idx in pivot_table.index:
                row_annotations = []
                for col in pivot_table.columns:
                    val = pivot_table.loc[idx, col]
                    row_annotations.append(f"{int(val)}" if not pd.isna(val) else "")
                annotation_text.append(row_annotations)
            
            fig = px.imshow(
                pivot_table,
                labels=dict(x="Group", y="Section", color="% Correct"),
                aspect="auto",
                color_continuous_scale=["red", "orange", "yellow", "green", "blue"],
                range_color=[0, 100]
            )
            
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

            # Display coverage statistics
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
                        (unanswered['section'] == selected_section) & 
                        (unanswered['group'] == selected_group)
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
                    st.success("This user has answered all questions in the test bank!")
            
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
            
            test_idx = test_options.index(selected_test)
            res = results[::-1][test_idx]
            
            df = pd.DataFrame(res['answers'])
            df['Result'] = df['is_correct'].map({True: '✅ Correct', False: '❌ Incorrect'})
            st.dataframe(
                df[["section", "group", "question", "Result", "selected", "correct"]],
                hide_index=True,
                use_container_width=True
            )
            
            # Add after the dataframe display
            if st.button("Download User Data"):
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"test_results_{selected_email}.csv",
                    mime="text/csv"
                )

            # Add JSON download option
            with st.expander("Download User Data - JSON"):
                # Read the JSON file
                with open(filename, "r") as f:
                    json_data = f.read()
                
                st.download_button(
                    label="Download JSON",
                    data=json_data,
                    file_name=f"test_results_{selected_email}.json",
                    mime="application/json"
                )