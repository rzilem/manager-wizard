"""
PSPM Manager Wizard - Unified Search Tool
Beautiful, intelligent search for homeowners and community documents.
Smart auto-detection routes queries to the right data source.
"""
import os
import re
import time
import json
import logging
from flask import Flask, jsonify, request, render_template

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# =============================================================================
# AZURE AI SEARCH CONFIGURATION (SharePoint Documents)
# =============================================================================
AZURE_SEARCH_ENDPOINT = os.environ.get('AZURE_SEARCH_ENDPOINT', 'https://psmai.search.windows.net')
AZURE_SEARCH_API_KEY = os.environ.get('AZURE_SEARCH_API_KEY', '')
AZURE_SEARCH_INDEX = os.environ.get('AZURE_SEARCH_INDEX', 'sharepoint-docs')

# =============================================================================
# ANTHROPIC CONFIGURATION (Claude for answer extraction)
# =============================================================================
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

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
# DOCUMENT SEARCH (Azure AI Search + Claude Extraction)
# =============================================================================

# Document type patterns for smart cards
DOCUMENT_PATTERNS = {
    'ccr': {
        'keywords': ['cc&r', 'ccr', 'covenants', 'conditions', 'restrictions', 'declaration'],
        'icon': 'file-contract',
        'color': '#1e40af',
        'label': 'CC&Rs'
    },
    'rules': {
        'keywords': ['rules', 'regulations', 'policy', 'policies', 'guidelines'],
        'icon': 'list-check',
        'color': '#7c3aed',
        'label': 'Rules & Regulations'
    },
    'pool': {
        'keywords': ['pool', 'swimming', 'aquatic'],
        'icon': 'swimming-pool',
        'color': '#0891b2',
        'label': 'Pool Rules'
    },
    'architectural': {
        'keywords': ['architectural', 'arc', 'design', 'modification', 'improvement'],
        'icon': 'drafting-compass',
        'color': '#ea580c',
        'label': 'Architectural Guidelines'
    },
    'fence': {
        'keywords': ['fence', 'fencing', 'barrier'],
        'icon': 'border-all',
        'color': '#65a30d',
        'label': 'Fence Regulations'
    },
    'parking': {
        'keywords': ['parking', 'vehicle', 'towing', 'garage'],
        'icon': 'car',
        'color': '#dc2626',
        'label': 'Parking Rules'
    },
    'pet': {
        'keywords': ['pet', 'animal', 'dog', 'cat'],
        'icon': 'paw',
        'color': '#db2777',
        'label': 'Pet Policy'
    },
    'bylaws': {
        'keywords': ['bylaws', 'by-laws', 'bylaw'],
        'icon': 'gavel',
        'color': '#4f46e5',
        'label': 'Bylaws'
    }
}

# Question patterns that indicate document search
QUESTION_PATTERNS = [
    r'\b(what|how|when|where|can i|am i allowed|is it okay|rules? for|policy on|guidelines? for)\b',
    r'\b(fence|pool|parking|pet|architectural|arc|modification|violation)\b',
    r'\b(cc&?r|bylaws?|regulations?|restrictions?)\b',
    r'\b(height|limit|allowed|permitted|required|deadline)\b'
]


def detect_query_type(query):
    """
    Smart detection of query type.
    Returns: 'homeowner', 'document', or 'both'
    """
    query_lower = query.lower().strip()
    digits = re.sub(r'\D', '', query)

    # Strong homeowner indicators
    is_phone = len(digits) >= 7 and len(digits) <= 11
    is_account = bool(re.match(r'^[A-Z]{2,4}\d{3,8}$', query.upper())) or \
                 bool(re.match(r'^\d{4,8}$', query))
    is_address = bool(re.match(r'^\d+\s+\w+', query)) and not any(kw in query_lower for kw in ['rule', 'policy', 'height', 'fence', 'pool'])
    is_unit = bool(re.match(r'^(unit|lot|#)\s*\d+', query_lower))

    # Strong document indicators
    is_question = any(re.search(pattern, query_lower) for pattern in QUESTION_PATTERNS)
    has_doc_keywords = any(
        any(kw in query_lower for kw in doc_type['keywords'])
        for doc_type in DOCUMENT_PATTERNS.values()
    )

    # Decision logic
    if is_phone or is_account or is_unit:
        return 'homeowner'

    if is_question or has_doc_keywords:
        # Check if also has a name pattern (e.g., "Smith fence rules")
        words = query.split()
        potential_name = len(words) >= 2 and words[0][0].isupper() and not has_doc_keywords
        if potential_name and not is_question:
            return 'both'
        return 'document'

    if is_address:
        return 'homeowner'

    # Default: could be a name search or general query
    # If it looks like a name (capitalized words), try homeowner
    if query[0].isupper() and ' ' not in query:
        return 'homeowner'

    # Ambiguous - search both
    return 'both'


