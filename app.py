"""
PSPM Homeowner Assistant - Standalone Agent
Beautiful, fast homeowner lookup for customer service staff.
"""
import os
import re
import time
import logging
from flask import Flask, jsonify, request, render_template

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# =============================================================================
# DATAVERSE CONFIGURATION
# =============================================================================
DATAVERSE_ENV_URL = os.environ.get('DATAVERSE_ENV_URL', 'https://org4f9a3823.crm.dynamics.com')
DATAVERSE_CLIENT_ID = os.environ.get('DATAVERSE_CLIENT_ID', '7b533f6b-b4fe-4355-bc8f-0fad34c8ec5d')
DATAVERSE_CLIENT_SECRET = os.environ.get('DATAVERSE_CLIENT_SECRET', '')
DATAVERSE_TENANT_ID = os.environ.get('DATAVERSE_TENANT_ID', '2ddb1df5-ce39-448e-86d2-a6b2184ac8a4')

# =============================================================================
# POWER BI CONFIGURATION (for payment history)
# =============================================================================
PBI_CLIENT_ID = os.environ.get('PBI_CLIENT_ID', '')
PBI_CLIENT_SECRET = os.environ.get('PBI_CLIENT_SECRET', '')
PBI_TENANT_ID = os.environ.get('PBI_TENANT_ID', '2ddb1df5-ce39-448e-86d2-a6b2184ac8a4')
PBI_WORKSPACE_ID = os.environ.get('PBI_WORKSPACE_ID', 'c5395f33-bd22-4d26-846f-5ad44c7ad108')
PBI_DATASET_ID = os.environ.get('PBI_DATASET_ID', 'e17e4241-37b7-4d12-a2e8-8f4e6148ca03')

# Use main homeowners table (has all fields) instead of lean copilot table
TABLE_NAME = 'cr258_hoa_homeowners'
COLUMNS = [
    'cr258_owner_name', 'cr258_accountnumber', 'cr258_property_address',
    'cr258_assoc_name', 'cr258_balance', 'cr258_creditbalance',
    'cr258_primaryphone', 'cr258_primaryemail', 'cr258_collectionstatus',
    'cr258_vantacaurl',
    # Additional fields for enhanced cards
    'cr258_allphones', 'cr258_allemails', 'cr258_tenantname',
    'cr258_collprovider', 'cr258_lotnumber', 'cr258_unitnumber',
    'cr258_tags', 'cr258_lastpaymentdate', 'cr258_lastpaymentamount',
    # Sync timestamp
    'modifiedon'
]

# Token cache
_token_cache = {'token': None, 'expires': 0}


def get_dataverse_token():
    """Get access token for Dataverse API."""
    if _token_cache['token'] and time.time() < _token_cache['expires']:
        return _token_cache['token']

    if not DATAVERSE_CLIENT_SECRET:
        logger.warning("Dataverse credentials not configured")
        return None

    try:
        import msal
        app_auth = msal.ConfidentialClientApplication(
            DATAVERSE_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{DATAVERSE_TENANT_ID}",
            client_credential=DATAVERSE_CLIENT_SECRET
        )
        result = app_auth.acquire_token_for_client(
            scopes=[f'{DATAVERSE_ENV_URL.rstrip("/")}/.default']
        )
        if 'access_token' in result:
            _token_cache['token'] = result['access_token']
            _token_cache['expires'] = time.time() + 3000
            return result['access_token']
        else:
            logger.error(f"Token error: {result.get('error_description', 'Unknown')}")
            return None
    except Exception as e:
        logger.error(f"Failed to get Dataverse token: {e}")
        return None


