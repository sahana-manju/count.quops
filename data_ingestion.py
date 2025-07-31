# Import necessary libraries
import pandas as pd
import numpy as np
import logging
from collections import defaultdict
import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import connection as PGConnection

load_dotenv()

# Setting up Database connection
conn = psycopg2.connect(
    host="localhost",
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    port="5432"
)

# Setting up logger object for console logging
logger = logging.getLogger("data_ingestion")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

# Function to load data from Excel sheet
def load_data_from_sheet(sheet_id: str)->pd.DataFrame:
    """
    Loading data from google sheet url
    """
    try:
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
        df = pd.read_excel(url,header=[0,1]) # loading multilevel headers
    
        # Removing unnamed portion of headers
        df.columns = [
        second
        for first, second in df.columns
        ]
        
        logger.debug('Data Loaded successfully')
        return df
         
    except Exception as e:
        logger.error('Unexpected Exception: % s',e)
        raise

# Function to handle duplicate column entries        
def handle_duplicate_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Handles duplicate column names in a DataFrame by renaming them to make them unique.

    For example, if 'ColumnA' appears three times, the output will be:
    ['ColumnA', 'ColumnA_1', 'ColumnA_2']

    Args:
        df (pd.DataFrame): The input DataFrame which may contain duplicate columns.

    Returns:
        tuple: A tuple containing:
            - pd.DataFrame: The DataFrame with renamed columns.
            - list[str]: A list of original duplicate column names.
    """
    try:
        # Identify duplicated columns
        duplicated = df.columns[df.columns.duplicated()].tolist()
        repeated_columns = list(set(duplicated))

        seen = defaultdict(int)
        new_columns = []

        for col in df.columns:
            count = seen[col]
            new_col = col if count == 0 else f"{col}_{count}"
            new_columns.append(new_col)
            seen[col] += 1

        df.columns = new_columns
        logger.debug('Duplicate columns handled successfully')

        return df, repeated_columns

    except Exception as e:
        logger.error('Error while handling duplicate columns: %s', e)
        raise

# Function for Feature Engineering
def add_custom_columns(df: pd.DataFrame, repeated_columns: list[str]) -> pd.DataFrame:
    """
    Adds custom columns to the DataFrame by:
    - Extracting the year from a 'Date' column.
    - Combining values from duplicate columns (e.g., 'Name', 'Name_1', 'Name_2') into a new column.

    Args:
        df (pd.DataFrame): The input DataFrame.
        repeated_columns (List[str]): A list of base names of duplicated columns.

    Returns:
        pd.DataFrame: The updated DataFrame with additional custom columns.
    """
    try:
        # Extract year from 'Date' column
        df['Year'] = pd.to_datetime(df['Date'], errors='coerce').dt.year
        logger.debug("Year column created from 'Date'")

        final_dict = {}

        # Group duplicated columns by base name
        for rcol in repeated_columns:
            final_dict[rcol] = [col for col in df.columns if col == rcol or col.startswith(f"{rcol}_")]

        # Create combined columns
        for base_col, columns_to_combine in final_dict.items():
            new_col_name = f"{base_col}s" if not base_col.endswith('s') else f"{base_col}_combined"
            df[new_col_name] = df[columns_to_combine].apply(
                lambda row: ', '.join(row.dropna().astype(str)), axis=1
            )
            logger.debug("Created combined column ")

        logger.debug("Custom columns added successfully.")
        return df

    except Exception as e:
        logger.error("Failed to add custom columns: %s", e)
        raise
        pass

# Function for missing columns imputation
def rename_missing_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and standardizes specific columns in the DataFrame:
    - Strips whitespace from 'Institution' and fills missing values with 'Unnamed'.
    - Fills missing values in 'Computer' with 'Unnamed'.
    - Fills missing values in 'Error mitigation' and its duplicate columns with 'No Data'.

    Args:
        df (pd.DataFrame): The input DataFrame to clean.

    Returns:
        pd.DataFrame: The cleaned DataFrame with updated column values.
    """
    try:
        # Clean 'Institution' column
        df['Institution'] = df['Institution'].str.strip()
        df['Institution'] = df['Institution'].fillna('Unnamed')
        logger.debug("Cleaned 'Institution' column.")

        # Clean 'Computer' column
        df['Computer'] = df['Computer'].fillna('Unnamed')
        logger.debug("Filled missing values in 'Computer' column.")

        # Fill missing values for 'Error mitigation' and its variants
        base_col = 'Error mitigation'
        for col in df.columns:
            if col == base_col or col.startswith(f'{base_col}_'):
                df[col] = df[col].fillna('No Data')
        logger.debug("Filled missing values in Error mitigation related columns.")

        return df

    except Exception as e:
        logger.error("Error while renaming/cleaning columns: %s", e)
        raise

def load_data_from_db(conn: PGConnection)->pd.DataFrame:
    query = "SELECT * FROM quant_data where status = 'APPROVED';"
    df_comp = pd.read_sql_query(query, conn)
    return df_comp

def load_comp_data_from_db()->pd.DataFrame:
    conn = psycopg2.connect(
                host="localhost",
                database=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                port="5432"
            )
    
    query = "SELECT * FROM quantum_computers;"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def clean_error_mitigation(x):
    if isinstance(x, (list, tuple, np.ndarray)) and len(x) == 0:
        return 'No Data'
    if isinstance(x, str) and x.strip() in ('', '[]'):
        return 'No Data'
    return x

def transform_db_data(df: pd.DataFrame)->pd.DataFrame:

    # Feature Engineering
    df['Computations'] = df['computation'].apply(
    lambda x: ', '.join(x) if isinstance(x, list) else ''
    )
    df['Error mitigations'] = df['error_mitigation'].apply(
    lambda x: ', '.join(x) if isinstance(x, list) else ''
    )
    df['Year'] = pd.to_datetime(df['date'], errors='coerce').dt.year

    # Imputing missing values
    df['institution'] = df['institution'].astype(str).str.strip()
    df['institution'] = df['institution'].replace('', np.nan).fillna('Unnamed')

    df['computer'] = df['computer'].astype(str).str.strip()
    df['computer'] = df['computer'].replace('', np.nan).fillna('Unnamed')

    df['institution'] = df['institution'].astype(str).str.strip()
    df['institution'] = df['institution'].replace('', np.nan).fillna('Unnamed')

    df['error_mitigation'] = df['error_mitigation'].apply(
    lambda x: ['No Data'] if isinstance(x, list) and len(x) == 0 else x
    )

    # Handle error_mitigation: Replace NaN or empty lists with 'No Data'
    df['Error mitigations'] = df['Error mitigations'].apply(clean_error_mitigation)

    # Rename columns
    df = df.rename(columns={
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
    'error_mitigation':'Error mitigation',
    })

    return df

def load_transform_data(data_source : str)->pd.DataFrame:
    """
    Main function to call the above functions in an order to clean the data
    """
    if data_source == "sheet":
        sheet_id = os.getenv('SHEET_ID')
        df = load_data_from_sheet(sheet_id)
        df, repeated_columns = handle_duplicate_columns(df)
        df = add_custom_columns(df,repeated_columns)
        df = rename_missing_data(df)
        return df
    else:
        conn = psycopg2.connect(
        host="localhost",
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port="5432"
    )
        
        df = load_data_from_db(conn)
        df = transform_db_data(df)
        conn.close()
        return df

#load_transform_data('db')


    

    
    