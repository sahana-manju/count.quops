import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from data_ingestion import load_transform_data,load_comp_data_from_db
import os
from dotenv import load_dotenv
import psycopg2
from datetime import datetime
import psycopg2.extras


load_dotenv()


CORRECT_USERNAME = os.getenv('USERNAME')
CORRECT_PASSWORD = os.getenv('PASSWORD')


# Initialize session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = 'login'


# Set page layout conditionally
if st.session_state.logged_in == 'login':
    st.set_page_config(layout="centered")
else:
    st.set_page_config(layout="wide")

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
                st.session_state.logged_in = 'app'
                #login_button = st.form_submit_button('Go to App')
                if os.getenv("ENVIRONMENT")=='dev':
                    st.experimental_rerun()
                else:
                    st.rerun()
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

    # @st.cache_data(show_spinner="Loading and transforming data...")
    # def load_data(data_source):
    #     return load_transform_data(data_source)

    data_source = os.getenv('DATA_SOURCE')
    # df = load_data(data_source)
 
    #st.session_state['df'] = df

    # === Page Title ===
    st.title("Count.QuOps")

    # === Tabs ===
    tab1, tab2, tab3= st.tabs(["Visualization", "Computer Overview", "Submit Datapoint"])

    # Database insertion function
    def insert_quantum_datapoint(
        reference, date, computation, num_qubits, num_2q_gates, num_1q_gates, total_gates,
        circuit_depth, circuit_depth_measure, institution, computer, error_mitigation
    ):
        try:
            conn = psycopg2.connect(
                host="localhost",
                database=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                port="5432"
            )
    
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO quant_data (
                    reference, date, computation,
                    num_qubits, num_2q_gates, num_1q_gates, total_gates,
                    circuit_depth, circuit_depth_measure,
                    institution, computer, error_mitigation
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                reference,
                date,
                psycopg2.extras.Json(computation),
                num_qubits,
                num_2q_gates,
                num_1q_gates,
                total_gates,
                circuit_depth,
                circuit_depth_measure,
                institution,
                computer,
                psycopg2.extras.Json(error_mitigation)
            ))
            
            conn.commit()
            
            return True
        except Exception as e:
            st.error(f"Database Error: {e}")
            return False
        finally:
            cursor.close()
            conn.close()


    # === Tab 1: Visualization ===
    with tab1:
        st.header("Visual Analysis")
        df = load_transform_data('db')

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
        
        if data_source == 'sheet':
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
        else:
             # Filter DataFrame
            filtered_df = df[
                (df['Institution'].isin(selected_comps)) &
                (df['Computer'].isin(selected_computers)) &
                (df['Year'].isin(selected_years)) &
                (
                      df['Error mitigation'].apply(
                     lambda x: bool(set(x) & set(selected_errors)) if isinstance(x, list) else False
                     )
                
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
        if os.getenv("DATA_SOURCE")=='sheet':     
            sheet_id = os.getenv('SHEET_ID')
            url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
            df_comp = pd.read_excel(url,sheet_name= 1,header=1)
            df_comp.drop('Unnamed: 0',axis=1,inplace=True)
        else:  
            df_comp = load_comp_data_from_db()

        
        df_comp.fillna('',inplace=True)

        st.subheader("Quick Info")
        st.markdown(f"- **Rows:** {df_comp.shape[0]}")
        st.markdown(f"- **Columns:** {df_comp.shape[1]}")
        st.markdown(f"- **Columns:** {', '.join(df_comp.columns)}")

        st.subheader("Preview of Dataset")
        st.dataframe(df_comp)

        # Download button
        st.download_button("Download CSV", df_comp.to_csv(index=False), "dataset.csv", "text/csv")

    
    with tab3:
        st.header("Submit Quantum Datapoint")

        


        with st.form("quantum_form"):
            reference = st.text_input("Reference (URL or citation)")
            date = st.date_input("Experiment Date", value=datetime.today())
            
            computation_raw = st.text_area("Computation (comma-separated list)", help="e.g. QFT, Measurement")
            error_mitigation_raw = st.text_area("Error Mitigation (comma-separated list)", help="e.g. ZNE, Clifford Data Regression")
            
            num_qubits = st.number_input("Number of Qubits", min_value=0, step=1)

            num_2q_gates_raw = st.text_input("Number of Two-Qubit Gates")
            num_2q_gates = int(num_2q_gates_raw) if num_2q_gates_raw.strip().isdigit() else None

            num_1q_gates_raw = st.text_input("Number of Single-Qubit Gates")
            num_1q_gates = int(num_1q_gates_raw) if num_1q_gates_raw.strip().isdigit() else None

            total_gates_raw = st.text_input("Total Number of Gates")
            total_gates = int(total_gates_raw) if total_gates_raw.strip().isdigit() else None

            circuit_depth_raw = st.text_input("Circuit Depth")
            circuit_depth = int(circuit_depth_raw) if circuit_depth_raw.strip().isdigit() else None

            circuit_depth_measure = st.text_input("Circuit Depth Measure")
            
            institution = st.text_input("Institution")
            computer = st.text_input("Computer")
            
            submit = st.form_submit_button("Submit")

            if st.session_state.get("submission_success"):
                st.success("Quantum datapoint submitted successfully!")
                del st.session_state["submission_success"]  # clear the flag

            if submit:
                if reference:
                    computation_list = [x.strip() for x in computation_raw.split(",") if x.strip()]
                    error_mitigation_list = [x.strip() for x in error_mitigation_raw.split(",") if x.strip()]
                    success = insert_quantum_datapoint(
                        reference, date, computation_list, num_qubits, num_2q_gates, num_1q_gates, total_gates,
                        circuit_depth, circuit_depth_measure, institution, computer, error_mitigation_list
                    )
                    if success:
                        st.success("Quantum datapoint submitted successfully!")
                        st.session_state.logged_in='refresh'
                        st.session_state.submission_success=True
                        if os.getenv("ENVIRONMENT")=='dev':
                            st.experimental_rerun()
                        else:
                            st.rerun()
                        
    
                else:
                    st.warning("Please fill out at least the reference field.")
            


# Main logic
if st.session_state.logged_in == 'refresh':
    show_main_app()
elif st.session_state.logged_in == 'app':
    show_main_app()
else:
    show_login_form()


