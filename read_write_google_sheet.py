from gspread_dataframe import set_with_dataframe, get_as_dataframe
import gspread
import pandas as pd
import os
import base64
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials


def get_credentials():
    """Decode the base64 key from env variable and return Credentials object."""
    key_base64 = os.environ["GOOGLE_AUTH"]
    key_json = base64.b64decode(key_base64).decode("utf-8")
    
    temp_key_path = "temp_gcp_key.json"
    with open(temp_key_path, "w") as f:
        f.write(key_json)

    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(temp_key_path, scopes=scopes)
    return creds


def read_google_sheet(sheet_id):   
    creds = get_credentials()
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).sheet1
    sheet_data = sheet.get_all_values()
    data = pd.DataFrame(sheet_data[1:], columns=sheet_data[0])  # skip header row
    return data


def write_to_google_sheet(df, sheet_id, mode='append'):
    creds = get_credentials()
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).sheet1

    if mode == 'overwrite':
        sheet.clear()
        set_with_dataframe(sheet, df, include_index=True, include_column_header=True)
        print("Data written (overwritten) to Google Sheet successfully.")
    elif mode == 'append':
        existing_data = get_as_dataframe(sheet, evaluate_formulas=True)
        non_empty_rows = existing_data.dropna(how='all').shape[0]
        next_row = non_empty_rows + 2
        set_with_dataframe(sheet, df, row=next_row, include_column_header=False)
        print("Data appended to Google Sheet successfully.")


def write_new_google_sheet_to_folder(df, sheet_title, folder_id):
    creds = get_credentials()
    client = gspread.authorize(creds)

    spreadsheet = client.create(sheet_title)
    spreadsheet.share('todaysprice-506@todaysprice.iam.gserviceaccount.com', perm_type='user', role='writer')

    drive_service = build('drive', 'v3', credentials=creds)
    file_id = spreadsheet.id

    current_parents = drive_service.files().get(fileId=file_id, fields='parents').execute().get('parents', [])

    drive_service.files().update(
        fileId=file_id,
        addParents=folder_id,
        removeParents=",".join(current_parents),
        fields='id, parents'
    ).execute()

    sheet = spreadsheet.sheet1
    set_with_dataframe(sheet, df, include_column_header=True)

    print(f"Sheet '{sheet_title}' created and moved to folder successfully.")
    print(f"URL: {spreadsheet.url}")
