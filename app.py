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
from psycopg2.extras import RealDictCursor
from captcha.image import ImageCaptcha
import random, string
import time

# Loading environment variables
load_dotenv()

# Initialize session state for Login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = 'login'

# Setting the wide page format
st.set_page_config(layout="wide")

# --- PostgreSQL connection ---
def get_connection():
    return psycopg2.connect(
        host="localhost",
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port="5432"
    )

# Check credentials for admin and user
def check_credentials(username, password,table):
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = f"SELECT * FROM {table} WHERE username = %s AND password = %s"
        cur.execute(query, (username, password))
        user = cur.fetchone()
        cur.close()
        conn.close()
        return user is not None
    except Exception as e:
        st.error(f"Database error: {e}")
        return False
    
def admin_interface():
    # --- Initialize page state ---
    if "admin_page" not in st.session_state:
        st.session_state.admin_page = "Data Table"

    # --- Sidebar vertical tabs ---
    st.sidebar.title("🔧 Admin Panel")
    # if st.sidebar.button("👥 Manage Users"):
    #     st.session_state.admin_page = "User Table"

    if st.sidebar.button("📊 Manage Datapoints"):
        st.session_state.admin_page = "Data Table"

    if st.sidebar.button("📊 Logout"):
        st.session_state.logged_in = "logout"
        st.rerun()

    # --- Main content based on sidebar tab selection ---
    # if st.session_state.admin_page == "User Table":
    #     st.header("👥 Manage Users")

    #     try:
    #         conn = get_connection()
    #         cur = conn.cursor(cursor_factory=RealDictCursor)
    #         cur.execute("SELECT username, status FROM users ORDER BY username")
    #         users = cur.fetchall()
    #         cur.close()
    #         conn.close()

    #         for user in users:
    #             col1, col2, col3 = st.columns([3, 2, 2])
    #             with col1:
    #                 st.write(f"👤 **{user['username']}** — `{user['status']}`")

    #             with col2:
    #                 if user["status"] != "APPROVED":
    #                     if st.button(f"✅ Approve {user['username']}", key=f"approve_{user['username']}"):
    #                         conn = get_connection()
    #                         cur = conn.cursor()
    #                         cur.execute("UPDATE users SET status = 'APPROVED' WHERE username = %s", (user['username'],))
    #                         conn.commit()
    #                         cur.close()
    #                         conn.close()
    #                         st.success(f"{user['username']} approved.")
    #                         st.rerun()

    #             with col3:
    #                 if st.button(f"🗑️ Delete {user['username']}", key=f"delete_{user['username']}"):
    #                     conn = get_connection()
    #                     cur = conn.cursor()
    #                     cur.execute("DELETE FROM users WHERE username = %s", (user['username'],))
    #                     conn.commit()
    #                     cur.close()
    #                     conn.close()
    #                     st.warning(f"{user['username']} deleted.")
    #                     st.rerun()

    #     except Exception as e:
    #         st.error(f"Error loading users: {e}")

    if st.session_state.admin_page == "Data Table":
        st.header("📈 Submissions Graph Data")
        try:
            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM quant_data where status IN ('PENDING','UPDATE REQUESTED') ORDER BY id DESC")
            data = cur.fetchall()
            cur.close()
            conn.close()
            df_data = pd.DataFrame(data)
            print(df_data.columns)

            if not data:
                st.info("✅ No pending submissions.")
            else:
                for row in data:
                    with st.container():
                        st.markdown("---")
                        col1, col2 = st.columns([8, 2])

                        with col1:
                            # st.markdown(f"**ID:** `{row['id']}`")
                            # st.markdown(f"**Reference:** {row['reference']}")
                            # st.markdown(f"**Date:** {row['date']}")
                            # st.markdown(f"**Computation:** {row['computation']}")
                            # st.markdown(f"**Qubits:** {row['num_qubits']}")
                            # st.markdown(f"**2-Qubit Gates:** {row['num_2q_gates']}")
                            # st.markdown(f"**1-Qubit Gates:** {row['num_1q_gates']}")
                            # st.markdown(f"**Total Gates:** {row['total_gates']}")
                            # st.markdown(f"**Circuit Depth:** {row['circuit_depth']}")
                            # st.markdown(f"**Depth (Measured):** {row['circuit_depth_measure']}")
                            # st.markdown(f"**Institution:** {row['institution']}")
                            # st.markdown(f"**Computer:** {row['computer']}")
                            # st.markdown(f"**Error Mitigation:** {row['error_mitigation']}")
                            # st.markdown(f"**Status:** `{row['status']}`")
                            if row["status"]=="PENDING":
                                st.markdown("New Datapoint")
                                st.table(row)
                            else:
                                st.markdown("Update Datapoint")
                                st.markdown(f"**Comments:** <span style='color:green'>{row['feedback']}</span>", unsafe_allow_html=True)
                                st.table(row)
                            

                        with col2:
                            c1, c2 = st.columns(2)
                            if c1.button("✅ Approve", key=f"approve_{row['id']}"):
                                conn = get_connection()
                                cur = conn.cursor()

                                if row['status']=='PENDING':
                                    cur.execute("UPDATE quant_data SET status = 'APPROVED' WHERE id = %s", (row['id'],))
                                else:
                                    cur.execute("DELETE from quant_data WHERE reference= %s and status= 'APPROVED'", (row['reference'],))
                                    conn.commit()
                                    cur.execute("UPDATE quant_data SET status = 'APPROVED' WHERE id = %s", (row['id'],))

                                conn.commit()
                                cur.close()
                                conn.close()
                                st.success(f"Approved ID {row['id']}")
                                st.rerun()

                            if c2.button("❌ Reject", key=f"reject_{row['id']}"):
                                conn = get_connection()
                                cur = conn.cursor()
                                cur.execute("DELETE from quant_data WHERE id = %s", (row['id'],))
                                conn.commit()
                                cur.close()
                                conn.close()
                                st.warning(f"Rejected ID {row['id']}")
                                st.rerun()

        except Exception as e:
            st.error(f"Database error: {e}")



