"""
Check Power BI PSPM Violation Report for property-level data.
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

def run_dax(query, workspace_id, dataset_id, label=""):
    """Execute DAX query."""
    resp = requests.post(
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/executeQueries",
        headers=headers,
        json={'queries': [{'query': query}], 'serializerSettings': {'includeNulls': True}}
    )
    if resp.status_code == 200:
        return resp.json()['results'][0]['tables'][0]['rows']
    else:
        print(f"    [{label}] Error {resp.status_code}")
        return []

print("=" * 70)
print("PSPM VIOLATION REPORT - Finding Dataset and Tables")
print("=" * 70)

# From the URL: workspace c5395f33-bd22-4d26-846f-5ad44c7ad108, report 97a64eee-0298-4d42-a058-60911a75fe82
workspace_id = "c5395f33-bd22-4d26-846f-5ad44c7ad108"
report_id = "97a64eee-0298-4d42-a058-60911a75fe82"

# Get report details to find dataset
print(f"\n[1] Getting report details...")
resp = requests.get(
    f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report_id}",
    headers=headers
)
if resp.status_code == 200:
    report = resp.json()
    print(f"    Report Name: {report.get('name')}")
    dataset_id = report.get('datasetId')
    print(f"    Dataset ID: {dataset_id}")
else:
    print(f"    Error getting report: {resp.status_code}")
    dataset_id = None

if not dataset_id:
    print("\n[1b] Listing all datasets in workspace...")
    resp = requests.get(
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets",
        headers=headers
    )
    if resp.status_code == 200:
        datasets = resp.json().get('value', [])
        for ds in datasets:
            print(f"    - {ds['name']}: {ds['id']}")
            if 'violation' in ds['name'].lower():
                dataset_id = ds['id']
                print(f"      ^ Using this one!")

if dataset_id:
    print(f"\n[2] Searching for tables in dataset {dataset_id}...")

    # Try various table name patterns
    table_names = [
        "Open Violation Raw",
        "Closed Violation Raw",
        "OpenViolationRaw",
        "ClosedViolationRaw",
        "Open Violations",
        "Closed Violations",
        "Violation",
        "Violations",
        "ViolationData",
        "vwOpenViolations",
        "vwClosedViolations",
    ]

    found = False
    for table in table_names:
        query = f"EVALUATE TOPN(1, '{table}')"
        rows = run_dax(query, workspace_id, dataset_id, table)
        if rows:
            found = True
            cols = list(rows[0].keys())
            print(f"\n    FOUND: '{table}' - {len(cols)} columns")

            # Look for property columns
            property_cols = [c for c in cols if any(x in c.lower() for x in
                ['owner', 'property', 'address', 'prop', 'lot', 'unit', 'account', 'acct'])]

            if property_cols:
                print(f"    >>> PROPERTY COLUMNS: {property_cols}")

            print(f"    All columns:")
            for c in sorted(cols):
                print(f"        {c}")

            # Show sample data
            print(f"\n    Sample row values:")
            for k, v in rows[0].items():
                if v:
                    val_str = str(v)[:60]
                    print(f"        {k}: {val_str}")

    if not found:
        print("\n    No violation tables found with common names.")
        print("    Let me try to discover tables...")

        # Try INFO.TABLES() to list tables
        query = "EVALUATE INFO.TABLES()"
        rows = run_dax(query, workspace_id, dataset_id, "INFO.TABLES")
        if rows:
            print("\n    Tables in dataset:")
            for row in rows:
                for k, v in row.items():
                    if 'name' in k.lower() and v:
                        print(f"        - {v}")

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)
