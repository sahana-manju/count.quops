import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from streamlit_plotly_events import plotly_events
import plotly.io as pio
pio.templates.default = "plotly"
from streamlit_echarts import st_echarts
from streamlit.components.v1 import html
from pyecharts.commons.utils import JsCode

import numpy as np
import pandas as pd
from data_ingestion import load_transform_data,load_comp_data_from_db
import math

import os
from dotenv import load_dotenv

import psycopg2
import psycopg2.extras
from psycopg2.extras import RealDictCursor

from captcha.image import ImageCaptcha
import random, string
from datetime import datetime
import time
from urllib.parse import urlparse

# Loading environment variables
load_dotenv()

# Initialize session state for Login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = 'login'

# Setting the wide page format
st.set_page_config(layout="wide")

def is_nan_or_nan_string(val):
    # Check for actual NaN
    if isinstance(val, float) and math.isnan(val):
        return True
    if isinstance(val, np.float64) and np.isnan(val):
        return True
    # Check for string 'nan', 'NaN', etc.
    if isinstance(val, str) and val.strip().lower() == 'nan':
        return True
    return False

# --- PostgreSQL connection ---
def get_connection():
    return psycopg2.connect(
        host="localhost",
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port="5432"
    )


def df_to_json_safe(df: pd.DataFrame):
    """
    Convert a pandas DataFrame into a JSON-safe list-of-lists format.
    Ensures numpy.int64, numpy.float64, NaN, etc. are converted to Python-native types.
    """
    def to_native(val):
        if isinstance(val, (np.generic,)):   # np.int64, np.float64, etc.
            return val.item()
        if pd.isna(val):  # Handle NaN / None
            return None
        return val
    
    return [df.columns.tolist()] + [[to_native(v) for v in row] for row in df.values.tolist()]

def is_hyperlink(s):
    try:
        result = urlparse(s)
        return all([result.scheme in ("http", "https"), result.netloc])
    except ValueError:
        return False
    
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

    if st.sidebar.button("📊 Manage Requests"):
        st.session_state.admin_page = "Data Table"

    if st.sidebar.button("📊 View Data Tables"):
        st.session_state.admin_page = "Database"

    if st.sidebar.button("📊 Logout"):
        st.session_state.logged_in = "app"
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
        
    if st.session_state.admin_page == "Database":
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM quant_data ORDER BY id DESC")
        data = cur.fetchall()
        cur.close()
        conn.close()
        df_all = pd.DataFrame(data)
        st.dataframe(df_all)
        df_ids = df_all["id"].unique()
        id_selected= st.selectbox("Select the id",df_ids)
        operations = st.selectbox("Select the operation to be performed",['Delete','Update'])

        # Initialize session state variables
        if "delete_requested" not in st.session_state:
            st.session_state.delete_requested = False
        if "delete_confirmed" not in st.session_state:
            st.session_state.delete_confirmed = False

        if operations == "Delete":
            # Step 1: User clicks "Delete Record"
            if st.button("Delete Record"):
                st.session_state.delete_requested = True

            # Step 2: Show confirmation buttons
            if st.session_state.delete_requested and not st.session_state.delete_confirmed:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Confirm Deletion"):
                        st.session_state.delete_confirmed = True
                with col2:
                    if st.button("❌ Cancel"):
                        st.session_state.delete_requested = False
                        st.session_state.delete_confirmed = False
                        st.warning("Deletion cancelled.")
                        st.rerun()

            # Step 3: Actually delete the record
            if st.session_state.delete_confirmed:
                conn = get_connection()
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("DELETE FROM quant_data WHERE id = %s", (int(id_selected),))
                conn.commit()
                cur.close()
                conn.close()
                st.success("✅ Successfully deleted the record.")

                if st.button("🔄 Click to refresh and see updates"):
                    st.session_state.delete_requested = False
                    st.session_state.delete_confirmed = False
                    st.rerun()

                
       
                



        if operations == "Update":
            
            df_all['Computations'] = df_all['computation'].apply(
                lambda x: ', '.join(x) if isinstance(x, list) else ''
                )
            df_all['Error mitigations'] = df_all['error_mitigation'].apply(
            lambda x: ', '.join(x) if isinstance(x, list) else ''
            )

            df_all = df_all.rename(columns={
                'reference': 'Reference',
                'date': 'Date',
                'computation': 'Computation',
                'num_qubits': 'Number of qubits',
                'num_2q_gates': 'Number of two-qubit gates',
                'num_1q_gates': 'Number of single-qubit gates',
                'total_gates':'Total number of gates',
                'circuit_depth':'Circuit depth',
                'circuit_depth_measure':'Circuit depth measure',
                'institution':'Institution',
                'computer':	'Computer',	
                })
            
            record = df_all[df_all['id'] == id_selected]
            if not record.empty:
            
                record = record.iloc[0]

                ref = st.text_input("Reference", value=record['Reference'])

                new_date = st.date_input("Date", value=record['Date'])
                new_qubits = st.number_input("Number of Qubits", value=int(record['Number of qubits']))

                try:
                    num_2q_gates_raw = st.text_input("Number of Two-Qubit Gates", value=record['Number of two-qubit gates'])
                    new_num_2q_gates = float(num_2q_gates_raw) if num_2q_gates_raw and not is_nan_or_nan_string(num_2q_gates_raw) else None
                except:
                    st.error("Invalid input. Please input a valid number")
                    

                try:
                    num_1q_gates_raw = st.text_input("Number of Single-Qubit Gates", value=record['Number of single-qubit gates'])
                    new_num_1q_gates = float(num_1q_gates_raw) if num_1q_gates_raw and not is_nan_or_nan_string(num_1q_gates_raw) else None
                except:
                    st.error("Invalid input. Please input a valid number")
                    

                try:
                    total_gates_raw = st.text_input("Total number of gates", value=record['Total number of gates'])
                    new_total_gates = float(total_gates_raw) if total_gates_raw and not is_nan_or_nan_string(total_gates_raw) else None
                except:
                    st.error("Invalid input. Please input a valid number")
                    
                try:
                    circuit_depth_raw = st.text_input("Circuit depth", value=record['Circuit depth'])
                    new_circuit_depth = float(circuit_depth_raw) if circuit_depth_raw and not is_nan_or_nan_string(circuit_depth_raw) else None
                except:
                    st.error("Invalid input. Please input a valid number")
                    
                new_circuit_depth_measure = st.text_input("Circuit depth measure", value=record['Circuit depth measure'])
                new_institution = st.text_input("Institution", value=record['Institution'])
                new_computation = st.text_input("Computation", value=record['Computations'])
                new_computer = st.text_input("Computer", value=record['Computer'])
                #new_mitigation = st.text_input("Error Mitigations", value=record['Error mitigations'])
                new_feedback = st.text_input("Comments", value=record['feedback'])

                computation_list = [x.strip() for x in new_computation.split(",") if x.strip()]
                #error_mitigation_list = [x.strip() for x in new_mitigation.split(",") if x.strip()]


                if st.button("Save Changes"):
                    if not ref:
                        st.error("Please fill out Reference(url or citation) as it is a required field. ")
                    if not new_qubits:
                        st.error("Please fill out Number of Qubits as it is a required field. ")
                    if not (new_num_2q_gates or new_total_gates):
                        st.error("Please fill either Number of two-Qubit operations or Total Number of Operations")
                    if not new_institution:
                        st.error("Please fill out Institution as it is a required field. ")
                    if not new_computer:
                        st.error("Please fill out Computer as it is a required field. ")
                    else:
                        conn = get_connection()
                        cursor = conn.cursor()
                        status = "APPROVED"

                        cursor.execute("""
                            UPDATE quant_data SET
                                reference = %s,
                                date = %s,
                                computation = %s,
                                num_qubits = %s,
                                num_2q_gates = %s,
                                num_1q_gates = %s,
                                total_gates = %s,
                                circuit_depth = %s,
                                circuit_depth_measure = %s,
                                institution = %s,
                                computer = %s,
                                status = %s,
                                feedback = %s
                            WHERE id = %s
                        """, (
                            ref,
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
                            status,
                            new_feedback,
                            int(record["id"]))
                        )
                        

                        conn.commit()
                        cursor.close()
                        conn.close()

                        st.success(f"Update done for ID : {record['id']}")

                        if st.button("Click to refresh and see updates"):
                            st.rerun()
                            


        



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

            if not data:
                st.info("✅ No pending submissions.")
            else:
                for index,row in df_data.iterrows():
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