def show_user_app():
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
    tab1, tab2, tab3, tab4= st.tabs(["Visualization", "Computer Overview", "Submit New Datapoint", "Update a Datapoint"])

    # define the costant
    length_captcha = 4
    width = 200
    height = 150



    # Database insertion function
    def insert_quantum_datapoint(
        reference, date, computation, num_qubits, num_2q_gates, num_1q_gates, total_gates,
        circuit_depth, circuit_depth_measure, institution, computer, error_mitigation
    ):
        try:
            conn = get_connection()
    
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
                'Number of qubits',
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

        
        # CAPTCHA Verification First
        if 'controllo' not in st.session_state:
            st.session_state['controllo'] = False
      
        if st.session_state['controllo'] == False:
            st.markdown("Please validate you are not a robot before submitting")

            col1, col2 = st.columns([1, 1])

            if 'Captcha' not in st.session_state:
                st.session_state['Captcha'] = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length_captcha))

            image = ImageCaptcha(width=width, height=height)
            data = image.generate(st.session_state['Captcha'])
            col1.image(data)

            captcha_input = col2.text_area('Enter captcha text', height=30)

            if st.button("Verify the code"):
                if st.session_state['Captcha'].lower() == captcha_input.strip().lower():
                    del st.session_state['Captcha']
                    st.session_state['controllo'] = True
                    #st.rerun()
                else:
                    st.error("🚨 Invalid Captcha")
                    del st.session_state['Captcha']
                    st.rerun()

            #st.stop()  # Stop here until CAPTCHA is verified

        # Only show the form if CAPTCHA passed
        if st.session_state['controllo'] == True:
            with st.form("quantum_form") :
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
                    del st.session_state["submission_success"]
                
                if submit:
                    st.write("Form submitted!")
                    st.write("Reference value:", reference)
                    if reference:
                        computation_list = [x.strip() for x in computation_raw.split(",") if x.strip()]
                        error_mitigation_list = [x.strip() for x in error_mitigation_raw.split(",") if x.strip()]
                        success = insert_quantum_datapoint(
                            reference, date, computation_list, num_qubits, num_2q_gates, num_1q_gates, total_gates,
                            circuit_depth, circuit_depth_measure, institution, computer, error_mitigation_list
                        )
                        print("success")
                        if success:
                            st.success("Quantum datapoint submitted successfully!")
                            #st.session_state['controllo'] = False
                            st.session_state.logged_in = 'refresh'
                            st.session_state.submission_success = True
                            st.rerun()
                    else:
                        st.warning("Please fill out at least the reference field.")


    with tab4:
        selected_ref = st.selectbox("🔍 Select a Reference to Update", df['Reference'])

        if selected_ref:
            record = df[df['Reference'] == selected_ref].iloc[0]
            st.subheader(f"✏️ Update Entry for: {record['Reference']}")

            new_date = st.date_input("Date", value=record['Date'])
            new_qubits = st.number_input("Number of Qubits", value=int(record['Number of qubits']))

            num_2q_gates_raw = st.text_input("Number of two Qubits", value=record['Number of two-qubit gates'])
            new_num_2q_gates = int(num_2q_gates_raw) if num_2q_gates_raw and num_2q_gates_raw.strip().isdigit() else None

            num_1q_gates_raw = st.text_input("Number of single Qubits", value=record['Number of single-qubit gates'])
            new_num_1q_gates = int(num_1q_gates_raw) if num_1q_gates_raw and num_1q_gates_raw.strip().isdigit() else None

            total_gates_raw = st.text_input("Total number of gates", value=record['Total number of gates'])
            new_total_gates = int(total_gates_raw) if total_gates_raw and total_gates_raw.strip().isdigit() else None

            circuit_depth_raw = st.text_input("Circuit depth", value=record['Circuit depth'])
            new_circuit_depth = int(circuit_depth_raw) if circuit_depth_raw and circuit_depth_raw.strip().isdigit() else None

            new_circuit_depth_measure = st.text_input("", value=record['Circuit depth measure'])
            new_institution = st.text_input("Institution", value=record['Institution'])
            new_computation = st.text_input("Computation", value=record['Computations'])
            new_computer = st.text_input("Computer", value=record['Computer'])
            new_mitigation = st.text_input("Error Mitigations", value=record['Error mitigations'])
            new_feedback = st.text_input("Comments", value=record['feedback'])

            computation_list = [x.strip() for x in new_computation.split(",") if x.strip()]
            error_mitigation_list = [x.strip() for x in new_mitigation.split(",") if x.strip()]

            # --- CAPTCHA ---
            col3, col4 = st.columns(2)

            if "update_captcha" not in st.session_state:
                st.session_state.update_captcha = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length_captcha))

            image1 = ImageCaptcha(width=width, height=height)
            data1 = image1.generate(st.session_state.update_captcha)
            col3.image(data1)

            captcha_input1 = col4.text_area('Enter the captcha text', height=30)

            if st.button("Verify I am not a robot and Submit"):
                if st.session_state.update_captcha.lower() == captcha_input1.strip().lower():
                    conn = get_connection()
                    cursor = conn.cursor()
                    status = "UPDATE REQUESTED"

                    cursor.execute("""
                        INSERT INTO quant_data (
                            reference, date, computation,
                            num_qubits, num_2q_gates, num_1q_gates, total_gates,
                            circuit_depth, circuit_depth_measure,
                            institution, computer, error_mitigation, status, feedback
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        selected_ref,
                        new_date,
                        psycopg2.extras.Json(computation_list),
                        new_qubits,
                        new_num_2q_gates,
                        new_num_1q_gates,
                        new_total_gates,
                        new_circuit_depth,
                        new_circuit_depth_measure,
                        new_institution,
                        new_computer,
                        psycopg2.extras.Json(error_mitigation_list),
                        status,
                        new_feedback
                    ))

                    conn.commit()
                    cursor.close()
                    conn.close()

                    st.success(f"Update request submitted: {record['Reference']}")
                    del st.session_state.update_captcha  # Reset captcha after success
                else:
                    st.error("🚨 Invalid Captcha")
                    del st.session_state.update_captcha
                    st.rerun()


            
            
def show_login_form():
        # --- Page Setup ---
    st.title("🔬 Count.QuOPS Portal")
    st.markdown("Welcome! Please log in as an **Admin** or a **User** to continue.")

    # --- Tabs for Login Options ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Visualization", "Computer Overview", "Submit New Datapoint", "Update a Datapoint", "Admin Login"])

    data_source = os.getenv('DATA_SOURCE')


    # define the costant
    length_captcha = 4
    width = 200
    height = 150



    # Database insertion function
    def insert_quantum_datapoint(
        reference, date, computation, num_qubits, num_2q_gates, num_1q_gates, total_gates,
        circuit_depth, circuit_depth_measure, institution, computer, error_mitigation
    ):
        try:
            conn = get_connection()
    
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
                'Number of qubits',
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

        
        # CAPTCHA Verification First
        if 'controllo' not in st.session_state:
            st.session_state['controllo'] = False
      
        if st.session_state['controllo'] == False:
            st.markdown("Please validate you are not a robot before submitting")

            col1, col2 = st.columns([1, 1])

            if 'Captcha' not in st.session_state:
                st.session_state['Captcha'] = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length_captcha))

            image = ImageCaptcha(width=width, height=height)
            data = image.generate(st.session_state['Captcha'])
            col1.image(data)

            captcha_input = col2.text_area('Enter captcha text', height=30)

            if st.button("Verify the code"):
                if st.session_state['Captcha'].lower() == captcha_input.strip().lower():
                    del st.session_state['Captcha']
                    st.session_state['controllo'] = True
                    #st.rerun()
                else:
                    st.error("🚨 Invalid Captcha")
                    del st.session_state['Captcha']
                    st.rerun()

            #st.stop()  # Stop here until CAPTCHA is verified

        # Only show the form if CAPTCHA passed
        if st.session_state['controllo'] == True:
            with st.form("quantum_form") :
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
                    del st.session_state["submission_success"]
                
                if submit:
                    st.write("Form submitted!")
                    st.write("Reference value:", reference)
                    if reference:
                        computation_list = [x.strip() for x in computation_raw.split(",") if x.strip()]
                        error_mitigation_list = [x.strip() for x in error_mitigation_raw.split(",") if x.strip()]
                        success = insert_quantum_datapoint(
                            reference, date, computation_list, num_qubits, num_2q_gates, num_1q_gates, total_gates,
                            circuit_depth, circuit_depth_measure, institution, computer, error_mitigation_list
                        )
                        print("success")
                        if success:
                            st.success("Quantum datapoint submitted successfully!")
                            #st.session_state['controllo'] = False
                            st.session_state.logged_in = 'refresh'
                            st.session_state.submission_success = True
                            st.rerun()
                    else:
                        st.warning("Please fill out at least the reference field.")


    with tab4:
        selected_ref = st.selectbox("🔍 Select a Reference to Update", df['Reference'])

        if selected_ref:
            record = df[df['Reference'] == selected_ref].iloc[0]
            st.subheader(f"✏️ Update Entry for: {record['Reference']}")

            new_date = st.date_input("Date", value=record['Date'])
            new_qubits = st.number_input("Number of Qubits", value=int(record['Number of qubits']))

            num_2q_gates_raw = st.text_input("Number of two Qubits", value=record['Number of two-qubit gates'])
            new_num_2q_gates = int(num_2q_gates_raw) if num_2q_gates_raw and num_2q_gates_raw.strip().isdigit() else None

            num_1q_gates_raw = st.text_input("Number of single Qubits", value=record['Number of single-qubit gates'])
            new_num_1q_gates = int(num_1q_gates_raw) if num_1q_gates_raw and num_1q_gates_raw.strip().isdigit() else None

            total_gates_raw = st.text_input("Total number of gates", value=record['Total number of gates'])
            new_total_gates = int(total_gates_raw) if total_gates_raw and total_gates_raw.strip().isdigit() else None

            circuit_depth_raw = st.text_input("Circuit depth", value=record['Circuit depth'])
            new_circuit_depth = int(circuit_depth_raw) if circuit_depth_raw and circuit_depth_raw.strip().isdigit() else None

            new_circuit_depth_measure = st.text_input("", value=record['Circuit depth measure'])
            new_institution = st.text_input("Institution", value=record['Institution'])
            new_computation = st.text_input("Computation", value=record['Computations'])
            new_computer = st.text_input("Computer", value=record['Computer'])
            new_mitigation = st.text_input("Error Mitigations", value=record['Error mitigations'])
            new_feedback = st.text_input("Comments", value=record['feedback'])

            computation_list = [x.strip() for x in new_computation.split(",") if x.strip()]
            error_mitigation_list = [x.strip() for x in new_mitigation.split(",") if x.strip()]

            # --- CAPTCHA ---
            col3, col4 = st.columns(2)

            if "update_captcha" not in st.session_state:
                st.session_state.update_captcha = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length_captcha))

            image1 = ImageCaptcha(width=width, height=height)
            data1 = image1.generate(st.session_state.update_captcha)
            col3.image(data1)

            captcha_input1 = col4.text_area('Enter the captcha text', height=30)

            if st.button("Verify I am not a robot and Submit"):
                if st.session_state.update_captcha.lower() == captcha_input1.strip().lower():
                    conn = get_connection()
                    cursor = conn.cursor()
                    status = "UPDATE REQUESTED"

                    cursor.execute("""
                        INSERT INTO quant_data (
                            reference, date, computation,
                            num_qubits, num_2q_gates, num_1q_gates, total_gates,
                            circuit_depth, circuit_depth_measure,
                            institution, computer, error_mitigation, status, feedback
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        selected_ref,
                        new_date,
                        psycopg2.extras.Json(computation_list),
                        new_qubits,
                        new_num_2q_gates,
                        new_num_1q_gates,
                        new_total_gates,
                        new_circuit_depth,
                        new_circuit_depth_measure,
                        new_institution,
                        new_computer,
                        psycopg2.extras.Json(error_mitigation_list),
                        status,
                        new_feedback
                    ))

                    conn.commit()
                    cursor.close()
                    conn.close()

                    st.success(f"Update request submitted: {record['Reference']}")
                    del st.session_state.update_captcha  # Reset captcha after success
                else:
                    st.error("🚨 Invalid Captcha")
                    del st.session_state.update_captcha
                    st.rerun()

    with tab5:
        st.subheader("Admin Login")
        
        admin_user = st.text_input("Username", key="admin_user")
        admin_pass = st.text_input("Password", type="password", key="admin_pass")
        if st.button("Login as Admin"):
            if check_credentials(admin_user, admin_pass,'admin_users'):
                st.success("✅ Admin login successful!")
                st.markdown("Welcome to the admin dashboard.")
                st.session_state.logged_in = 'admin'
                #login_button = st.form_submit_button('Go to App')
                st.rerun()
            # Add your admin dashboard code here
            else:
                st.error("❌ Invalid credentials.")


    # with tab2:
    #     st.subheader("User Login")
    #     user_user = st.text_input("Username", key="user_user")
    #     user_pass = st.text_input("Password", type="password", key="user_pass")
    #     if st.button("Login as User"):
    #         if check_credentials(user_user,user_pass,'users'):
    #             st.success("✅ User login successful!")
    #             st.markdown("Welcome to the quantum computing portal.")
    #             st.session_state.logged_in = 'app'
    #             #login_button = st.form_submit_button('Go to App')
    #             st.rerun()
    #             # Add user-specific features here
    #         else:
    #             st.error("❌ Invalid user credentials.")

# Main logic
if st.session_state.logged_in == 'refresh':
    #show_user_app()
    show_login_form()
elif st.session_state.logged_in == 'app':
    #show_user_app()
    show_login_form()
elif st.session_state.logged_in == 'admin':
    admin_interface()
else:
    show_login_form()


