"""
Check Power BI schema for violation tables to find property-level linkage.
Deep dive into all available tables and datasets.
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
        print(f"    [{label}] Error {resp.status_code}: {resp.text[:300]}")
        return []

def get_tables(workspace_id, dataset_id):
    """Get list of tables in a dataset."""
    resp = requests.get(
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/tables",
        headers=headers
    )
    if resp.status_code == 200:
        return [t['name'] for t in resp.json().get('value', [])]
    return []

print("=" * 70)
print("DEEP DIVE: Finding Property-Level Violation Data")
print("=" * 70)

# List all datasets we have access to
datasets = [
    ("M360", pbi['m360_workspace_id'], pbi['m360_dataset_id']),
    ("Violations", pbi['m360_workspace_id'], pbi.get('violation_dataset_id', '')),
    ("KPI", pbi['kpi_workspace_id'], pbi['kpi_dataset_id']),
]

print("\n[1] Checking available tables in each dataset...")
for name, ws, ds in datasets:
    if not ds:
        continue
    print(f"\n    {name} Dataset ({ds[:8]}...):")

    # Try to list tables via API
    tables = get_tables(ws, ds)
    if tables:
        for t in tables:
            print(f"        - {t}")
    else:
        print("        (Table list not available via API)")

# Check for violation-related tables in KPI dataset
print("\n[2] Looking for property-linked violation tables in KPI dataset...")

# Try common table names that might have property info
table_checks = [
    "Violations",
    "ViolationDetail",
    "ViolationDetails",
    "XNDetails",
    "XN_Details",
    "PropertyViolations",
    "OwnerViolations",
    "PA_XN_Weekly_Table",
    "pbi Violations",
]

for table in table_checks:
    query = f"EVALUATE TOPN(1, '{table}')"
    rows = run_dax(query, pbi['kpi_workspace_id'], pbi['kpi_dataset_id'], table)
    if rows:
        cols = list(rows[0].keys())
        # Check for property/owner columns
        property_cols = [c for c in cols if any(x in c.lower() for x in ['owner', 'property', 'address', 'prop', 'lot', 'unit', 'account'])]
        print(f"\n    {table}: {len(cols)} columns")
        if property_cols:
            print(f"    *** FOUND PROPERTY COLUMNS: {property_cols}")
        print(f"    All columns: {cols[:10]}{'...' if len(cols) > 10 else ''}")

# Check M360 dataset for XN table with property info
print("\n[3] Checking M360 dataset for XN/violation tables with property linkage...")

m360_tables = [
    "XN",
    "XNs",
    "ActionItems",
    "Violations",
    "pbi XN",
    "pbi Violations",
]

for table in m360_tables:
    query = f"EVALUATE TOPN(1, '{table}')"
    rows = run_dax(query, pbi['m360_workspace_id'], pbi['m360_dataset_id'], table)
    if rows:
        cols = list(rows[0].keys())
        property_cols = [c for c in cols if any(x in c.lower() for x in ['owner', 'property', 'address', 'prop', 'lot', 'unit', 'account'])]
        print(f"\n    {table}: {len(cols)} columns")
        if property_cols:
            print(f"    *** FOUND PROPERTY COLUMNS: {property_cols}")
        print(f"    All columns: {cols}")

# Check if pbi Homeowners has any violation-related columns
print("\n[4] Checking if 'pbi Homeowners' has violation columns...")
query = "EVALUATE TOPN(1, 'pbi Homeowners')"
rows = run_dax(query, pbi['m360_workspace_id'], pbi['m360_dataset_id'], "pbi Homeowners")
if rows:
    cols = list(rows[0].keys())
    viol_cols = [c for c in cols if 'viol' in c.lower() or 'xn' in c.lower()]
    print(f"    Violation-related columns: {viol_cols if viol_cols else 'None found'}")
    print(f"    Total columns: {len(cols)}")

# Check ActionItemDetails for ALL columns
print("\n[5] ActionItemDetails - FULL column list...")
query = "EVALUATE TOPN(1, ActionItemDetails)"
rows = run_dax(query, pbi['kpi_workspace_id'], pbi['kpi_dataset_id'], "ActionItemDetails")
if rows:
    cols = list(rows[0].keys())
    print(f"    Total columns: {len(cols)}")
    print(f"    ALL COLUMNS:")
    for c in sorted(cols):
        print(f"        {c}")

    # Highlight property-related
    property_cols = [c for c in cols if any(x in c.lower() for x in ['owner', 'property', 'address', 'prop', 'lot', 'unit', 'account'])]
    if property_cols:
        print(f"\n    *** PROPERTY-RELATED: {property_cols}")

# Check CurrentStatus for ALL columns
print("\n[6] CurrentStatus - FULL column list...")
query = "EVALUATE TOPN(1, CurrentStatus)"
rows = run_dax(query, pbi['m360_workspace_id'], pbi['violation_dataset_id'], "CurrentStatus")
if rows:
    cols = list(rows[0].keys())
    print(f"    Total columns: {len(cols)}")
    print(f"    ALL COLUMNS:")
    for c in sorted(cols):
        print(f"        {c}")

    property_cols = [c for c in cols if any(x in c.lower() for x in ['owner', 'property', 'address', 'prop', 'lot', 'unit', 'account'])]
    if property_cols:
        print(f"\n    *** PROPERTY-RELATED: {property_cols}")

# Try to find what other tables exist in KPI dataset by probing common Vantaca tables
print("\n[7] Probing for other Vantaca tables in KPI dataset...")
probe_tables = [
    "vOwnerLedger", "vOwnerLedger2", "Owners", "Properties",
    "XNActionItems", "XNViolations", "ViolationXN",
    "pbi ActionItems", "pbi XNs", "XN_Property",
    "PropertyXN", "OwnerXN", "XNOwner",
]
for table in probe_tables:
    query = f"EVALUATE TOPN(1, '{table}')"
    rows = run_dax(query, pbi['kpi_workspace_id'], pbi['kpi_dataset_id'], table)
    if rows:
        cols = list(rows[0].keys())
        print(f"\n    FOUND: {table} - {len(cols)} columns")
        property_cols = [c for c in cols if any(x in c.lower() for x in ['owner', 'property', 'address', 'prop', 'lot', 'unit', 'account'])]
        if property_cols:
            print(f"    *** PROPERTY COLUMNS: {property_cols}")

print("\n" + "=" * 70)
print("SEARCH COMPLETE")
print("=" * 70)
