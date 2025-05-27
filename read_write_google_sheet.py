
from gspread_dataframe import set_with_dataframe, get_as_dataframe
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from googleapiclient.discovery import build
import os

def read_google_sheet(sheet_id):   
    spreadsheet_id = sheet_id
    # Define the scope
    scope = ["https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"]

    # Provide path to your downloaded JSON credentials
    creds = ServiceAccountCredentials.from_json_keyfile_name("todaysprice-6803a237d35c.json", scope)
    # Authorize the client
    client = gspread.authorize(creds)
    # Open your Google Sheet by name or by URL
    sheet = client.open_by_key(spreadsheet_id).sheet1
    sheet_data = sheet.get_all_values()
    data = pd.DataFrame(sheet_data[1:], columns=sheet_data[0])  # skip header row
    return data


def write_to_google_sheet(df, sheet_id, mode='append'):
    # Define the scope
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]

    # Provide path to your downloaded JSON credentials
    creds = ServiceAccountCredentials.from_json_keyfile_name("todaysprice-6803a237d35c.json", scope)
    # Authorize the client
    client = gspread.authorize(creds)
    
    # Access the sheet
    sheet = client.open_by_key(sheet_id).sheet1

    if mode == 'overwrite':
        sheet.clear()  # Clear existing content
        set_with_dataframe(sheet, df, include_index = True, include_column_header=True)
        print("Data written (overwritten) to Google Sheet successfully.")
    
    elif mode == 'append':
        existing_data = get_as_dataframe(sheet, evaluate_formulas=True)
        non_empty_rows = existing_data.dropna(how='all').shape[0]
        next_row = non_empty_rows + 2  # account for header and indexing

        set_with_dataframe(sheet, df, row=next_row, include_column_header=False)
        print("Data appended to Google Sheet successfully.")



def write_new_google_sheet_to_folder(df, sheet_title, folder_id):
    """
    Creates a new Google Sheet, writes the DataFrame to it, and moves it to the specified folder.
    
    Args:
        df (pd.DataFrame): The data to write.
        sheet_title (str): The title of the new Google Sheet.
        folder_id (str): The ID of the Google Drive folder to place the sheet into.
    """
    # Define the scope
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    # Provide path to your JSON credentials
    creds = ServiceAccountCredentials.from_json_keyfile_name("todaysprice-6803a237d35c.json", scope)
    client = gspread.authorize(creds)

    # Create a new spreadsheet
    spreadsheet = client.create(sheet_title)
    spreadsheet.share('todaysprice-506@todaysprice.iam.gserviceaccount.com', perm_type='user', role='writer')

    # Move the spreadsheet to the specified folder
    drive_service = build('drive', 'v3', credentials=creds)
    file_id = spreadsheet.id

    # Get current parent folders
    current_parents = drive_service.files().get(fileId=file_id, fields='parents').execute().get('parents', [])

    # Move to target folder
    drive_service.files().update(
        fileId=file_id,
        addParents=folder_id,
        removeParents=",".join(current_parents),
        fields='id, parents'
    ).execute()

    # Write the DataFrame
    sheet = spreadsheet.sheet1
    set_with_dataframe(sheet, df, include_column_header=True)

    print(f"Sheet '{sheet_title}' created and moved to folder successfully.")
    print(f"URL: {spreadsheet.url}")

