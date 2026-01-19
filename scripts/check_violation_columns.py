"""
Check CurrentStatus columns and find violation tables with property linkage.
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

def run_dax(query, label=""):
    """Execute DAX query and return rows."""
    resp = requests.post(
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/executeQueries",
        headers=headers,
        json={'queries': [{'query': query}], 'serializerSettings': {'includeNulls': True}}
    )
    if resp.status_code == 200:
        return resp.json()['results'][0]['tables'][0]['rows']
    else:
        print(f"    [{label}] Error {resp.status_code}: {resp.text[:200]}")
        return []

print("=" * 70)
print("VIOLATION DATA - Column Analysis")
print("=" * 70)

# 1. Check CurrentStatus columns and sample data
print("\n[1] CurrentStatus Table - Columns and Sample:")
rows = run_dax("EVALUATE TOPN(1, CurrentStatus)", "CurrentStatus sample")
if rows:
    cols = list(rows[0].keys())
    print(f"    Found {len(cols)} columns:")

    # Look for property-related columns
    property_cols = [c for c in cols if any(x in c.lower() for x in
        ['owner', 'property', 'address', 'prop', 'lot', 'unit', 'account', 'acct', 'ownerid'])]

    if property_cols:
        print(f"\n    PROPERTY COLUMNS FOUND:")
        for c in property_cols:
            print(f"        {c}")

    print(f"\n    All columns:")
    for c in sorted(cols):
        print(f"        {c}")

    print(f"\n    Sample values:")
    for k, v in rows[0].items():
        if v:
            val_str = str(v)[:60]
            print(f"        {k}: {val_str}")

# 2. Try table names with variations
print("\n[2] Trying Various Table Names:")
table_variations = [
    # Note the page name was " Open Violation Raw" with leading space
    " Open Violation Raw",
    "Open Violation Raw",
    "OpenViolationRaw",
    " Closed Violation Raw",
    "Closed Violation Raw",
    "ClosedViolationRaw",
    "Open Violation",
    "Closed Violation",
    "vwOpenViolation",
    "vwClosedViolation",
    # Vantaca SQL views often have these patterns
    "vw_Open_Violations",
    "vw_Closed_Violations",
    "OpenViolations",
    "ClosedViolations"
]

for table in table_variations:
    query = f"EVALUATE TOPN(1, '{table}')"
    rows = run_dax(query, table)
    if rows:
        cols = list(rows[0].keys())
        print(f"\n    FOUND: '{table}'")
        print(f"    Columns: {len(cols)}")

        # Look for property columns
        property_cols = [c for c in cols if any(x in c.lower() for x in
            ['owner', 'property', 'address', 'prop', 'lot', 'unit', 'account', 'acct', 'ownerid'])]
        if property_cols:
            print(f"    PROPERTY COLUMNS: {property_cols}")

        print(f"    Sample row:")
        for k, v in rows[0].items():
            if v:
                val_str = str(v)[:50]
                print(f"        {k}: {val_str}")

# 3. Check if CurrentStatus has enough data for our needs
print("\n[3] CurrentStatus - Count by Status Type:")
query = """
EVALUATE
SUMMARIZECOLUMNS(
    CurrentStatus[CurrentStatus],
    "Count", COUNTROWS(CurrentStatus)
)
"""
rows = run_dax(query, "Status Summary")
if rows:
    for row in rows:
        status = row.get('CurrentStatus[CurrentStatus]', 'Unknown')
        count = row.get('[Count]', 0)
        print(f"    {status}: {count}")

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)