# def show_user_app():
#     #st.set_page_config(layout="wide")

#     # Sidebar logout button
#     with st.sidebar:
#         st.subheader("🔐 Session")
#         if st.button("Logout"):
#             st.button("Confirm Logout")
#             st.session_state.logged_in = False

#     # @st.cache_data(show_spinner="Loading and transforming data...")
#     # def load_data(data_source):
#     #     return load_transform_data(data_source)

#     data_source = os.getenv('DATA_SOURCE')
#     # df = load_data(data_source)
 
#     #st.session_state['df'] = df

#     # === Page Title ===
#     st.title("Quantum Operation Counts")

#     # === Tabs ===
#     tab1, tab2, tab3, tab4= st.tabs(["Visualization", "Computer Overview", "Submit New Datapoint", "Update a Datapoint"])

#     # define the costant
#     length_captcha = 4
#     width = 200
#     height = 150



#     # Database insertion function
#     def insert_quantum_datapoint(
#         reference, date, computation, num_qubits, num_2q_gates, num_1q_gates, total_gates,
#         circuit_depth, circuit_depth_measure, institution, computer, error_mitigation
#     ):
#         try:
#             conn = get_connection()
    
#             cursor = conn.cursor()
            
#             cursor.execute("""
#                 INSERT INTO quant_data (
#                     reference, date, computation,
#                     num_qubits, num_2q_gates, num_1q_gates, total_gates,
#                     circuit_depth, circuit_depth_measure,
#                     institution, computer, error_mitigation
#                 )
#                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
#             """, (
#                 reference,
#                 date,
#                 psycopg2.extras.Json(computation),
#                 num_qubits,
#                 num_2q_gates,
#                 num_1q_gates,
#                 total_gates,
#                 circuit_depth,
#                 circuit_depth_measure,
#                 institution,
#                 computer,
#                 psycopg2.extras.Json(error_mitigation)
#             ))
            
#             conn.commit()
            
#             return True
#         except Exception as e:
#             st.error(f"Database Error: {e}")
#             return False
#         finally:
#             cursor.close()
#             conn.close()


#     # === Tab 1: Visualization ===
#     with tab1:
#         st.header("Visual Analysis")
#         df = load_transform_data('db')

#             # Create two columns
#         col1, col2 = st.columns([1, 2])  # You can adjust the ratio as needed

#         # Filter controls in the first column
#         with col1:
#             # Institution filter
#             comp_options = list(df['Institution'].unique())
#             selected_comps = st.multiselect("Select Institution Types", comp_options, default=comp_options)

#             # Computer filter based on Institution
#             filtered_computer_options = df[df['Institution'].isin(selected_comps)]['Computer'].dropna().unique()
#             selected_computers = st.multiselect("Select Computers", filtered_computer_options, default=filtered_computer_options)

#             # Year filter
#             years = sorted(df['Year'].dropna().unique())
#             selected_years = st.multiselect("Select Years", years, default=years)

#             # Error mitigation filter
#             error_methods = [
#                 'Bitstring postselection', 'Dynamical decoupling', 'Floquet calibration', 'Pauli twirling',
#                 'Probabilistic error amplification', 'Readout error mitigation', 'Zero noise extrapolation', 'No Data'
#             ]
#             selected_errors = st.multiselect("Select Error Mitigation", error_methods, default=error_methods)

#             # Y-axis selection
#             y_options = [
#                 'Number of two-qubit gates',
#                 'Number of single-qubit gates',
#                 'Total number of gates',
#                 'Circuit depth'
#             ]
#             y_axis = st.selectbox("Select Y-axis", y_options)

