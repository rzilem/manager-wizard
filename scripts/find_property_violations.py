"""
Find property-level violation data from all available sources.
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

def run_dax(workspace_id, dataset_id, query, label=""):
    """Execute DAX query and return rows."""
    resp = requests.post(
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/executeQueries",
        headers=headers,
        json={'queries': [{'query': query}], 'serializerSettings': {'includeNulls': True}}
    )
    if resp.status_code == 200:
        return resp.json()['results'][0]['tables'][0]['rows']
    else:
        return None

# Violation Report dataset
violation_workspace = "c5395f33-bd22-4d26-846f-5ad44c7ad108"
violation_dataset = "0d7d34b1-71c8-45f1-8224-01c4f8c1efd9"

# Manager360/KPI datasets (from board-weekly-updates config)
manager_workspace = "c5395f33-bd22-4d26-846f-5ad44c7ad108"
manager_dataset = "e17e4241-37b7-4d12-a2e8-8f4e6148ca03"  # M360 dataset

kpi_workspace = "7def987c-e21b-4349-ac0f-731a4cf542d9"
kpi_dataset = "1d0f8dce-cebc-4a87-9d4a-32aa04af03c7"  # KPI dataset

print("=" * 70)
print("FINDING PROPERTY-LEVEL VIOLATION DATA")
print("=" * 70)

# 1. Check ActionItemDetails in Manager360 for violations with owner info
print("\n[1] ActionItemDetails (Manager360) - Looking for Violation Types with Owner Data:")

# First get a sample row
rows = run_dax(manager_workspace, manager_dataset,
    "EVALUATE TOPN(1, ActionItemDetails)", "ActionItemDetails sample")
if rows:
    cols = list(rows[0].keys())
    print(f"    Found {len(cols)} columns")

    # Property columns
    property_cols = [c for c in cols if any(x in c.lower() for x in
        ['owner', 'address', 'account', 'acct', 'prop', 'lot', 'unit'])]
    print(f"\n    PROPERTY COLUMNS: {property_cols}")

    # Check for violation-related columns
    vio_cols = [c for c in cols if any(x in c.lower() for x in
        ['violation', 'type', 'status', 'descr'])]
    print(f"    VIOLATION COLUMNS: {vio_cols}")

    print(f"\n    All columns:")
    for c in sorted(cols):
        print(f"        {c}")

# 2. Check if ActionItemDetails has owner/property info for violations
print("\n[2] ActionItemDetails - Violation Records with Owner Info:")
query = """
EVALUATE
TOPN(5,
    FILTER(ActionItemDetails,
        SEARCH("violation", ActionItemDetails[ai_TypeDescr], 1, 0) > 0
    )
)
"""
rows = run_dax(manager_workspace, manager_dataset, query, "Violation filter")
if rows:
    print(f"    Found violation records with these fields:")
    for i, row in enumerate(rows[:2]):
        print(f"\n    Record {i+1}:")
        for k, v in row.items():
            if v:
                val_str = str(v)[:60]
                print(f"        {k}: {val_str}")
else:
    print("    No violation records found or query failed")

# 3. Try to find Owner table relationships
print("\n[3] Looking for Owner Tables:")
owner_tables = ["Owner", "Owners", "vwOwner", "OwnerData", "vOwner", "Owner Master"]
for table in owner_tables:
    rows = run_dax(manager_workspace, manager_dataset,
        f"EVALUATE TOPN(1, '{table}')", table)
    if rows:
        cols = list(rows[0].keys())
        print(f"\n    FOUND: '{table}' with {len(cols)} columns")
        print(f"    Sample columns: {cols[:10]}")

# 4. Check XN field in CurrentStatus - might link to ActionItemDetails
print("\n[4] Checking XN (Transaction Number) Linkage:")
print("    CurrentStatus has XN field - checking if it links to ActionItemDetails...")
rows = run_dax(violation_workspace, violation_dataset,
    "EVALUATE TOPN(1, CurrentStatus)", "XN check")
if rows:
    xn = rows[0].get('CurrentStatus[XN]')
    print(f"    Sample XN: {xn}")

    # Try to find this XN in ActionItemDetails
    query = f"""
    EVALUATE
    FILTER(ActionItemDetails,
        ActionItemDetails[XN] = {xn}
    )
    """
    linked = run_dax(manager_workspace, manager_dataset, query, f"XN {xn}")
    if linked:
        print(f"    FOUND LINKED RECORD in ActionItemDetails!")
        for k, v in linked[0].items():
            if v:
                print(f"        {k}: {str(v)[:50]}")

# 5. List all tables in Manager360 dataset
print("\n[5] Tables in Manager360 Dataset:")
common_tables = [
    "ActionItemDetails", "CurrentStatus", "AssocData", "Association",
    "Owner", "OwnerLedger", "vOwnerLedger", "vOwnerLedger2",
    "FinancialGL", "Budget", "WorkOrder", "Violation"
]
for table in common_tables:
    rows = run_dax(manager_workspace, manager_dataset,
        f"EVALUATE ROW(\"count\", COUNTROWS('{table}'))", table)
    if rows:
        count = list(rows[0].values())[0]
        print(f"    {table}: {count:,} rows")

# 6. List all tables in KPI dataset
print("\n[6] Tables in KPI Dataset:")
for table in common_tables:
    rows = run_dax(kpi_workspace, kpi_dataset,
        f"EVALUATE ROW(\"count\", COUNTROWS('{table}'))", table)
    if rows:
        count = list(rows[0].values())[0]
        print(f"    {table}: {count:,} rows")

# 7. Check ActionItemDetails in both datasets for owner columns
print("\n[7] ActionItemDetails Columns Check:")
for name, ws, ds in [("M360", manager_workspace, manager_dataset),
                      ("KPI", kpi_workspace, kpi_dataset)]:
    rows = run_dax(ws, ds, "EVALUATE TOPN(1, ActionItemDetails)", f"{name} ActionItemDetails")
    if rows:
        cols = list(rows[0].keys())
        print(f"\n    {name} ActionItemDetails - {len(cols)} columns:")
        # Look for owner/property columns
        owner_cols = [c for c in cols if any(x in c.lower() for x in
            ['owner', 'address', 'account', 'acct', 'prop', 'lot', 'unit'])]
        if owner_cols:
            print(f"    OWNER/PROPERTY COLUMNS: {owner_cols}")
        # Show all columns
        for c in sorted(cols)[:20]:
            print(f"        {c}")

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)
