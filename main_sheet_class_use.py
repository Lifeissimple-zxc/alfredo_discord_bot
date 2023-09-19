import asyncio

from alfredo_lib.gateways import google_sheets_gateway

sheets = google_sheets_gateway.GoogleSheetAsyncGateway(
    service_acc_path="secrets/google.json"
)

SAMPLE_SPREADSHEET_ID = "1x_8Jq6difcp606OQUJuvO8NpE5r7yl5GfJeY7boDeGo" 
SAMPLE_RANGE_NAME = "test!A1:B2"

async def main():
    await   sheets.discover_sheet_service(api_version="v4")
    sheet_data = await sheets.get_sheet_data(sheet_id=SAMPLE_SPREADSHEET_ID)
    print(sheet_data)

loop = asyncio.get_event_loop()

loop.run_until_complete(main())