#             # B-axis selection
#             b_options = [
#                 'Number of qubits',
#                 'Number of two-qubit gates',
#                 'Number of single-qubit gates',
#                 'Total number of gates',
#                 'Circuit depth',
#                 'Date'
#             ]
#             b_axis = st.selectbox("Select column for the size of pointers", b_options)

#             if b_axis == 'Date':
#                 date_min = df['Date'].min()
#                 date_max = df['Date'].max()
#                 df['bubble_size'] = df['Date'].apply(lambda x: (x - date_min).days / (date_max - date_min).days if pd.notnull(x) else None)

#                 # Scale to a desired range (e.g., 10–60)
#                 df['bubble_size'] = df['bubble_size'] * 50 + 10  # range from 10 to 60
#                 b_axis = 'bubble_size'
        
#         if data_source == 'sheet':
#         # Filter DataFrame
#             filtered_df = df[
#                 (df['Institution'].isin(selected_comps)) &
#                 (df['Computer'].isin(selected_computers)) &
#                 (df['Year'].isin(selected_years)) &
#                 (
#                     df['Error mitigation'].isin(selected_errors) |
#                     df['Error mitigation_1'].isin(selected_errors) |
#                     df['Error mitigation_2'].isin(selected_errors) |
#                     df['Error mitigation_3'].isin(selected_errors)
#                 )
#             ]
#         else:
#              # Filter DataFrame
#             filtered_df = df[
#                 (df['Institution'].isin(selected_comps)) &
#                 (df['Computer'].isin(selected_computers)) &
#                 (df['Year'].isin(selected_years)) &
#                 (
#                       df['Error mitigation'].apply(
#                      lambda x: bool(set(x) & set(selected_errors)) if isinstance(x, list) else False
#                      )
                
#                 )
#             ]


#         filtered_df = filtered_df.dropna(subset=[b_axis])

        

#         # Plot in the second column
#         with col2:
            
            
#             fig = px.scatter(
#                 filtered_df,
#                 x='Number of qubits',
#                 y=y_axis,
#                 color='Computer',
#                 hover_data=['Reference', 'Year', 'Error mitigations', 'Computations'],
#                 title=f"{y_axis} vs Number of Qubits",
#                 height=650,
#                 width=900,
#                 size=b_axis,
#                 size_max=60
#             )
        
#             st.plotly_chart(fig, use_container_width=True)



#     # === Tab 2: Dataset Overview ===
#     with tab2:
#         st.header("Computer Overview")
#         if os.getenv("DATA_SOURCE")=='sheet':     
#             sheet_id = os.getenv('SHEET_ID')
#             url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
#             df_comp = pd.read_excel(url,sheet_name= 1,header=1)
#             df_comp.drop('Unnamed: 0',axis=1,inplace=True)
#         else:  
#             df_comp = load_comp_data_from_db()

        
#         df_comp.fillna('',inplace=True)

#         st.subheader("Quick Info")
#         st.markdown(f"- **Rows:** {df_comp.shape[0]}")
#         st.markdown(f"- **Columns:** {df_comp.shape[1]}")
#         st.markdown(f"- **Columns:** {', '.join(df_comp.columns)}")

#         st.subheader("Preview of Dataset")
#         st.dataframe(df_comp)

#         # Download button
#         st.download_button("Download CSV", df_comp.to_csv(index=False), "dataset.csv", "text/csv")

    
#     with tab3:
#         st.header("Submit Quantum Datapoint")

        
#         # CAPTCHA Verification First
#         if 'controllo' not in st.session_state:
#             st.session_state['controllo'] = False
      
#         if st.session_state['controllo'] == False:
#             st.markdown("Please validate you are not a robot before submitting")

#             col1, col2 = st.columns([1, 1])

#             if 'Captcha' not in st.session_state:
#                 st.session_state['Captcha'] = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length_captcha))

#             image = ImageCaptcha(width=width, height=height)
#             data = image.generate(st.session_state['Captcha'])
#             col1.image(data)

#             captcha_input = col2.text_area('Enter captcha text', height=30)

#             if st.button("Verify the code"):
#                 if st.session_state['Captcha'].lower() == captcha_input.strip().lower():
#                     del st.session_state['Captcha']
#                     st.session_state['controllo'] = True
#                     #st.rerun()
#                 else:
#                     st.error("🚨 Invalid Captcha")
#                     del st.session_state['Captcha']
#                     st.rerun()

#             #st.stop()  # Stop here until CAPTCHA is verified

#         # Only show the form if CAPTCHA passed
#         if st.session_state['controllo'] == True:
#             with st.form("quantum_form") :
#                 reference = st.text_input("Reference (URL or citation)")
#                 date = st.date_input("Experiment Date", value=datetime.today())

#                 computation_raw = st.text_area("Computation (comma-separated list)", help="e.g. QFT, Measurement")
#                 error_mitigation_raw = st.text_area("Error Mitigation (comma-separated list)", help="e.g. ZNE, Clifford Data Regression")

#                 num_qubits = st.number_input("Number of Qubits", min_value=0, step=1, help = "Number of qubits used in the quantum computation")

#                 num_2q_gates_raw = st.text_input("Number of Two-Qubit Operations", help = "Number of two-qubit operations used in the quantum computation")
#                 num_2q_gates = int(num_2q_gates_raw) if num_2q_gates_raw.strip().isdigit() else None

#                 num_1q_gates_raw = st.text_input("Number of Single-Qubit Operations", help = "Number of siingle-qubit operations used in the quantum computation")
#                 num_1q_gates = int(num_1q_gates_raw) if num_1q_gates_raw.strip().isdigit() else None

#                 total_gates_raw = st.text_input("Total Number of Operations",help = "Total number of operations used in the quantum computation, e.g. single-qubit operations + two-qubit operations")
#                 total_gates = int(total_gates_raw) if total_gates_raw.strip().isdigit() else None

#                 circuit_depth_raw = st.text_input("Circuit Depth")
#                 circuit_depth = int(circuit_depth_raw) if circuit_depth_raw.strip().isdigit() else None

#                 circuit_depth_measure = st.text_input("Circuit Depth Measure")

#                 institution = st.text_input("Institution")
#                 computer = st.text_input("Computer")

