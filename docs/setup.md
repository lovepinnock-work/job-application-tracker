# Setup

## Requirements
- Python 3.9+
- Gmail API access
- Google Sheets API access
- Gemini API key
- A Google Sheet with the required tabs

## Google Sheets tabs

Create these tabs:

- Applications
- Events
- EventApplications
- ReviewQueue

## Environment

Create a .env file from .env.example.

Example:

```code
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

GOOGLE_SHEETS_SPREADSHEET_ID=your_google_sheet_id_here
GOOGLE_APPLICATION_CREDENTIALS=service_account.json
``` 
## Install dependencies
```
pip install -r requirements.txt
```

## Run in test mode

Use local fixture emails in test_emails/ to validate extraction and reconciliation before touching live Gmail.

## Run in Gmail mode

Use Gmail polling mode once OAuth is configured and the spreadsheet is ready.
Use task scheduler or equivalent to run on a schedule:
- Polling every 30 minutes
- Processing every 2-4 hours

For additional details, see:
- [Demo](demo-walkthrough.md)
- [Architecture](architecture.md)
- [Data Model](data-model.md)