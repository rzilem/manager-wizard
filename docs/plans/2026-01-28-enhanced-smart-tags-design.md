# Enhanced Smart Tags System Design

**Date:** 2026-01-28
**Status:** Design Complete - Ready for Implementation
**Author:** Claude (Research Session)

---

## Executive Summary

This document outlines the design for 6 new smart tag badges in Manager Wizard to help customer service quickly identify homeowner context. These visual indicators will appear alongside existing badges (Board Member, New Owner, Attorney) to provide instant situational awareness.

---

## Current State Analysis

### Existing Badges

| Badge | Color | Icon | Trigger | Location |
|-------|-------|------|---------|----------|
| **BOARD MEMBER** | Purple (#7c3aed) | star | `cr258_boardmember=true` OR "Board" in tags | app.py:680 |
| **NEW OWNER** | Cyan (#0891b2) | user-plus | Settled within 90 days (`cr258_settleddate`) | app.py:650-655 |
| **ATTORNEY** | Red (var(--danger)) | - | `collection_status` contains "attorney" | index.html:2226 |
| **In Collections** | Brown (#7C2D12) | - | `collection_indicator === 'collections'` | index.html:2228 |
| **60+ Days** | Red | - | `collection_indicator === '60_days'` | index.html:2230 |
| **30+ Days** | Yellow | - | `collection_indicator === '30_days'` | index.html:2232 |

### Current Data Sources

**Dataverse Table:** `cr258_hoa_homeowners` (23,752+ records)

**Fields Currently Synced:**
```python
COLUMNS = [
    'cr258_owner_name', 'cr258_accountnumber', 'cr258_property_address',
    'cr258_assoc_name', 'cr258_balance', 'cr258_creditbalance',
    'cr258_primaryphone', 'cr258_primaryemail', 'cr258_collectionstatus',
    'cr258_vantacaurl', 'cr258_allphones', 'cr258_allemails', 'cr258_tenantname',
    'cr258_collprovider', 'cr258_lotnumber', 'cr258_unitnumber',
    'cr258_tags', 'cr258_lastpaymentdate', 'cr258_lastpaymentamount',
    'cr258_boardmember', 'modifiedon'
]
```

**Power BI Tables Available:**
- `pbi Homeowners` - Owner data with balances
- `vOwnerLedger2` - Transaction history
- `PA_XN_Weekly_Table` - Action items
- `CurrentStatus` - Violations (by AssocID, not homeowner)
- `Association` - Community data

---

## New Smart Tags Design

### 1. Payment Plan Badge

**Purpose:** Identify accounts currently on a structured payment arrangement.

| Attribute | Value |
|-----------|-------|
| **Label** | `ON PAYMENT PLAN` |
| **Color** | Indigo (#4f46e5) |
| **Icon** | `calendar-check` (FontAwesome) |
| **CSS Class** | `badge-payment-plan` |

**Trigger Condition:**
```python
is_on_payment_plan = rec.get('cr258_paymentplan') == True or rec.get('cr258_paymentplan') == 1
```

**Dataverse Field Required:**
- **Field Name:** `cr258_paymentplan`
- **Type:** Boolean (Two Option)
- **Display Name:** "On Payment Plan"
- **Default:** No

**Data Source:** Power BI table or Vantaca direct - need to identify where payment plan status is tracked.

**Customer Service Context:** Indicates homeowner has made arrangements. CS should:
- Acknowledge payment plan exists
- Not pressure for immediate full payment
- Direct questions about plan to collections team

---

### 2. Delinquent 90+ Days Badge

**Purpose:** Highlight severely delinquent accounts requiring escalation.

| Attribute | Value |
|-----------|-------|
| **Label** | `90+ DAYS` |
| **Color** | Deep Red (#991b1b) |
| **Icon** | `exclamation-circle` (FontAwesome) |
| **CSS Class** | `badge-90days` |

**Trigger Condition:**
```python
# Option 1: Calculate from delinquency days field
is_90plus = (rec.get('cr258_delinquencydays') or 0) >= 90

# Option 2: Already exists in collection_status
# Current system already has this via collection_indicator
# '60_days' and 'In Collections' covers this
```

**Dataverse Field Required:**
- **Field Name:** `cr258_delinquencydays`
- **Type:** Whole Number
- **Display Name:** "Days Delinquent"
- **Default:** 0

**Alternative:** Enhance existing `cr258_collectionstatus` to include "90 Days" bucket.

**Data Source:** Calculate from oldest unpaid assessment date in `vOwnerLedger2`.

**Customer Service Context:** High-priority accounts. CS should:
- Be extra empathetic (financial hardship likely)
- Mention payment plan options immediately
- Escalate to collections if homeowner is uncooperative

---

### 3. Tenant/Rental Badge

**Purpose:** Identify properties with tenant occupants (owner is landlord).

| Attribute | Value |
|-----------|-------|
| **Label** | `RENTAL` |
| **Color** | Blue (#1e40af) |
| **Icon** | `user-friends` (FontAwesome) |
| **CSS Class** | `badge-rental` |

**Trigger Condition:**
```python
# Tenant name field already exists and is synced
is_rental = bool(rec.get('cr258_tenantname'))
```

**Dataverse Field Required:** NONE - Already have `cr258_tenantname` field!

**Current Issue:** The tenant name displays in card-tags section but doesn't have a prominent badge.

**Customer Service Context:** Important distinction:
- Caller may be tenant OR owner
- Tenant questions → limited info (refer to owner or landlord)
- Owner questions → full access
- Violations → notify owner, not tenant

---

### 4. VIP / Long-term Owner Badge

**Purpose:** Identify homeowners who have been in the community 10+ years (loyal customers).

| Attribute | Value |
|-----------|-------|
| **Label** | `VIP` or `10+ YEARS` |
| **Color** | Gold (#ca8a04) |
| **Icon** | `crown` or `award` (FontAwesome) |
| **CSS Class** | `badge-vip` |

**Trigger Condition:**
```python
from datetime import datetime, timedelta

# Calculate from purchase/settle date
settle_date = rec.get('cr258_settleddate')
if settle_date:
    try:
        settled_dt = datetime.fromisoformat(settle_date.replace('Z', '+00:00'))
        years_owned = (datetime.now() - settled_dt.replace(tzinfo=None)).days / 365.25
        is_vip = years_owned >= 10
    except:
        is_vip = False
else:
    is_vip = False
```

**Dataverse Field Required:** NONE - Already have `cr258_settleddate`! Just needs calculation.

**Customer Service Context:** VIP treatment:
- Extra courtesy and patience
- "Thank you for being with us for over 10 years"
- Prioritize their issues
- May have institutional knowledge of community history

---

### 5. Recent Violation Badge

**Purpose:** Alert CS that homeowner has open violations (may call upset).

| Attribute | Value |
|-----------|-------|
| **Label** | `VIOLATION` or `OPEN VIOLATION` |
| **Color** | Orange (#ea580c) |
| **Icon** | `triangle-exclamation` (FontAwesome) |
| **CSS Class** | `badge-violation` |

**Trigger Condition:**
```python
has_open_violations = (rec.get('cr258_openviolations') or 0) > 0
```

**Dataverse Field Required:**
- **Field Name:** `cr258_openviolations`
- **Type:** Whole Number
- **Display Name:** "Open Violations"
- **Default:** 0

**Data Source Challenge:**
Violations in Power BI are stored by **community (AssocID)** in `CurrentStatus` and `ActionItemDetails` tables, NOT linked to individual homeowner records. There is no `account_number` or `property_address` field to join on.

**Solution Required:** Modify `dataverse-copilot-sync` to:
1. Query violations from Vantaca API (if available) OR
2. Match violations to homeowners using property address fuzzy matching OR
3. Create new Vantaca report that links violations to accounts

**Customer Service Context:** Critical awareness:
- Homeowner may be calling to dispute violation
- Have empathy - violations can be emotional
- Be prepared to explain violation process
- Do NOT take sides or make promises

---

### 6. Recent Communication Badge

**Purpose:** Show that staff recently contacted this homeowner (within 7 days).

| Attribute | Value |
|-----------|-------|
| **Label** | `RECENT CONTACT` |
| **Color** | Teal (#0d9488) |
| **Icon** | `comments` (FontAwesome) |
| **CSS Class** | `badge-recent-contact` |

**Trigger Condition:**
```python
from datetime import datetime, timedelta

last_contact = rec.get('cr258_lastcontactdate')
if last_contact:
    try:
        contact_dt = datetime.fromisoformat(last_contact.replace('Z', '+00:00'))
        days_since = (datetime.now() - contact_dt.replace(tzinfo=None)).days
        is_recent_contact = days_since <= 7
    except:
        is_recent_contact = False
else:
    is_recent_contact = False
```

**Dataverse Field Required:**
- **Field Name:** `cr258_lastcontactdate`
- **Type:** DateTime
- **Display Name:** "Last Contact Date"
- **Default:** null

**Data Source Options:**
1. **Phone AI Agent:** Log calls to Dataverse (already doing this in `cr258_phone_calls`)
2. **Email sync:** Track last email sent to homeowner
3. **Vantaca XN history:** Pull from action item updates

**Customer Service Context:** Continuity:
- "I see we spoke with you recently about..."
- Avoid repeating information already shared
- Check notes from previous contact

---

## Implementation Plan

### Phase 1: Quick Wins (No Dataverse Changes)

**Badges that can be implemented immediately:**

1. **RENTAL Badge** - `cr258_tenantname` already exists
2. **VIP Badge** - Calculate from existing `cr258_settleddate`

**Code Changes:**

```python
# In app.py format_homeowner() function, add:

# Tenant/Rental badge
is_rental = bool(rec.get('cr258_tenantname'))

# VIP/Long-term owner badge (10+ years)
is_vip = False
settled_date = rec.get('cr258_settleddate')
if settled_date:
    try:
        settled_dt = datetime.fromisoformat(settled_date.replace('Z', '+00:00'))
        years_owned = (now - settled_dt.replace(tzinfo=None)).days / 365.25
        is_vip = years_owned >= 10
    except:
        pass

# Return these in the response
return {
    # ... existing fields ...
    'is_rental': is_rental,
    'is_vip': is_vip,
}
```

```html
<!-- In index.html renderHomeownerCard() function, add badges: -->

// Rental badge
let rentalBadge = '';
if (h.is_rental) {
    rentalBadge = '<span class="status-badge badge-rental"><i class="fas fa-user-friends"></i> RENTAL</span>';
}

// VIP badge
let vipBadge = '';
if (h.is_vip) {
    vipBadge = '<span class="status-badge badge-vip"><i class="fas fa-crown"></i> VIP</span>';
}

// Insert in badge row
${boardMemberBadge}${newOwnerBadge}${vipBadge}${rentalBadge}${statusBadge}
```

```css
/* Add to CSS */
.badge-rental { background: #1e40af; color: white; }
.badge-vip { background: #ca8a04; color: white; }
```

### Phase 2: Dataverse Schema Updates

**New fields to add to `cr258_hoa_homeowners` table:**

| Field | Schema Name | Type | Description |
|-------|-------------|------|-------------|
| On Payment Plan | `cr258_paymentplan` | Boolean | True if on payment arrangement |
| Days Delinquent | `cr258_delinquencydays` | Whole Number | Days since oldest unpaid balance |
| Open Violations | `cr258_openviolations` | Whole Number | Count of open violations |
| Last Contact Date | `cr258_lastcontactdate` | DateTime | Last staff contact with homeowner |

**Script to add fields:**
```python
# Create file: dataverse-copilot-sync/add_smart_tag_fields.py

import requests
import msal
import json

# Load config
with open('config.json') as f:
    config = json.load(f)

dv = config['dataverse']
env_url = dv['environment_url'].rstrip('/')

# Get token
app = msal.ConfidentialClientApplication(
    dv['client_id'],
    authority=f"https://login.microsoftonline.com/{dv['tenant_id']}",
    client_credential=dv['client_secret']
)
result = app.acquire_token_for_client(scopes=[f"{env_url}/.default"])
token = result['access_token']

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json',
    'OData-MaxVersion': '4.0',
    'OData-Version': '4.0'
}

base_url = f"{env_url}/api/data/v9.2/EntityDefinitions(LogicalName='cr258_hoa_homeowner')/Attributes"

# Field definitions
fields = [
    {
        "@odata.type": "#Microsoft.Dynamics.CRM.BooleanAttributeMetadata",
        "SchemaName": "cr258_paymentplan",
        "DisplayName": {"@odata.type": "#Microsoft.Dynamics.CRM.Label", "LocalizedLabels": [{"@odata.type": "#Microsoft.Dynamics.CRM.LocalizedLabel", "Label": "On Payment Plan", "LanguageCode": 1033}]},
        "RequiredLevel": {"Value": "None"},
        "OptionSet": {"TrueOption": {"Value": 1, "Label": {"LocalizedLabels": [{"Label": "Yes", "LanguageCode": 1033}]}}, "FalseOption": {"Value": 0, "Label": {"LocalizedLabels": [{"Label": "No", "LanguageCode": 1033}]}}}
    },
    {
        "@odata.type": "#Microsoft.Dynamics.CRM.IntegerAttributeMetadata",
        "SchemaName": "cr258_delinquencydays",
        "DisplayName": {"@odata.type": "#Microsoft.Dynamics.CRM.Label", "LocalizedLabels": [{"@odata.type": "#Microsoft.Dynamics.CRM.LocalizedLabel", "Label": "Days Delinquent", "LanguageCode": 1033}]},
        "RequiredLevel": {"Value": "None"},
        "MinValue": 0,
        "MaxValue": 9999
    },
    {
        "@odata.type": "#Microsoft.Dynamics.CRM.IntegerAttributeMetadata",
        "SchemaName": "cr258_openviolations",
        "DisplayName": {"@odata.type": "#Microsoft.Dynamics.CRM.Label", "LocalizedLabels": [{"@odata.type": "#Microsoft.Dynamics.CRM.LocalizedLabel", "Label": "Open Violations", "LanguageCode": 1033}]},
        "RequiredLevel": {"Value": "None"},
        "MinValue": 0,
        "MaxValue": 999
    },
    {
        "@odata.type": "#Microsoft.Dynamics.CRM.DateTimeAttributeMetadata",
        "SchemaName": "cr258_lastcontactdate",
        "DisplayName": {"@odata.type": "#Microsoft.Dynamics.CRM.Label", "LocalizedLabels": [{"@odata.type": "#Microsoft.Dynamics.CRM.LocalizedLabel", "Label": "Last Contact Date", "LanguageCode": 1033}]},
        "RequiredLevel": {"Value": "None"},
        "Format": "DateAndTime"
    }
]

for field in fields:
    print(f"Creating {field['SchemaName']}...")
    resp = requests.post(base_url, headers=headers, json=field)
    if resp.status_code in [200, 201, 204]:
        print(f"  OK: {field['SchemaName']} created")
    else:
        print(f"  ERROR: {resp.status_code} - {resp.text[:200]}")
```

### Phase 3: Sync Script Updates

**Modify `daily_sync_v3.py` to populate new fields:**

```python
# Add to DAX query - need to source this data:
# - cr258_paymentplan: Source TBD (Vantaca payment arrangement data)
# - cr258_delinquencydays: Calculate from oldest unpaid assessment
# - cr258_openviolations: Match violations to homeowner by address
# - cr258_lastcontactdate: Aggregate from cr258_phone_calls + email logs

# Example delinquency days calculation (add to sync):
def calculate_delinquency_days(owner_id):
    """Calculate days since oldest unpaid balance."""
    query = f"""
    EVALUATE
    SELECTCOLUMNS(
        FILTER(vOwnerLedger2,
            vOwnerLedger2[OwnerID] = {owner_id}
            && vOwnerLedger2[Amount] > 0
            && vOwnerLedger2[TypeDescr] = "Assessment"
        ),
        "Date", MIN(vOwnerLedger2[LedgerDate])
    )
    """
    rows = run_dax(query)
    if rows and rows[0].get('[Date]'):
        oldest_date = datetime.fromisoformat(rows[0]['[Date]'].replace('Z', '+00:00'))
        return (datetime.now() - oldest_date).days
    return 0
```

### Phase 4: Violation Badge (Complex)

**Challenge:** Violations are stored by community, not by homeowner address.

**Solution Options:**

1. **Vantaca API Query:** If Vantaca has an API to get violations by property, use that directly.

2. **Power BI Address Matching:** Query `CurrentStatus` violations and match to homeowner by address:
   ```python
   # In daily sync, for each homeowner:
   violations = get_violations_for_community(assoc_id)
   for v in violations:
       if fuzzy_match(v['property_address'], homeowner['address']):
           open_violation_count += 1
   ```

3. **Vantaca Report:** Create a custom Vantaca report that exports violations with account numbers.

**Recommendation:** Start with option 2 (address matching) as a proof of concept, then refine.

---

## UI Design Mockup

### Badge Row Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  John Smith                                              $1,250.00  │
│  Falcon Pointe HOA                                        Balance   │
│                                                                     │
│  [⭐ BOARD MEMBER] [👤+ NEW OWNER] [👑 VIP] [👥 RENTAL]             │
│  [⚠️ VIOLATION] [📅 PAYMENT PLAN] [💬 RECENT CONTACT]               │
│  [🔴 90+ DAYS]                                                      │
│                                                                     │
│  Address: 1234 Main Street                                          │
│  Phone: (512) 555-1234                                              │
│  ...                                                                │
└─────────────────────────────────────────────────────────────────────┘
```

### Badge Priority Order

Display badges in this order (most important first):
1. **ATTORNEY** (red - highest priority warning)
2. **90+ DAYS** (deep red - severe delinquency)
3. **In Collections** (brown)
4. **VIOLATION** (orange - active issue)
5. **BOARD MEMBER** (purple - VIP status)
6. **VIP** (gold - 10+ years)
7. **NEW OWNER** (cyan - onboarding context)
8. **PAYMENT PLAN** (indigo - arrangement exists)
9. **RENTAL** (blue - tenant context)
10. **RECENT CONTACT** (teal - continuity)

### Responsive Behavior

On mobile (< 768px), badges should wrap to multiple lines and maintain readability:
- Each badge min-width: 80px
- Gap between badges: 4px
- Font size: 0.65rem (same as current)

---

## CSS Additions

```css
/* New Smart Tag Badge Styles */
.badge-payment-plan {
    background: #4f46e5;
    color: white;
}

.badge-90days {
    background: #991b1b;
    color: white;
}

.badge-rental {
    background: #1e40af;
    color: white;
}

.badge-vip {
    background: linear-gradient(135deg, #ca8a04 0%, #a16207 100%);
    color: white;
}

.badge-violation {
    background: #ea580c;
    color: white;
}

.badge-recent-contact {
    background: #0d9488;
    color: white;
}

/* Add icon spacing for all badges */
.status-badge i {
    margin-right: 4px;
}

/* Badge wrap container */
.card-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 4px;
}
```

---

## Testing Checklist

### Phase 1 Tests (Quick Wins)

- [ ] RENTAL badge appears when `cr258_tenantname` has value
- [ ] RENTAL badge hidden when `cr258_tenantname` is empty/null
- [ ] VIP badge appears when `cr258_settleddate` is 10+ years ago
- [ ] VIP badge hidden for owners < 10 years
- [ ] VIP badge handles null/invalid settle dates gracefully
- [ ] Multiple badges display correctly in row
- [ ] Badges wrap properly on mobile screens

### Phase 2 Tests (New Fields)

- [ ] Payment Plan badge appears when `cr258_paymentplan = true`
- [ ] 90+ Days badge appears when `cr258_delinquencydays >= 90`
- [ ] Violation badge appears when `cr258_openviolations > 0`
- [ ] Recent Contact badge appears when `cr258_lastcontactdate` within 7 days
- [ ] Sync script populates new fields correctly
- [ ] Performance acceptable with additional fields

---

## Rollout Plan

| Week | Milestone |
|------|-----------|
| Week 1 | Implement Phase 1 (RENTAL + VIP badges) |
| Week 1 | Deploy to production, gather feedback |
| Week 2 | Create Dataverse fields (Phase 2) |
| Week 2 | Update daily sync script |
| Week 3 | Implement Payment Plan + 90+ Days badges |
| Week 3 | Research violation data source |
| Week 4 | Implement Violation badge |
| Week 4 | Implement Recent Contact badge |
| Week 5 | Full testing and refinement |

---

## Open Questions

1. **Payment Plan Source:** Where is payment plan status stored in Vantaca/Power BI? Need to identify the table/field.

2. **Violation Linking:** Best approach to link violations (stored by community) to individual homeowners? Options:
   - Vantaca API (if exists)
   - Address matching (fuzzy)
   - Custom report from Vantaca

3. **Recent Contact Sources:** Should this include:
   - Phone AI calls only?
   - All inbound calls?
   - Outbound emails from managers?
   - Vantaca action item updates?

4. **Badge Limit:** Should there be a maximum number of badges displayed? Consider collapsing to "+3 more" if too many.

---

## Appendix: Current File Locations

| File | Purpose |
|------|---------|
| `manager-wizard/app.py` | Main Flask app, format_homeowner() function |
| `manager-wizard/templates/index.html` | Frontend template, renderHomeownerCard() function |
| `dataverse-copilot-sync/daily_sync_v3.py` | Daily sync script, populates homeowner data |
| `dataverse-copilot-sync/config.json` | Azure/Dataverse credentials |

---

*Document created 2026-01-28 for Manager Wizard enhanced smart tags feature.*