#                 submit = st.form_submit_button("Submit")
          
#                 if st.session_state.get("submission_success"):
#                     st.success("Quantum datapoint submitted successfully!")
#                     del st.session_state["submission_success"]
                
#                 if submit:
#                     st.write("Form submitted!")
#                     st.write("Reference value:", reference)
#                     if reference:
#                         computation_list = [x.strip() for x in computation_raw.split(",") if x.strip()]
#                         error_mitigation_list = [x.strip() for x in error_mitigation_raw.split(",") if x.strip()]
#                         success = insert_quantum_datapoint(
#                             reference, date, computation_list, num_qubits, num_2q_gates, num_1q_gates, total_gates,
#                             circuit_depth, circuit_depth_measure, institution, computer, error_mitigation_list
#                         )
#                         print("success")
#                         if success:
#                             st.success("Quantum datapoint submitted successfully!")
#                             #st.session_state['controllo'] = False
#                             #st.session_state.logged_in = 'refresh'
#                             st.session_state.submission_success = True
#                             st.rerun()
#                     else:
#                         st.warning("Please fill out at least the reference field.")


#     with tab4:
#         selected_ref = st.selectbox("🔍 Select a Reference to Update", df['Reference'])

#         if selected_ref:
#             record = df[df['Reference'] == selected_ref].iloc[0]
#             st.subheader(f"✏️ Update Entry for: {record['Reference']}")

#             new_date = st.date_input("Date", value=record['Date'])
#             new_qubits = st.number_input("Number of Qubits", value=int(record['Number of qubits']))

#             num_2q_gates_raw = st.text_input("Number of Two-Qubit Operations", value=record['Number of two-qubit gates'])
#             new_num_2q_gates = int(num_2q_gates_raw) if num_2q_gates_raw and num_2q_gates_raw.strip().isdigit() else None

#             num_1q_gates_raw = st.text_input("Number of Single-Qubit Operations", value=record['Number of single-qubit gates'])
#             new_num_1q_gates = int(num_1q_gates_raw) if num_1q_gates_raw and num_1q_gates_raw.strip().isdigit() else None

#             total_gates_raw = st.text_input("Total number of Operations", value=record['Total number of gates'])
#             new_total_gates = int(total_gates_raw) if total_gates_raw and total_gates_raw.strip().isdigit() else None

#             circuit_depth_raw = st.text_input("Circuit depth", value=record['Circuit depth'])
#             new_circuit_depth = int(circuit_depth_raw) if circuit_depth_raw and circuit_depth_raw.strip().isdigit() else None

#             new_circuit_depth_measure = st.text_input("Circuit depth measure", value=record['Circuit depth measure'])
#             new_institution = st.text_input("Institution", value=record['Institution'])
#             new_computation = st.text_input("Computation", value=record['Computations'])
#             new_computer = st.text_input("Computer", value=record['Computer'])
#             new_mitigation = st.text_input("Error Mitigations", value=record['Error mitigations'])
#             new_feedback = st.text_input("Comments", value=record['feedback'])

#             computation_list = [x.strip() for x in new_computation.split(",") if x.strip()]
#             error_mitigation_list = [x.strip() for x in new_mitigation.split(",") if x.strip()]

#             # --- CAPTCHA ---
#             col3, col4 = st.columns(2)

#             if "update_captcha" not in st.session_state:
#                 st.session_state.update_captcha = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length_captcha))

#             image1 = ImageCaptcha(width=width, height=height)
#             data1 = image1.generate(st.session_state.update_captcha)
#             col3.image(data1)

#             captcha_input1 = col4.text_area('Enter the captcha text', height=30)

#             if st.button("Verify I am not a robot and Submit"):
#                 if st.session_state.update_captcha.lower() == captcha_input1.strip().lower():
#                     conn = get_connection()
#                     cursor = conn.cursor()
#                     status = "UPDATE REQUESTED"

#                     cursor.execute("""
#                         INSERT INTO quant_data (
#                             reference, date, computation,
#                             num_qubits, num_2q_gates, num_1q_gates, total_gates,
#                             circuit_depth, circuit_depth_measure,
#                             institution, computer, error_mitigation, status, feedback
#                         )
#                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
#                     """, (
#                         selected_ref,
#                         new_date,
#                         psycopg2.extras.Json(computation_list),
#                         new_qubits,
#                         new_num_2q_gates,
#                         new_num_1q_gates,
#                         new_total_gates,
#                         new_circuit_depth,
#                         new_circuit_depth_measure,
#                         new_institution,
#                         new_computer,
#                         psycopg2.extras.Json(error_mitigation_list),
#                         status,
#                         new_feedback
#                     ))

#                     conn.commit()
#                     cursor.close()
#                     conn.close()

#                     st.success(f"Update request submitted: {selected_ref}")
#                     del st.session_state.update_captcha  # Reset captcha after success
#                 else:
#                     st.error("🚨 Invalid Captcha")
#                     del st.session_state.update_captcha
#                     st.rerun()


            
            