def extract_community_from_query(query):
    """Try to extract community name from query."""
    # Common community name patterns
    community_patterns = [
        r'(?:for|in|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        r'([A-Z][a-z]+(?:\s+(?:Creek|Park|Hills?|Valley|Ranch|Pointe?|Vista|Heights?))+)',
    ]

    for pattern in community_patterns:
        match = re.search(pattern, query)
        if match:
            return match.group(1)
    return None


def search_azure_documents(query, community=None, top=10):
    """Search Azure AI Search index for SharePoint documents."""
    import requests

    if not AZURE_SEARCH_API_KEY:
        logger.warning("Azure Search not configured")
        return {'documents': [], 'answers': [], 'count': 0}

    url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{AZURE_SEARCH_INDEX}/docs/search?api-version=2023-11-01"

    # Build search query
    search_text = query
    if community:
        search_text = f"{query} AND \"{community}\""

    payload = {
        "search": search_text,
        "queryType": "simple",
        "top": top,
        "select": "metadata_spo_item_name,metadata_spo_item_path,metadata_spo_item_weburi"
    }

    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_SEARCH_API_KEY
    }

    try:
        logger.info(f"Azure Search query: {search_text}")
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            results = []

            # Process search results
            for doc in data.get('value', []):
                # Determine document type
                doc_type = 'general'
                doc_type_info = {'icon': 'file-alt', 'color': '#6b7280', 'label': 'Document'}

                name_lower = (doc.get('metadata_spo_item_name') or '').lower()
                for dtype, info in DOCUMENT_PATTERNS.items():
                    if any(kw in name_lower for kw in info['keywords']):
                        doc_type = dtype
                        doc_type_info = info
                        break

                # Extract community from path
                path = doc.get('metadata_spo_item_path') or ''
                community_match = re.search(r'/([^/]+)/Association Documents/', path)
                doc_community = community_match.group(1) if community_match else None

                results.append({
                    'title': doc.get('metadata_spo_item_name', 'Unknown'),
                    'path': path,
                    'url': doc.get('metadata_spo_item_weburi', ''),
                    'community': doc_community,
                    'doc_type': doc_type,
                    'doc_type_info': doc_type_info,
                    'score': doc.get('@search.score', 0)
                })

            logger.info(f"Azure Search found {len(results)} results")

            return {
                'documents': results,
                'answers': [],
                'count': len(results)
            }
        else:
            logger.error(f"Azure Search failed: {resp.status_code} - {resp.text[:500]}")
            return {'documents': [], 'answers': [], 'count': 0, 'error': resp.text[:200]}
    except Exception as e:
        logger.error(f"Azure Search request failed: {e}")
        return {'documents': [], 'answers': [], 'count': 0, 'error': str(e)}


