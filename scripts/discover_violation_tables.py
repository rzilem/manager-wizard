"""
Discover tables in PSPM Violation Report using Power BI REST API.
"""
import json
import requests
import msal

# Load config
config_path = r'C:\Users\ricky\OneDrive - PS Prop Mgmt\Documents\GitHub\board-weekly-updates\config.json'
with open(config_path) as f:
    config = json.load(f)

pbi = config['power_bi']

# Get Power BI token
app = msal.ConfidentialClientApplication(
    pbi['client_id'],
    authority=f"https://login.microsoftonline.com/{pbi['tenant_id']}",
    client_credential=pbi['client_secret']
)
result = app.acquire_token_for_client(
    scopes=["https://analysis.windows.net/powerbi/api/.default"]
)
token = result['access_token']
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

workspace_id = "c5395f33-bd22-4d26-846f-5ad44c7ad108"
dataset_id = "0d7d34b1-71c8-45f1-8224-01c4f8c1efd9"

print("=" * 70)
print("PSPM VIOLATION REPORT - Dataset Discovery")
print("=" * 70)

# Method 1: Get dataset details
print("\n[1] Dataset Details:")
resp = requests.get(
    f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}",
    headers=headers
)
if resp.status_code == 200:
    ds = resp.json()
    print(f"    Name: {ds.get('name')}")
    print(f"    Configured By: {ds.get('configuredBy')}")
    print(f"    Is Refreshable: {ds.get('isRefreshable')}")
    print(f"    Is On-Prem Gateway Required: {ds.get('isOnPremGatewayRequired')}")
else:
    print(f"    Error: {resp.status_code}")

# Method 2: Get datasources (might reveal table info)
print("\n[2] Data Sources:")
resp = requests.get(
    f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/datasources",
    headers=headers
)
if resp.status_code == 200:
    sources = resp.json().get('value', [])
    for src in sources:
        print(f"    Type: {src.get('datasourceType')}")
        details = src.get('connectionDetails', {})
        print(f"    Server: {details.get('server', 'N/A')}")
        print(f"    Database: {details.get('database', 'N/A')}")
        print(f"    URL: {details.get('url', 'N/A')}")
else:
    print(f"    Error: {resp.status_code} - {resp.text[:200]}")

# Method 3: Get tables via dataset/tables endpoint (newer API)
print("\n[3] Tables (REST API):")
resp = requests.get(
    f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/tables",
    headers=headers
)
if resp.status_code == 200:
    tables = resp.json().get('value', [])
    print(f"    Found {len(tables)} tables:")
    for t in tables:
        print(f"    - {t.get('name')}")
else:
    print(f"    Error: {resp.status_code}")
    # This endpoint only works for push datasets, try alternative

# Method 4: Try to get report pages and visuals (might reveal table names)
print("\n[4] Report Pages and Visuals:")
report_id = "97a64eee-0298-4d42-a058-60911a75fe82"
resp = requests.get(
    f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report_id}/pages",
    headers=headers
)
if resp.status_code == 200:
    pages = resp.json().get('value', [])
    print(f"    Found {len(pages)} pages:")
    for p in pages:
        print(f"    - {p.get('displayName')} (order: {p.get('order')})")
else:
    print(f"    Error: {resp.status_code}")

# Method 5: Try refresh history (might reveal tables)
print("\n[5] Refresh History:")
resp = requests.get(
    f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/refreshes?$top=5",
    headers=headers
)
if resp.status_code == 200:
    refreshes = resp.json().get('value', [])
    print(f"    Last {len(refreshes)} refreshes:")
    for r in refreshes:
        print(f"    - {r.get('startTime')} | {r.get('status')} | {r.get('refreshType')}")
else:
    print(f"    Error: {resp.status_code}")

# Method 6: Try different DAX queries for table discovery
print("\n[6] DAX Table Discovery Attempts:")

def try_dax(query, label):
    resp = requests.post(
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/executeQueries",
        headers=headers,
        json={'queries': [{'query': query}], 'serializerSettings': {'includeNulls': True}}
    )
    if resp.status_code == 200:
        rows = resp.json()['results'][0]['tables'][0]['rows']
        return rows
    else:
        return None

# Try various table name patterns based on Vantaca naming
vantaca_patterns = [
    "vwOpenViolation",
    "vwClosedViolation",
    "OpenViolation",
    "ClosedViolation",
    "Violation",
    "ViolationRaw",
    "Open Violation",
    "Closed Violation",
    "tblViolation",
    "CurrentStatus",
    "vw_Open_Violation",
    "vw_Closed_Violation"
]

for table in vantaca_patterns:
    # Try to get just one row
    query = f"EVALUATE ROW(\"test\", COUNTROWS('{table}'))"
    rows = try_dax(query, table)
    if rows:
        count = list(rows[0].values())[0]
        print(f"    FOUND: '{table}' has {count} rows")
    else:
        # Try without quotes around table name for single-word tables
        if " " not in table:
            query = f"EVALUATE ROW(\"test\", COUNTROWS({table}))"
            rows = try_dax(query, table)
            if rows:
                count = list(rows[0].values())[0]
                print(f"    FOUND: {table} (unquoted) has {count} rows")

print("\n" + "=" * 70)
print("DONE - If no tables found, table names may need to be found in Power BI Desktop")
print("=" * 70)