def show_login_form():
        # --- Page Setup ---
    st.title("🔬 Quantum Operations (QuOps) Info")



    if "clicked_id" not in st.session_state:
        st.session_state.clicked_id = None
    


    # --- Tabs for Login Options ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["About","Visualization", "Submit New Datapoint", "Update a Datapoint", "Admin Login"])

    

    def switch(tab):
        return f"""
    var tabGroup = window.parent.document.getElementsByClassName("stTabs")[0]
    var tab = tabGroup.getElementsByTagName("button")
    tab[{tab}].click()
    """
    # last_row = st.container()
    # if last_row.button("Update Datapoint"):
    #     html(f"<script>{switch(3)}</script>", height=0)

    
   

    data_source = os.getenv('DATA_SOURCE')

    # define the costant
    length_captcha = 4
    width = 200
    height = 150
    
    html(f"<script>{switch(1)} </script>", height=0)

    # Database insertion function
    def insert_quantum_datapoint(
        reference, date, computation, num_qubits, num_2q_gates, num_1q_gates, total_gates,
        circuit_depth, circuit_depth_measure, institution, computer
    ):
        try:
            conn = get_connection()
    
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO quant_data (
                    reference, date, computation,
                    num_qubits, num_2q_gates, num_1q_gates, total_gates,
                    circuit_depth, circuit_depth_measure,
                    institution, computer
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                computer
            ))
            
            conn.commit()
            
            return True
        except Exception as e:
            st.error(f"Database Error: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    with tab1:
        # Page title

        # Inject button + JS in one iframe
        html(f"""
             <style>
             button
             {{
                 
                border: none;
                background-color: white;
                color: blue;
                text-decoration: underline;
                cursor: pointer;
                font: inherit;
                padding: 0;
             }}
             </style>
             <div style="font-family: system-ui, sans-serif; line-height: 1.6; font-size: 1rem;">
                <p>
                    Track the quantum operations (QuOps) used in state-of-the-art quantum computations over time.
                </p>

                <p>
                    On the visualization page <button class="goto" style="margin-left: 6px;">Visualization</button>:<br>
                    1. <strong>Hover</strong> over a point to see its data.<br>
                    2. <strong>Single-click</strong> a point to update its data.<br>
                    3. <strong>Double-click</strong> a point to open its reference.
                </p>

                <p>
                    You can also submit new datapoints 
                    <button class="gotos" style="margin-left: 6px;">Submit new datapoint</button>.
                </p>

                <p>
                    All new submissions and updates are reviewed by site administrators.
                </p>
            </div>
                
                <script>
                const be = document.querySelector(".goto");
                be.addEventListener("click", () => {{
                    {switch(1)}
                }});
                const bes = document.querySelector(".gotos");
                bes.addEventListener("click",()=>{{
                      {switch(2)} 
                    
                }});
                </script>
            """, height=500)

    # === Tab 1: Visualization ===
    with tab2:
        
        #st.header("Visual Analysis")
        df = load_transform_data('db')

            # Create two columns
        col1, col2 = st.columns([1, 2])  # You can adjust the ratio as needed

        # Filter controls in the first column
        with col1:
            # Institution filter
            comp_options = list(df['Institution'].unique())
            selected_comps = st.multiselect("Institution", comp_options, default=comp_options)

            # Computer filter based on Institution
            filtered_computer_options = df[df['Institution'].isin(selected_comps)]['Computer'].dropna().unique()
            selected_computers = st.multiselect("Computer", filtered_computer_options, default=filtered_computer_options)

            # Year filter
            years = sorted(df['Year'].dropna().unique())
            selected_years = st.multiselect("Year", years, default=years)

            # Error mitigation filter
            # Flatten the list and get unique values
            #unique_items = set(item for sublist in df['Error mitigation'] for item in sublist)

            # If you want it as a list
            # error_methods = list(unique_items)
            # # error_methods = [
            # #     'Bitstring postselection', 'Dynamical decoupling', 'Floquet calibration', 'Pauli twirling',
            # #     'Probabilistic error amplification', 'Readout error mitigation', 'Zero noise extrapolation', 'No Data'
            # # ]
            # selected_errors = st.multiselect("Select Error Mitigation", error_methods, default=error_methods)

            # Y-axis selection
            y_options = [
                'Number of two-qubit gates',
                'Number of single-qubit gates',
                'Total number of gates',
                'Circuit depth'
            ]
            y_axis = st.selectbox("Vertical axis", y_options)

            # B-axis selection
            b_options = [
                'Date (more recent = larger)',
                'Number of qubits',
                'Number of two-qubit gates',
                'Number of single-qubit gates',
                'Total number of gates',
                'Circuit depth',
                
            ]
            
            b_axis = st.selectbox("Marker size", b_options)
            if b_axis == 'Date (more recent = larger)':
                b_axis = 'Date'

            if b_axis == 'Date':
                date_min = df['Date'].min()
                date_max = df['Date'].max()
                df['bubble_size'] = df['Date'].apply(lambda x: (x - date_min).days / (date_max - date_min).days if pd.notnull(x) else None)

                # Scale to a desired range (e.g., 10–60)
                df['bubble_size'] = df['bubble_size'] * 50 + 10  # range from 10 to 60
                b_axis = 'bubble_size'

            col5,col6 = st.columns(2)

            with col5:
                x_axis_scale = st.selectbox("X-axis scale", ["Linear", "Log"], index=0)
            with col6:
                y_axis_scale = st.selectbox("Y-axis scale", ["Linear", "Log"], index=0)
        
        if data_source == 'sheet':
        # Filter DataFrame
            filtered_df = df[
                (df['Institution'].isin(selected_comps)) &
                (df['Computer'].isin(selected_computers)) &
                (df['Year'].isin(selected_years)) 
                # &
                # (
                #     df['Error mitigation'].isin(selected_errors) |
                #     df['Error mitigation_1'].isin(selected_errors) |
                #     df['Error mitigation_2'].isin(selected_errors) |
                #     df['Error mitigation_3'].isin(selected_errors)
                # )
            ]
        else:
             # Filter DataFrame
            filtered_df = df[
                (df['Institution'].isin(selected_comps)) &
                (df['Computer'].isin(selected_computers)) &
                (df['Year'].isin(selected_years)) 
                # &
                # (
                #       df['Error mitigation'].apply(
                #      lambda x: bool(set(x) & set(selected_errors)) if isinstance(x, list) else False
                #      )
                
                # )
            ]

        
        filtered_df = filtered_df.dropna(subset=[b_axis])

        

        

       

        # Assume filtered_df, y_axis, b_axis are already defined
        with col2:
        

            graph_df = filtered_df.copy()
            
            # if x_axis_scale == 'Log':
            #     graph_df['Number of qubits'] = np.log(graph_df['Number of qubits'].replace(0, np.nan).dropna())
            # if y_axis_scale == 'Log':
            #     graph_df[y_axis] = np.log(graph_df[y_axis].replace(0, np.nan).dropna())

            graph_df["Date"] = graph_df["Date"].astype(str)
            graph_df_numeric = graph_df.select_dtypes(include='number')
            graph_df[graph_df_numeric.columns] = graph_df_numeric.fillna(0)

            graph_df_category = graph_df.select_dtypes(exclude='number')
            graph_df[graph_df_category.columns] = graph_df_category.fillna('')

            

            x_index = graph_df.columns.get_loc("Number of qubits")
            y_index = graph_df.columns.get_loc(y_axis)

            
            graph_df["Comp_Inst"] = graph_df["Institution"] + " " + graph_df["Computer"]
            computers = list(graph_df["Comp_Inst"].unique())

            comp_index = graph_df.columns.get_loc("Comp_Inst")

            bubble_index = graph_df.columns.get_loc(b_axis)
            min_value = graph_df.iloc[:, bubble_index].min()
            max_value = graph_df.iloc[:, bubble_index].max()

            min_value = 0 if pd.isna(min_value) else min_value
            max_value = 0 if pd.isna(max_value) else max_value


            bubble_index = int(bubble_index)
            min_value = float(min_value) if min_value is not None else 0
            max_value = float(max_value) if max_value is not None else 0


            option = {
                "dataset": [
                    {"source": [graph_df.columns.tolist()] + graph_df.values.tolist()}
                ] + [
                    {"transform": {"type": "filter", "config": {"dimension": comp_index, "eq": i}}}
                    for i in computers
                ],
                "title": {
                    #"text": "Quantum Points",
                   # "subtext": "Please click on the datapoint you would like to update.",
                    #"sublink": "https://count.quops.com",
                    "left": "center"
                },
                "legend": {"data": computers, "bottom": 1},
                "tooltip": {"trigger": "item","confine":True,"appendToBody":True},
                "xAxis": {"type": "log" if x_axis_scale == "Log" else "value", "splitLine": {"lineStyle": {"type": "dashed"}},"min": 1,
                          "name": "Number of qubits",         
                          "nameLocation": "middle",          
                          "nameGap": 30 ,
                           "axisLabel": {
            "formatter": JsCode(
                # one-line JS required
                "function (val) { var e = Math.log10(val); var map = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹','-':'⁻'}; return '10' + e.toString().split('').map(function(c){return map[c]||c}).join(''); }"
            ).js_code if x_axis_scale == "Log" else "{value}"  # this makes labels show as powers of 10
        }
   },
                "yAxis": {"type": "log" if y_axis_scale == "Log" else "value", "splitLine": {"lineStyle": {"type": "dashed"}},"min": 1,
                          "name": y_axis,         
                         "nameLocation": "middle",          
                         "nameGap": 50 ,
                          "axisLabel": {
            "formatter": JsCode(
                # one-line JS required
                "function (val) { var e = Math.log10(val); var map = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹','-':'⁻'}; return '10' + e.toString().split('').map(function(c){return map[c]||c}).join(''); }"
            ).js_code if y_axis_scale == "Log" else "{value}"  # this makes labels show as powers of 10
        }
                    
                       
   },
                "visualMap": {
                    "show": False,
                    "dimension": bubble_index,
                    "min": min_value,
                    "max": max_value,
                    "seriesIndex": list(range(len(computers))),
                    "inRange": {"symbolSize": [50, 120]}
                },
                "series": [
                    {
                        "name": comp,
                        "type": "scatter",
                        "datasetIndex": idx + 1,  # important: dataset index matches filter
                        "encode": {"x": x_index, "y": y_index, "tooltip": [1, 2,4, 5,6,7,8,9,10,11,14]}
                    }
                    for idx, comp in enumerate(computers)
                ]
            }

            last_row = st.container()
            clicked_id = None
            
            
            clicked_id = st_echarts(
                option,
                events={
                    "click": "function(params) { return params.value[0]; }" ,
                    "dblclick": "function(params) { return params.value[1]; }" 

                },
                height="500px",
                key="global",
            )

            

            if clicked_id is not None and isinstance(clicked_id,int):
                st.session_state.clicked_id = clicked_id

            if clicked_id is not None and isinstance(clicked_id,int):
                # Inject CSS to make Streamlit button green
                st.markdown(
                    """
                    <style>
                     div.stButton > button:first-child {
                        background-color: #FF4B4B;
                        color: white;
                        border-radius: 5px;
                      
                    }
                    div.stButton > button:first-child:hover {
                        background-color: #45a049;
                        color: white;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True,
                )
                update_ref = graph_df.loc[graph_df["id"]==st.session_state.clicked_id,"Reference"].values[0]

                if last_row.button(f"Update data for reference {update_ref}"):
                    ts = int(time.time() * 1000)
                    html(f"<script>{switch(3)} // trigger for id {clicked_id} at {ts}</script>", height=0)
            elif clicked_id is not None and isinstance(clicked_id,str):
                st.components.v1.html(
                    f"""
                    <script>
                        window.open("{clicked_id}", "_blank");
                    </script>
                    """,
                    height=0
                )


            

            
            #st.write(clicked_id)
            #st.write(st.session_state.clicked_id)
            
            
            # if clicked_id is not None and isinstance(clicked_id,int) and st.session_state.visited==0 :
            #     st.session_state.clicked_id = clicked_id
            #     ts = int(time.time() * 1000)
                
            #     html(f"<script>{switch(3)} // trigger for id {clicked_id} at {ts}</script>", height=0)
            # elif  st.session_state.clicked_id != clicked_id and clicked_id is not None  and isinstance(clicked_id,int) :
            #     st.session_state.clicked_id = clicked_id
            #     ts = int(time.time() * 1000)  # current timestamp in ms
            #     html(f"<script>{switch(3)} // trigger for id {clicked_id} at {ts}</script>", height=0)
            # elif  isinstance(clicked_id,str) and is_hyperlink(clicked_id):
            #     st.components.v1.html(
            #         f"""
            #         <script>
            #             window.open("{clicked_id}", "_blank");
            #         </script>
            #         """,
            #         height=0
            #     )

            

            
         
    # === Tab 2: Dataset Overview ===
    # with tab3:
       
    #     st.header("Computer Overview")
    #     if os.getenv("DATA_SOURCE")=='sheet':     
    #         sheet_id = os.getenv('SHEET_ID')
    #         url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    #         df_comp = pd.read_excel(url,sheet_name= 1,header=1)
    #         df_comp.drop('Unnamed: 0',axis=1,inplace=True)
    #     else:  
    #         df_comp = load_comp_data_from_db()

        
    #     df_comp.fillna('',inplace=True)

    #     st.subheader("Quick Info")
    #     st.markdown(f"- **Rows:** {df_comp.shape[0]}")
    #     st.markdown(f"- **Columns:** {df_comp.shape[1]}")
    #     st.markdown(f"- **Columns:** {', '.join(df_comp.columns)}")

    #     st.subheader("Preview of Dataset")
    #     st.dataframe(df_comp)

    #     # Download button
    #     st.download_button("Download CSV", df_comp.to_csv(index=False), "dataset.csv", "text/csv")

    
    with tab3:

        #st.header("Submit Quantum Datapoint")

        
        # CAPTCHA Verification First
        if 'controllo' not in st.session_state:
            st.session_state['controllo'] = False
      
        if st.session_state['controllo'] == False:
            st.markdown("Confirm humanity")

            col1, col2 = st.columns([1, 1])

            if 'Captcha' not in st.session_state:
                st.session_state['Captcha'] = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length_captcha))

            image = ImageCaptcha(width=width, height=height)
            data = image.generate(st.session_state['Captcha'])
            col1.image(data)

            captcha_input = col2.text_area('Enter captcha text', height=30)

            if st.button("Verify"):
                if st.session_state['Captcha'].lower() == captcha_input.strip().lower():
                    del st.session_state['Captcha']
                    st.session_state['controllo'] = True
                    st.rerun()
                else:
                    st.error("🚨 Invalid Captcha")
                    del st.session_state['Captcha']
                    st.rerun()

            #st.stop()  # Stop here until CAPTCHA is verified

        # Only show the form if CAPTCHA passed
        
        elif st.session_state['controllo'] == True:
            st.markdown("""
            <style>
                /* Hide the default Streamlit label */
                label[for="reference_input"] {
                    display: none;
                }
                /* Make the custom label green */
                .green-label {
                    color: green;
                    font-weight:bold;

                }
                .black-label{
                    color:black;
                    
                }
            </style>
        """, unsafe_allow_html=True)
            with st.form("quantum_form") :
                st.markdown("Highlighted = required field")

                st.markdown('<div class="green-label">Reference</div>', unsafe_allow_html=True)
                reference = st.text_input(label='', key="reference_input", help = "The reference for the quantum computation, typically an arXiv or journal link")

                st.markdown('<div class="black-label">Experiment Date</div>', unsafe_allow_html=True)
                date = st.date_input("", value=datetime.today(), help="The date the experiment was performed or published (typically the date of the reference)")
                
                st.markdown('<div class="black-label">Computation (comma-separated list)</div>', unsafe_allow_html=True)
                computation_raw = st.text_area("", help="The algorithm used/computation performed, for example Trotter, VQE, Phase estimation")

                # st.markdown('<div class="black-label">Error Mitigation (comma-separated list)</div>', unsafe_allow_html=True)
                # error_mitigation_raw = st.text_area("", help="e.g. ZNE, Clifford Data Regression")

                st.markdown('<div class="green-label">Number of Qubits</div>', unsafe_allow_html=True)
                num_qubits_raw = st.text_input("", help = "Number of qubits used in the quantum computation")
                num_qubits = int(num_qubits_raw) if num_qubits_raw.strip().isdigit() else None

                st.markdown('<div class="black-label">Number of Two-Qubit Operations</div>', unsafe_allow_html=True)
                num_2q_gates_raw = st.text_input("", help = "Number of two-qubit operations used in the quantum computation")
                num_2q_gates = int(num_2q_gates_raw) if num_2q_gates_raw.strip().isdigit() else None

                st.markdown('<div class="black-label">Number of Single-Qubit Operations</div>', unsafe_allow_html=True)
                num_1q_gates_raw = st.text_input("", help = "Number of siingle-qubit operations used in the quantum computation")
                num_1q_gates = int(num_1q_gates_raw) if num_1q_gates_raw.strip().isdigit() else None

                st.markdown('<div class="black-label">Total Number of Operations</div>', unsafe_allow_html=True)
                total_gates_raw = st.text_input("",help = "Total number of operations used in the quantum computation, e.g. single-qubit operations + two-qubit operations")
                total_gates = int(total_gates_raw) if total_gates_raw.strip().isdigit() else None

                st.markdown('<div class="black-label">Circuit Depth</div>', unsafe_allow_html=True)
                circuit_depth_raw = st.text_input("", help = "The depth of the circuit in the quantum computation (see Circuit Depth Measure).")
                circuit_depth = int(circuit_depth_raw) if circuit_depth_raw.strip().isdigit() else None

                st.markdown('<div class="black-label">Circuit Depth Measure</div>', unsafe_allow_html=True)
                circuit_depth_measure = st.text_input("", help="The measure/metric used for circuit depth, for example two-qubit gate layers, Trotter step, etc. Number of two-qubit operations and/or total number of operations is preferred to this metric, and this should be used only when these are unknown. ")

                st.markdown('<div class="green-label">Institution</div>', unsafe_allow_html=True)
                institution = st.text_input("", help="Who owns the quantum computer, e.g. Google, Quantinuum, QuEra")
                
                st.markdown('<div class="green-label">Computer</div>', unsafe_allow_html=True)
                computer = st.text_input("", help="The name or other identifying label for the quantum computer")

                submit = st.form_submit_button("Submit")
          
                if st.session_state.get("submission_success"):
                    st.success("Quantum datapoint submitted successfully!")
                    del st.session_state["submission_success"]
                
                if submit:
                    if not reference:
                        st.error("Please fill out Reference(url or citation) as it is a required field. ")
                    if not num_qubits:
                        st.error("Please fill out Number of Qubits as it is a required field. ")
                    if not institution:
                        st.error("Please fill out Institution as it is a required field. ")
                    if not computer:
                        st.error("Please fill out Computer as it is a required field. ")
                    if not (num_2q_gates or total_gates):
                        st.error("Please fill either Number of two-Qubit operations or Total Number of Operations")
                    
                    #if reference and num_qubits and (num_2q_gates or total_gates):
                    else:
                        computation_list = [x.strip() for x in computation_raw.split(",") if x.strip()]
                        #error_mitigation_list = [x.strip() for x in error_mitigation_raw.split(",") if x.strip()]
                        success = insert_quantum_datapoint(
                            reference, date, computation_list, num_qubits, num_2q_gates, num_1q_gates, total_gates,
                            circuit_depth, circuit_depth_measure, institution, computer
                        )
                    
                        if success:
                            st.success("Quantum datapoint submitted successfully!")
                            #st.session_state['controllo'] = False
                            
                            st.session_state.submission_success = True
                            st.rerun()
                    


    
    with tab4:

        
        if st.session_state.clicked_id is None:
            st.subheader("Please provide the necessary details…")
            update_id = df.iloc[0]["id"]
        else:
            st.subheader("Please provide the necessary details…")
            update_id = st.session_state.clicked_id
            st.session_state.visited = 1
        
        
        record = df[df['id'] == update_id]

        if not record.empty:
        
            record = record.iloc[0]

            new_ref = st.text_input("Reference",value = record["Reference"],help = "The reference for the quantum computation, typically an arXiv or journal link")
            new_date = st.date_input("Date", value=record['Date'])
            new_qubits = st.number_input("Number of Qubits", value=int(record['Number of qubits']), help = "Number of qubits used in the quantum computation")

            try:
                num_2q_gates_raw = st.text_input("Number of Two-Qubit Gates", value=record['Number of two-qubit gates'], help = "Number of two-qubit operations used in the quantum computation")
                new_num_2q_gates = float(num_2q_gates_raw) if num_2q_gates_raw and not is_nan_or_nan_string(num_2q_gates_raw) else None
            except:
                st.error("Invalid input. Please input a valid number")
                

            try:
                num_1q_gates_raw = st.text_input("Number of Single-Qubit Gates", value=record['Number of single-qubit gates'], help = "Number of single-qubit operations used in the quantum computation")
                new_num_1q_gates = float(num_1q_gates_raw) if num_1q_gates_raw and not is_nan_or_nan_string(num_1q_gates_raw) else None
            except:
                st.error("Invalid input. Please input a valid number")
                

            try:
                total_gates_raw = st.text_input("Total number of gates", value=record['Total number of gates'], help = "Total number of operations used in the quantum computation, e.g. single-qubit operations + two-qubit operations")
                new_total_gates = float(total_gates_raw) if total_gates_raw and not is_nan_or_nan_string(total_gates_raw) else None
            except:
                st.error("Invalid input. Please input a valid number")
                
            try:
                circuit_depth_raw = st.text_input("Circuit depth", value=record['Circuit depth'], help = "The depth of the circuit in the quantum computation (see Circuit Depth Measure).")
                new_circuit_depth = float(circuit_depth_raw) if circuit_depth_raw and not is_nan_or_nan_string(circuit_depth_raw) else None
            except:
                st.error("Invalid input. Please input a valid number")
                
            new_circuit_depth_measure = st.text_input("Circuit depth measure", value=record['Circuit depth measure'], help="The measure/metric used for circuit depth, for example two-qubit gate layers, Trotter step, etc. Number of two-qubit operations and/or total number of operations is preferred to this metric, and this should be used only when these are unknown. ")
            new_institution = st.text_input("Institution", value=record['Institution'], help="Who owns the quantum computer, e.g. Google, Quantinuum, QuEra")
            new_computation = st.text_input("Computation", value=record['Computations'], help="e.g. QFT, Measurement")
            new_computer = st.text_input("Computer", value=record['Computer'], help="The name or other identifying label for the quantum computer")
            #new_mitigation = st.text_input("Error Mitigations", value=record['Error mitigations'], help="e.g. ZNE, Clifford Data Regression")
            new_feedback = st.text_input("Justification for changes", value=record['feedback'], help="Clear description of the changes made with justification. For example: “Changed the number of two-qubit operations from 512 to 1024. The correct number (1024 two-qubit operations) is stated in the caption of Figure 1 of the reference.")

            computation_list = [x.strip() for x in new_computation.split(",") if x.strip()]
            #error_mitigation_list = [x.strip() for x in new_mitigation.split(",") if x.strip()]

            # --- CAPTCHA ---
            col3, col4 = st.columns(2)

            if "update_captcha" not in st.session_state:
                st.session_state.update_captcha = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length_captcha))

            image1 = ImageCaptcha(width=width, height=height)
            data1 = image1.generate(st.session_state.update_captcha)
            col3.image(data1)

            captcha_input1 = col4.text_area('Enter the captcha text', height=30)

            if st.button("Verify humanity and submit"):
                if st.session_state.update_captcha.lower() == captcha_input1.strip().lower():
                    if not new_ref:
                        st.error("Please fill out Reference(url or citation) as it is a required field. ")
                    if not new_qubits:
                        st.error("Please fill out Number of Qubits as it is a required field. ")
                    if not (new_num_2q_gates or new_total_gates):
                        st.error("Please fill either Number of two-Qubit operations or Total Number of Operations")
                    if not new_institution:
                        st.error("Please fill out Institution as it is a required field. ")
                    if not new_computer:
                        st.error("Please fill out Computer as it is a required field. ")
                    if not new_feedback:
                        st.error("Please fill out Justification for changes as it is a required field. ")
                    
                    #if reference and num_qubits and (num_2q_gates or total_gates):
                    else:
                        conn = get_connection()
                        cursor = conn.cursor()
                        status = "UPDATE REQUESTED"

                        cursor.execute("""
                            INSERT INTO quant_data (
                                reference, date, computation,
                                num_qubits, num_2q_gates, num_1q_gates, total_gates,
                                circuit_depth, circuit_depth_measure,
                                institution, computer, status, feedback
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            new_ref,
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
# if st.session_state.logged_in == 'refresh':
#     #show_user_app()
#     show_login_form()
if st.session_state.logged_in == 'app':
    #show_user_app()
    show_login_form()
elif st.session_state.logged_in == 'admin':
    admin_interface()
else:
    show_login_form()