def extract_answer_with_claude(query, documents, community=None):
    """Use Claude to create a helpful response based on found documents."""
    import requests

    if not ANTHROPIC_API_KEY or not documents:
        return None

    # Prepare document context - we only have metadata, not full content
    doc_context = "Found relevant documents:\n"
    for i, doc in enumerate(documents[:5]):  # Top 5 docs
        doc_context += f"\n{i+1}. {doc['title']}"
        if doc.get('community'):
            doc_context += f" (Community: {doc['community']})"
        doc_context += f"\n   Type: {doc.get('doc_type_info', {}).get('label', 'Document')}"
        if doc.get('url'):
            doc_context += f"\n   URL: {doc['url']}"
        doc_context += "\n"

    # Determine what type of info to extract
    query_lower = query.lower()
    extraction_type = "general"

    if any(kw in query_lower for kw in ['fence', 'height', 'material']):
        extraction_type = "fence"
    elif any(kw in query_lower for kw in ['pool', 'swimming', 'hours']):
        extraction_type = "pool"
    elif any(kw in query_lower for kw in ['parking', 'vehicle', 'tow']):
        extraction_type = "parking"
    elif any(kw in query_lower for kw in ['pet', 'dog', 'cat', 'animal']):
        extraction_type = "pet"
    elif any(kw in query_lower for kw in ['architectural', 'arc', 'modification']):
        extraction_type = "architectural"

    # Build extraction prompt based on type
    extraction_prompts = {
        "fence": """Extract fence regulations into this JSON format:
{
    "max_height_back": "X feet",
    "max_height_front": "X feet",
    "approved_materials": ["material1", "material2"],
    "arc_required": true/false,
    "key_restrictions": ["restriction1", "restriction2"],
    "summary": "One sentence summary"
}""",
        "pool": """Extract pool rules into this JSON format:
{
    "hours": "X AM - X PM",
    "guest_policy": "description",
    "key_rules": ["rule1", "rule2", "rule3"],
    "restrictions": ["restriction1", "restriction2"],
    "summary": "One sentence summary"
}""",
        "parking": """Extract parking rules into this JSON format:
{
    "allowed_vehicles": ["type1", "type2"],
    "prohibited_vehicles": ["type1", "type2"],
    "guest_parking": "description",
    "towing_policy": "description",
    "key_rules": ["rule1", "rule2"],
    "summary": "One sentence summary"
}""",
        "pet": """Extract pet policy into this JSON format:
{
    "allowed_pets": ["type1", "type2"],
    "max_pets": "X",
    "weight_limit": "X lbs",
    "leash_required": true/false,
    "key_rules": ["rule1", "rule2"],
    "summary": "One sentence summary"
}""",
        "architectural": """Extract architectural guidelines into this JSON format:
{
    "submission_required": true/false,
    "approval_timeline": "X days",
    "common_projects": ["project1", "project2"],
    "prohibited_modifications": ["mod1", "mod2"],
    "key_requirements": ["req1", "req2"],
    "summary": "One sentence summary"
}""",
        "general": """Extract the relevant information into this JSON format:
{
    "answer": "Direct answer to the question",
    "key_points": ["point1", "point2", "point3"],
    "source_section": "Section name if found",
    "summary": "One sentence summary"
}"""
    }

    prompt = f"""You are a helpful assistant for PS Property Management. A manager is looking for information about community rules and policies.

Question: {query}
{f'Community: {community}' if community else ''}

{doc_context}

Based on the documents found, provide a helpful response in this JSON format:
{{
    "summary": "A brief helpful response about what was found and where to look",
    "documents_found": ["list of most relevant document names"],
    "suggestion": "Suggestion for what to do next (e.g., 'Open the CC&Rs document to find fence height limits')",
    "category": "{extraction_type}"
}}

Be helpful and direct. If specific documents were found, tell them which one is most likely to have their answer.
Return ONLY valid JSON, no other text."""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-3-5-haiku-20241022",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )

        if resp.status_code == 200:
            content = resp.json()['content'][0]['text']
            # Try to parse JSON
            try:
                # Find JSON in response
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    return {
                        'extracted': json.loads(json_match.group()),
                        'extraction_type': extraction_type
                    }
            except json.JSONDecodeError:
                pass
            return None
        else:
            logger.error(f"Claude API failed: {resp.status_code}")
            return None
    except Exception as e:
        logger.error(f"Claude extraction failed: {e}")
        return None


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
    azure_configured = bool(AZURE_SEARCH_API_KEY)

    if token:
        return jsonify({
            'status': 'connected',
            'dataverse_url': DATAVERSE_ENV_URL,
            'table': TABLE_NAME,
            'record_count': '23,752+',
            'azure_search': 'configured' if azure_configured else 'not configured',
            'documents_indexed': '482,000+' if azure_configured else 'N/A'
        })
    else:
        return jsonify({
            'status': 'disconnected',
            'error': 'Could not connect to Dataverse',
            'check_credentials': not bool(DATAVERSE_CLIENT_SECRET),
            'azure_search': 'configured' if azure_configured else 'not configured'
        }), 503


