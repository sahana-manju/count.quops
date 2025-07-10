import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from data_ingestion import load_transform_data
import os
from dotenv import load_dotenv



load_dotenv()


CORRECT_USERNAME = os.getenv('USERNAME')
CORRECT_PASSWORD = os.getenv('PASSWORD')


# Initialize session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# Set page layout conditionally
if st.session_state.logged_in:
    st.set_page_config(layout="wide")
else:
    st.set_page_config(layout="centered")

def show_login_form():
    with st.form(key='login_form'):
        st.subheader('🔐 Login Credentials')
        username = st.text_input('**Username:**')
        password = st.text_input('**Password:**', type='password')
        login_button = st.form_submit_button('Login')

        if login_button:
            if not username or not password:
                st.error("Please enter both username and password.")
            elif username == CORRECT_USERNAME and password == CORRECT_PASSWORD:
                st.success("Login successful!")
                st.session_state.logged_in = True
                login_button = st.form_submit_button('Go to App')
            else:
                st.error("Invalid username or password")

def show_main_app():
    #st.set_page_config(layout="wide")

    # Sidebar logout button
    with st.sidebar:
        st.subheader("🔐 Session")
        if st.button("Logout"):
            st.button("Confirm Logout")
            st.session_state.logged_in = False

    @st.cache_data(show_spinner="Loading and transforming data...")
    def load_data(sheet_id):
        return load_transform_data(sheet_id)

    sheet_id = os.getenv('SHEET_ID')
    df = load_data(sheet_id)
    st.session_state['df'] = df

    # === Page Title ===
    st.title("Count.QuOps")

    # === Tabs ===
    tab1, tab2 = st.tabs(["📊 Visualization", "📋 Computer Overview"])

    # === Tab 1: Visualization ===
    with tab1:
        st.header("Visual Analysis")

            # Create two columns
        col1, col2 = st.columns([1, 2])  # You can adjust the ratio as needed

        # Filter controls in the first column
        with col1:
            # Institution filter
            comp_options = list(df['Institution'].unique())
            selected_comps = st.multiselect("Select Institution Types", comp_options, default=comp_options)

            # Computer filter based on Institution
            filtered_computer_options = df[df['Institution'].isin(selected_comps)]['Computer'].dropna().unique()
            selected_computers = st.multiselect("Select Computers", filtered_computer_options, default=filtered_computer_options)

            # Year filter
            years = sorted(df['Year'].dropna().unique())
            selected_years = st.multiselect("Select Years", years, default=years)

            # Error mitigation filter
            error_methods = [
                'Bitstring postselection', 'Dynamical decoupling', 'Floquet calibration', 'Pauli twirling',
                'Probabilistic error amplification', 'Readout error mitigation', 'Zero noise extrapolation', 'No Data'
            ]
            selected_errors = st.multiselect("Select Error Mitigation", error_methods, default=error_methods)

            # Y-axis selection
            y_options = [
                'Number of two-qubit gates',
                'Number of single-qubit gates',
                'Total number of gates',
                'Circuit depth'
            ]
            y_axis = st.selectbox("Select Y-axis", y_options)

            # B-axis selection
            b_options = [
                'Number of two-qubit gates',
                'Number of single-qubit gates',
                'Total number of gates',
                'Circuit depth',
                'Date'
            ]
            b_axis = st.selectbox("Select column for the size of pointers", b_options)

            if b_axis == 'Date':
                date_min = df['Date'].min()
                date_max = df['Date'].max()
                df['bubble_size'] = df['Date'].apply(lambda x: (x - date_min).days / (date_max - date_min).days if pd.notnull(x) else None)

                # Scale to a desired range (e.g., 10–60)
                df['bubble_size'] = df['bubble_size'] * 50 + 10  # range from 10 to 60
                b_axis = 'bubble_size'
        
        # Filter DataFrame
        filtered_df = df[
            (df['Institution'].isin(selected_comps)) &
            (df['Computer'].isin(selected_computers)) &
            (df['Year'].isin(selected_years)) &
            (
                df['Error mitigation'].isin(selected_errors) |
                df['Error mitigation_1'].isin(selected_errors) |
                df['Error mitigation_2'].isin(selected_errors) |
                df['Error mitigation_3'].isin(selected_errors)
            )
        ]

        filtered_df = filtered_df.dropna(subset=[b_axis])

        

        # Plot in the second column
        with col2:
            
            
            fig = px.scatter(
                filtered_df,
                x='Number of qubits',
                y=y_axis,
                color='Computer',
                hover_data=['Reference', 'Year', 'Error mitigations', 'Computations'],
                title=f"{y_axis} vs Number of Qubits",
                height=650,
                width=900,
                size=b_axis,
                size_max=60
            )
        
            st.plotly_chart(fig, use_container_width=True)


    # === Tab 2: Dataset Overview ===
    with tab2:
        st.header("Computer Overview")

        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
        df_comp = pd.read_excel(url,sheet_name= 1,header=1)
        df_comp.drop('Unnamed: 0',axis=1,inplace=True)
        df_comp.fillna('',inplace=True)

        st.subheader("Quick Info")
        st.markdown(f"- **Rows:** {df_comp.shape[0]}")
        st.markdown(f"- **Columns:** {df_comp.shape[1]}")
        st.markdown(f"- **Columns:** {', '.join(df_comp.columns)}")

        st.subheader("Preview of Dataset")
        st.dataframe(df_comp)

        # Download button
        st.download_button("Download CSV", df_comp.to_csv(index=False), "dataset.csv", "text/csv")

# Main logic
if st.session_state.logged_in:
    show_main_app()
else:
    show_login_form()