def query_dataverse(filter_expr, top=50):
    """Query Dataverse with OData filter."""
    import requests

    token = get_dataverse_token()
    if not token:
        return None

    url = f"{DATAVERSE_ENV_URL.rstrip('/')}/api/data/v9.2/{TABLE_NAME}"
    params = {
        '$select': ','.join(COLUMNS),
        '$filter': filter_expr,
        '$top': str(top)
    }
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'OData-MaxVersion': '4.0',
        'OData-Version': '4.0'
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json().get('value', [])
        else:
            logger.error(f"Dataverse query failed: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        logger.error(f"Dataverse request failed: {e}")
        return None


def normalize_phone(phone):
    """Strip non-digits from phone number."""
    return re.sub(r'\D', '', phone)


# =============================================================================
# POWER BI FUNCTIONS (for payment history)
# =============================================================================
_pbi_token_cache = {'token': None, 'expires': 0}


def get_pbi_token():
    """Get access token for Power BI API."""
    if _pbi_token_cache['token'] and time.time() < _pbi_token_cache['expires']:
        return _pbi_token_cache['token']

    if not PBI_CLIENT_SECRET:
        logger.warning("Power BI credentials not configured")
        return None

    try:
        import msal
        app_auth = msal.ConfidentialClientApplication(
            PBI_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{PBI_TENANT_ID}",
            client_credential=PBI_CLIENT_SECRET
        )
        result = app_auth.acquire_token_for_client(
            scopes=['https://analysis.windows.net/powerbi/api/.default']
        )
        if 'access_token' in result:
            _pbi_token_cache['token'] = result['access_token']
            _pbi_token_cache['expires'] = time.time() + 3000
            return result['access_token']
        else:
            logger.error(f"PBI Token error: {result.get('error_description', 'Unknown')}")
            return None
    except Exception as e:
        logger.error(f"Failed to get Power BI token: {e}")
        return None


def query_pbi_dax(query):
    """Execute DAX query against Power BI dataset."""
    import requests

    token = get_pbi_token()
    if not token:
        return None

    url = f"https://api.powerbi.com/v1.0/myorg/groups/{PBI_WORKSPACE_ID}/datasets/{PBI_DATASET_ID}/executeQueries"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {
        'queries': [{'query': query}],
        'serializerSettings': {'includeNulls': True}
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            return resp.json()['results'][0]['tables'][0]['rows']
        else:
            logger.error(f"Power BI query failed: {resp.status_code} - {resp.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Power BI request failed: {e}")
        return None


def get_owner_id_by_account(account_number):
    """Get OwnerID from Power BI by account number."""
    safe_account = account_number.replace("'", "''").upper()
    query = f"""
    EVALUATE
    SELECTCOLUMNS(
        FILTER('pbi Homeowners', 'pbi Homeowners'[AccountNo] = "{safe_account}"),
        "OwnerID", 'pbi Homeowners'[OwnerID]
    )
    """
    rows = query_pbi_dax(query)
    if rows and len(rows) > 0:
        return rows[0].get('[OwnerID]')
    return None


def get_payment_history(owner_id, limit=15):
    """Get recent payment/charge history for an owner."""
    from datetime import datetime

    # Fetch more rows to ensure we get enough after sorting
    query = f"""
    EVALUATE
    SELECTCOLUMNS(
        FILTER(vOwnerLedger2, vOwnerLedger2[OwnerID] = {owner_id}),
        "Date", vOwnerLedger2[LedgerDate],
        "Amount", vOwnerLedger2[Amount],
        "Type", vOwnerLedger2[TypeDescr],
        "Description", vOwnerLedger2[Descr]
    )
    """
    rows = query_pbi_dax(query)
    if not rows:
        return []

    history = []
    for row in rows:
        date_str = row.get('[Date]', '')
        amount = row.get('[Amount]', 0)
        tx_type = row.get('[Type]', '')
        desc = row.get('[Description]', '')

        # Parse and format date
        formatted_date = ''
        sort_date = None
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                formatted_date = dt.strftime('%b %d, %Y')
                sort_date = dt
            except:
                formatted_date = date_str[:10] if len(date_str) >= 10 else date_str
                sort_date = None

        history.append({
            'date': formatted_date,
            'sort_date': sort_date,
            'raw_date': date_str,
            'amount': amount,
            'amount_display': f"${abs(amount):,.2f}",
            'type': tx_type,
            'is_payment': amount < 0,
            'description': desc
        })

    # Sort by date ascending (oldest first) for running balance calculation
    history.sort(key=lambda x: x['sort_date'] or datetime.min)

    # Take only the most recent 'limit' transactions after sorting
    if len(history) > limit:
        history = history[-limit:]

    return history


def format_homeowner(rec):
    """Format a homeowner record for API response."""
    balance = rec.get('cr258_balance') or 0
    credit = rec.get('cr258_creditbalance') or 0
    status = rec.get('cr258_collectionstatus') or 'Current'

    if credit > 0:
        balance_display = f"${credit:.2f} CREDIT"
        balance_status = "credit"
    elif balance == 0:
        balance_display = "$0.00"
        balance_status = "current"
    else:
        balance_display = f"${balance:.2f}"
        balance_status = "owed"

    collection_indicator = None
    if status == 'In Collections':
        collection_indicator = 'collections'
    elif status == '60 Days':
        collection_indicator = '60_days'
    elif status == '30 Days':
        collection_indicator = '30_days'

    # Format last payment info
    last_payment_date = rec.get('cr258_lastpaymentdate')
    last_payment_amount = rec.get('cr258_lastpaymentamount')
    last_payment = None
    if last_payment_date and last_payment_amount:
        # Format date nicely
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(last_payment_date.replace('Z', '+00:00'))
            date_str = dt.strftime('%b %d, %Y')
            last_payment = {
                'date': date_str,
                'amount': f"${last_payment_amount:,.2f}",
                'raw_date': last_payment_date,
                'raw_amount': last_payment_amount
            }
        except:
            last_payment = {
                'date': last_payment_date,
                'amount': f"${last_payment_amount:,.2f}" if last_payment_amount else 'N/A'
            }

    # Parse tags into list
    tags_str = rec.get('cr258_tags') or ''
    tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []

    # Build unit/lot display
    lot = rec.get('cr258_lotnumber') or ''
    unit = rec.get('cr258_unitnumber') or ''
    unit_lot = None
    if unit and lot:
        unit_lot = f"Unit {unit}, Lot {lot}"
    elif unit:
        unit_lot = f"Unit {unit}"
    elif lot:
        unit_lot = f"Lot {lot}"

    # Format last sync timestamp from Dataverse (convert UTC to Central Time)
    modified_on = rec.get('modifiedon')
    last_synced = None
    last_synced_display = None
    if modified_on:
        try:
            from zoneinfo import ZoneInfo
            sync_dt = datetime.fromisoformat(modified_on.replace('Z', '+00:00'))
            # Convert to Central Time
            central_tz = ZoneInfo('America/Chicago')
            sync_dt_central = sync_dt.astimezone(central_tz)
            last_synced = modified_on
            last_synced_display = sync_dt_central.strftime('%b %d, %Y at %I:%M %p CT')
        except:
            last_synced_display = modified_on

    return {
        'owner_name': rec.get('cr258_owner_name', 'Unknown'),
        'property_address': rec.get('cr258_property_address', 'N/A'),
        'community': rec.get('cr258_assoc_name', 'N/A'),
        'account_number': rec.get('cr258_accountnumber', 'N/A'),
        'balance': balance,
        'credit_balance': credit,
        'balance_display': balance_display,
        'balance_status': balance_status,
        'collection_status': status,
        'collection_indicator': collection_indicator,
        'collection_provider': rec.get('cr258_collprovider') or None,
        'phone': rec.get('cr258_primaryphone') or 'N/A',
        'email': rec.get('cr258_primaryemail') or 'N/A',
        'all_phones': rec.get('cr258_allphones') or None,
        'all_emails': rec.get('cr258_allemails') or None,
        'tenant_name': rec.get('cr258_tenantname') or None,
        'unit_lot': unit_lot,
        'tags': tags,
        'last_payment': last_payment,
        'vantaca_url': rec.get('cr258_vantacaurl') or None,
        'last_synced': last_synced,
        'last_synced_display': last_synced_display
    }


# =============================================================================
# ROUTES
# =============================================================================

@app.route('/')
def index():
    """Render the main search interface."""
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """Check Dataverse connection status."""
    token = get_dataverse_token()
    if token:
        return jsonify({
            'status': 'connected',
            'dataverse_url': DATAVERSE_ENV_URL,
            'table': TABLE_NAME,
            'record_count': '23,752+'
        })
    else:
        return jsonify({
            'status': 'disconnected',
            'error': 'Could not connect to Dataverse',
            'check_credentials': not bool(DATAVERSE_CLIENT_SECRET)
        }), 503


@app.route('/api/search')
def search():
    """Universal homeowner search endpoint."""
    query = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'auto')
    delinquent = request.args.get('delinquent', 'false').lower() == 'true'
    community_filter = request.args.get('community', '').strip() or None

    if not query:
        return jsonify({'error': 'Query required', 'homeowners': []}), 400

    # Auto-detect search type
    if search_type == 'auto':
        digits = normalize_phone(query)
        upper_query = query.upper()

        # Check for phone number (7+ digits)
        if len(digits) >= 7:
            search_type = 'phone'
        # Check for account number patterns:
        # 1. Starts with known prefixes (FAL51515)
        # 2. Pattern like ABC12345 (3 letters + numbers)
        # 3. Just numbers that are 4-8 digits (could be account without prefix)
        elif upper_query.startswith(('FAL', 'AMC', 'AVA', 'CHA', 'HER', 'HIL', 'SOC', 'VIL', 'WES', 'VER', 'WIL', 'SAG', 'OAK', 'VIS')):
            search_type = 'account'
        elif re.match(r'^[A-Z]{2,4}\d{3,8}$', upper_query):
            # Pattern: 2-4 letters followed by 3-8 digits (like FAL51515)
            search_type = 'account'
        elif re.match(r'^\d{4,8}$', query):
            # Pure numbers 4-8 digits - likely account number without prefix
            search_type = 'account'
        # Check for unit/lot patterns (unit 5, lot 12, #5, etc.)
        elif re.match(r'^(unit|lot|#)\s*\d+', query.lower()):
            search_type = 'unit'
        else:
            # Default to general search (searches name, address, AND account)
            search_type = 'general'

    # Execute search - all types now support community_filter
    if search_type == 'phone':
        return search_by_phone(query, community_filter)
    elif search_type == 'address':
        return search_by_address(query, community_filter)
    elif search_type == 'name':
        return search_by_name(query, community_filter)
    elif search_type == 'general':
        return search_general(query, community_filter)
    elif search_type == 'community':
        return search_by_community(query, delinquent)
    elif search_type == 'account':
        return search_by_account(query, community_filter)
    elif search_type == 'unit':
        return search_by_unit(query, community_filter)
    else:
        return jsonify({'error': 'Invalid search type', 'homeowners': []}), 400


def search_by_phone(phone, community_filter=None):
    """Search by phone number, with optional community filter."""
    digits = normalize_phone(phone)
    if len(digits) < 7:
        return jsonify({'error': f"Phone too short: '{phone}'", 'homeowners': [], 'count': 0}), 400

    last4 = digits[-4:]
    filter_expr = f"contains(cr258_primaryphone,'{last4}')"

    if community_filter:
        safe_community = community_filter.replace("'", "''")
        filter_expr = f"contains(cr258_assoc_name,'{safe_community}') and {filter_expr}"

    results = query_dataverse(filter_expr, top=50)

    if results is None:
        return jsonify({'error': 'Dataverse connection failed', 'homeowners': []}), 503

    # Further filter by full phone match
    filtered = [r for r in results if digits[-10:] in normalize_phone(r.get('cr258_primaryphone', ''))]
    homeowners = [format_homeowner(r) for r in filtered]

    return jsonify({
        'search_type': 'phone',
        'query': phone,
        'community_filter': community_filter,
        'homeowners': homeowners,
        'count': len(homeowners)
    })


def search_by_address(address, community_filter=None):
    """Search by address, with optional community filter."""
    safe_address = address.replace("'", "''")
    filter_expr = f"contains(cr258_property_address,'{safe_address}')"

    if community_filter:
        safe_community = community_filter.replace("'", "''")
        filter_expr += f" and contains(cr258_assoc_name,'{safe_community}')"

    results = query_dataverse(filter_expr, top=20)

    if results is None:
        return jsonify({'error': 'Dataverse connection failed', 'homeowners': []}), 503

    homeowners = [format_homeowner(r) for r in results]

    return jsonify({
        'search_type': 'address',
        'query': address,
        'community_filter': community_filter,
        'homeowners': homeowners,
        'count': len(homeowners)
    })


def search_by_name(name, community_filter=None):
    """Search by owner name - flexible partial matching."""
    safe_name = name.replace("'", "''")

    # Search owner name field
    filter_expr = f"contains(cr258_owner_name,'{safe_name}')"

    if community_filter:
        safe_community = community_filter.replace("'", "''")
        filter_expr += f" and contains(cr258_assoc_name,'{safe_community}')"

    results = query_dataverse(filter_expr, top=30)

    if results is None:
        return jsonify({'error': 'Dataverse connection failed', 'homeowners': []}), 503

    homeowners = [format_homeowner(r) for r in results]

    return jsonify({
        'search_type': 'name',
        'query': name,
        'community_filter': community_filter,
        'homeowners': homeowners,
        'count': len(homeowners)
    })


def search_general(query, community_filter=None):
    """Search across name, address, account, and unit/lot fields - most flexible search."""
    safe_query = query.replace("'", "''")
    upper_query = safe_query.upper()

    # Build filter: search in name OR address OR account number
    filter_expr = f"(contains(cr258_owner_name,'{safe_query}') or contains(cr258_property_address,'{safe_query}') or contains(cr258_accountnumber,'{upper_query}'))"

    if community_filter:
        safe_community = community_filter.replace("'", "''")
        filter_expr = f"contains(cr258_assoc_name,'{safe_community}') and {filter_expr}"

    results = query_dataverse(filter_expr, top=30)

    if results is None:
        return jsonify({'error': 'Dataverse connection failed', 'homeowners': []}), 503

    # If query looks like a number, also search unit/lot fields
    if query.isdigit() and not results:
        unit_filter = f"(cr258_unitnumber eq '{safe_query}' or cr258_lotnumber eq '{safe_query}')"
        if community_filter:
            unit_filter = f"contains(cr258_assoc_name,'{safe_community}') and {unit_filter}"
        unit_results = query_dataverse(unit_filter, top=30)
        if unit_results:
            results = results + unit_results if results else unit_results

    homeowners = [format_homeowner(r) for r in results]

    return jsonify({
        'search_type': 'general',
        'query': query,
        'community_filter': community_filter,
        'homeowners': homeowners,
        'count': len(homeowners)
    })


def search_by_community(community, delinquent_only=False):
    """Search by community name."""
    safe_community = community.replace("'", "''")
    filter_expr = f"contains(cr258_assoc_name,'{safe_community}')"

    if delinquent_only:
        filter_expr += " and cr258_balance gt 0"

    results = query_dataverse(filter_expr, top=100)

    if results is None:
        return jsonify({'error': 'Dataverse connection failed', 'homeowners': []}), 503

    homeowners = [format_homeowner(r) for r in results]

    if delinquent_only:
        homeowners.sort(key=lambda x: x['balance'], reverse=True)

    total_balance = sum(h['balance'] for h in homeowners if h['balance'] > 0)

    return jsonify({
        'search_type': 'community',
        'query': community,
        'delinquent_only': delinquent_only,
        'homeowners': homeowners,
        'count': len(homeowners),
        'total_outstanding': round(total_balance, 2) if delinquent_only else None
    })


def search_by_account(account, community_filter=None):
    """Search by account number - flexible matching."""
    safe_account = account.replace("'", "''").upper()

    # Try exact match first (case-insensitive via upper)
    filter_expr = f"cr258_accountnumber eq '{safe_account}'"
    if community_filter:
        safe_community = community_filter.replace("'", "''")
        filter_expr = f"contains(cr258_assoc_name,'{safe_community}') and {filter_expr}"

    results = query_dataverse(filter_expr, top=5)

    # If no exact match, try contains search
    if results is None:
        return jsonify({'error': 'Dataverse connection failed', 'homeowners': []}), 503

    if not results:
        # Try contains match (partial account number)
        filter_expr = f"contains(cr258_accountnumber,'{safe_account}')"
        if community_filter:
            filter_expr = f"contains(cr258_assoc_name,'{safe_community}') and {filter_expr}"
        results = query_dataverse(filter_expr, top=20)

    # If still no results and query is just digits, try with common prefixes
    if not results and safe_account.isdigit():
        common_prefixes = ['FAL', 'AVA', 'CHA', 'HER', 'VIS', 'VIL', 'WES', 'HIL', 'OAK', 'SAG']
        for prefix in common_prefixes:
            test_account = f"{prefix}{safe_account}"
            filter_expr = f"cr258_accountnumber eq '{test_account}'"
            if community_filter:
                filter_expr = f"contains(cr258_assoc_name,'{safe_community}') and {filter_expr}"
            results = query_dataverse(filter_expr, top=5)
            if results:
                break

    homeowners = [format_homeowner(r) for r in (results or [])]

    return jsonify({
        'search_type': 'account',
        'query': account,
        'community_filter': community_filter,
        'homeowners': homeowners,
        'count': len(homeowners)
    })


def search_by_unit(unit_query, community_filter=None):
    """Search by unit or lot number."""
    # Extract the number from patterns like "unit 5", "lot 12", "#5"
    match = re.search(r'\d+', unit_query)
    if not match:
        return jsonify({'error': 'Invalid unit/lot number', 'homeowners': [], 'count': 0}), 400

    number = match.group()
    safe_number = number.replace("'", "''")

    # Build filter to search unit number OR lot number
    filter_expr = f"(cr258_unitnumber eq '{safe_number}' or cr258_lotnumber eq '{safe_number}')"

    if community_filter:
        safe_community = community_filter.replace("'", "''")
        filter_expr = f"contains(cr258_assoc_name,'{safe_community}') and {filter_expr}"

    results = query_dataverse(filter_expr, top=30)

    if results is None:
        return jsonify({'error': 'Dataverse connection failed', 'homeowners': []}), 503

    # If no exact match, try contains search
    if not results:
        filter_expr = f"(contains(cr258_unitnumber,'{safe_number}') or contains(cr258_lotnumber,'{safe_number}'))"
        if community_filter:
            filter_expr = f"contains(cr258_assoc_name,'{safe_community}') and {filter_expr}"
        results = query_dataverse(filter_expr, top=30)

    homeowners = [format_homeowner(r) for r in (results or [])]

    return jsonify({
        'search_type': 'unit',
        'query': unit_query,
        'community_filter': community_filter,
        'homeowners': homeowners,
        'count': len(homeowners)
    })


@app.route('/api/history')
def get_history():
    """Get payment/charge history for an account - returns ledger-style data."""
    account = request.args.get('account', '').strip()
    limit = int(request.args.get('limit', 15))

    if not account:
        return jsonify({'error': 'Account number required', 'history': []}), 400

    if not PBI_CLIENT_SECRET:
        return jsonify({
            'error': 'Power BI not configured',
            'history': [],
            'message': 'Payment history requires Power BI credentials'
        }), 503

    # Get OwnerID from account number
    owner_id = get_owner_id_by_account(account)
    if not owner_id:
        return jsonify({
            'error': 'Account not found in Power BI',
            'account': account,
            'history': []
        }), 404

    # Get payment history (already sorted oldest to newest)
    history = get_payment_history(owner_id, limit=limit)

    # Calculate running balance from oldest to newest
    running_balance = 0
    for item in history:
        running_balance += item['amount']
        item['running_balance'] = round(running_balance, 2)
        item['balance_display'] = f"${abs(running_balance):,.2f}"
        if running_balance < 0:
            item['balance_display'] = f"(${abs(running_balance):,.2f})"  # Credit shown in parens
        # Remove sort_date from response (not needed by frontend)
        item.pop('sort_date', None)

    # Reverse to show newest first (most recent transactions at top)
    history.reverse()

    return jsonify({
        'account': account,
        'owner_id': owner_id,
        'history': history,
        'count': len(history)
    })


@app.route('/api/suggest')
def suggest():
    """Predictive search - return quick suggestions as user types."""
    query = request.args.get('q', '').strip()

    if len(query) < 2:
        return jsonify({'suggestions': []})

    safe_query = query.replace("'", "''")
    suggestions = []
    seen = set()

    # Search across multiple fields for suggestions
    # 1. Owner names
    name_results = query_dataverse(
        f"contains(cr258_owner_name,'{safe_query}')",
        top=5
    )
    if name_results:
        for r in name_results:
            name = r.get('cr258_owner_name', '')
            if name and name.lower() not in seen:
                seen.add(name.lower())
                suggestions.append({
                    'text': name,
                    'type': 'person',
                    'icon': 'user',
                    'subtext': r.get('cr258_property_address', '')
                })

    # 2. Addresses (if query looks like an address - has numbers)
    if any(c.isdigit() for c in query):
        addr_results = query_dataverse(
            f"contains(cr258_property_address,'{safe_query}')",
            top=4
        )
        if addr_results:
            for r in addr_results:
                addr = r.get('cr258_property_address', '')
                if addr and addr.lower() not in seen:
                    seen.add(addr.lower())
                    suggestions.append({
                        'text': addr,
                        'type': 'address',
                        'icon': 'map-marker-alt',
                        'subtext': r.get('cr258_assoc_name', '')
                    })

    # 3. Communities
    comm_results = query_dataverse(
        f"contains(cr258_assoc_name,'{safe_query}')",
        top=3
    )
    if comm_results:
        # Get unique community names
        communities_seen = set()
        for r in comm_results:
            comm = r.get('cr258_assoc_name', '')
            if comm and comm.lower() not in communities_seen:
                communities_seen.add(comm.lower())
                if comm.lower() not in seen:
                    seen.add(comm.lower())
                    suggestions.append({
                        'text': comm,
                        'type': 'community',
                        'icon': 'building',
                        'subtext': 'Community'
                    })

    # Limit to 8 total suggestions
    return jsonify({
        'query': query,
        'suggestions': suggestions[:8]
    })


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