@app.route('/api/unified-search')
def unified_search():
    """
    Smart unified search - auto-detects whether to search homeowners or documents.
    Returns structured results from both sources when appropriate.
    """
    query = request.args.get('q', '').strip()
    mode = request.args.get('mode', 'auto')  # auto, homeowner, document, both

    if not query:
        return jsonify({'error': 'Query required'}), 400

    # Detect query type if auto mode
    if mode == 'auto':
        detected_type = detect_query_type(query)
    else:
        detected_type = mode

    # Extract community from query if present
    community = extract_community_from_query(query)

    result = {
        'query': query,
        'detected_type': detected_type,
        'community_detected': community,
        'homeowners': [],
        'documents': [],
        'ai_answer': None
    }

    # Search homeowners if needed
    if detected_type in ['homeowner', 'both']:
        # Reuse existing search logic
        homeowner_result = search_homeowners_internal(query, community)
        result['homeowners'] = homeowner_result.get('homeowners', [])
        result['homeowner_count'] = len(result['homeowners'])

    # Search documents if needed
    if detected_type in ['document', 'both']:
        doc_result = search_azure_documents(query, community)
        result['documents'] = doc_result.get('documents', [])
        result['document_count'] = len(result['documents'])
        result['semantic_answers'] = doc_result.get('answers', [])

        # If we have documents, try to extract a structured answer
        if result['documents'] and ANTHROPIC_API_KEY:
            ai_result = extract_answer_with_claude(query, result['documents'], community)
            if ai_result:
                result['ai_answer'] = ai_result

    return jsonify(result)


def search_homeowners_internal(query, community=None):
    """Internal homeowner search - returns dict instead of Response."""
    safe_query = query.replace("'", "''")
    digits = normalize_phone(query)
    upper_query = query.upper()

    # Determine best search strategy
    if len(digits) >= 7:
        # Phone search
        last4 = digits[-4:]
        filter_expr = f"contains(cr258_primaryphone,'{last4}')"
        if community:
            filter_expr = f"contains(cr258_assoc_name,'{community}') and {filter_expr}"
        results = query_dataverse(filter_expr, top=20)
        if results:
            results = [r for r in results if digits[-10:] in normalize_phone(r.get('cr258_primaryphone', ''))]
    elif re.match(r'^[A-Z]{2,4}\d{3,8}$', upper_query) or re.match(r'^\d{4,8}$', query):
        # Account search
        filter_expr = f"contains(cr258_accountnumber,'{upper_query}')"
        if community:
            filter_expr = f"contains(cr258_assoc_name,'{community}') and {filter_expr}"
        results = query_dataverse(filter_expr, top=20)
    elif re.match(r'^\d+\s+\w+', query):
        # Address search
        filter_expr = f"contains(cr258_property_address,'{safe_query}')"
        if community:
            filter_expr += f" and contains(cr258_assoc_name,'{community}')"
        results = query_dataverse(filter_expr, top=20)
    else:
        # General name/address search
        filter_expr = f"(contains(cr258_owner_name,'{safe_query}') or contains(cr258_property_address,'{safe_query}'))"
        if community:
            filter_expr = f"contains(cr258_assoc_name,'{community}') and {filter_expr}"
        results = query_dataverse(filter_expr, top=20)

    homeowners = [format_homeowner(r) for r in (results or [])]
    return {'homeowners': homeowners, 'count': len(homeowners)}


@app.route('/api/documents/search')
def search_documents():
    """Direct document search endpoint."""
    query = request.args.get('q', '').strip()
    community = request.args.get('community', '').strip() or None
    top = int(request.args.get('top', 10))
    extract_answer = request.args.get('extract', 'true').lower() == 'true'

    if not query:
        return jsonify({'error': 'Query required'}), 400

    result = search_azure_documents(query, community, top)

    if extract_answer and result.get('documents') and ANTHROPIC_API_KEY:
        ai_result = extract_answer_with_claude(query, result['documents'], community)
        if ai_result:
            result['ai_answer'] = ai_result

    return jsonify(result)


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
