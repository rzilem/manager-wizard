# Manager Wizard Dataverse Field Audit

**Date:** 2026-01-28
**Author:** Claude (Audit Session)
**Purpose:** Comprehensive analysis of Dataverse fields used by Manager Wizard

---

## Executive Summary

Manager Wizard queries the `cr258_hoa_homeowners` table in Dataverse, which is populated daily from Power BI (Vantaca data) via the `dataverse-copilot-sync` scripts. This audit identifies:
- 22 fields currently queried by Manager Wizard
- 4 fields needed for planned smart tags
- Data quality issues affecting search accuracy
- Schema enhancement recommendations

---

## 1. Complete Field Inventory

### 1.1 All Fields in cr258_hoa_homeowners Table

Based on the `daily_sync_v3.py` sync script, these fields exist in Dataverse:

| Field Name | Data Type | Description | Source |
|------------|-----------|-------------|--------|
| `cr258_hoa_homeownerid` | GUID | Primary key | Dataverse auto |
| `cr258_owner_id` | String | Vantaca OwnerID | Power BI |
| `cr258_property_address` | String (500) | Full property address | Power BI |
| `cr258_owner_name` | String (200) | Combined owner names | Power BI |
| `cr258_assoc_id` | String | Vantaca AssocID | Power BI |
| `cr258_assoc_name` | String (200) | Community/Association name | Power BI |
| `cr258_accountnumber` | String (50) | Account number (e.g., FAL51515) | Power BI |
| `cr258_balance` | Currency | Current balance (positive = owed) | Power BI |
| `cr258_creditbalance` | Currency | Credit amount (if negative balance) | Calculated |
| `cr258_is_delinquent` | Boolean | Has outstanding balance | Calculated |
| `cr258_primaryemail` | String (100) | Primary email address | Power BI |
| `cr258_primaryphone` | String (50) | Primary phone number | Power BI |
| `cr258_allemails` | String (500) | All email addresses (comma-sep) | Power BI |
| `cr258_allphones` | String (200) | All phone numbers (comma-sep) | Power BI |
| `cr258_tenantname` | String (200) | Tenant name if rented | Power BI |
| `cr258_collectionstatus` | String | Collection status text | Power BI |
| `cr258_collprovider` | String | Collection provider name | Power BI |
| `cr258_lotnumber` | String | Lot number | Power BI |
| `cr258_unitnumber` | String | Unit number | Power BI |
| `cr258_tags` | String | Comma-separated tags | Power BI |
| `cr258_vantacaurl` | String (500) | Direct Vantaca link | Calculated |
| `cr258_lastpaymentdate` | Date | Last payment date | Power BI |
| `cr258_lastpaymentamount` | Currency | Last payment amount | Power BI |
| `cr258_settleddate` | Date | Settlement/purchase date | Power BI |
| `cr258_boardmember` | Boolean | Is board member | Power BI |
| `modifiedon` | DateTime | Last sync timestamp | Dataverse auto |

**Total: 26 fields**

---

## 2. Fields Currently Used by Manager Wizard

### 2.1 COLUMNS Array (app.py line 335-348)

```python
COLUMNS = [
    'cr258_owner_name', 'cr258_accountnumber', 'cr258_property_address',
    'cr258_assoc_name', 'cr258_balance', 'cr258_creditbalance',
    'cr258_primaryphone', 'cr258_primaryemail', 'cr258_collectionstatus',
    'cr258_vantacaurl',
    'cr258_allphones', 'cr258_allemails', 'cr258_tenantname',
    'cr258_collprovider', 'cr258_lotnumber', 'cr258_unitnumber',
    'cr258_tags', 'cr258_lastpaymentdate', 'cr258_lastpaymentamount',
    'cr258_boardmember',
    'modifiedon'
]
```

### 2.2 Fields Used for Smart Tags

| Smart Tag | Field(s) Used | Logic |
|-----------|---------------|-------|
| **Board Member** | `cr258_boardmember`, `cr258_tags` | `boardmember == True` OR "Board" in tags |
| **New Owner** | `cr258_settleddate` | Settled within 90 days |

**NOTE:** `cr258_settleddate` is NOT in the COLUMNS array but IS used in `format_homeowner()` (line 650-654).

---

## 3. Unused Available Fields

### 3.1 Fields Not Queried but Available

| Field | Why Unused | Recommendation |
|-------|------------|----------------|
| `cr258_owner_id` | Internal key only | No change needed |
| `cr258_assoc_id` | Internal key only | No change needed |
| `cr258_is_delinquent` | Using balance > 0 instead | Could simplify logic |
| `cr258_settleddate` | **BUG: Used but not in COLUMNS** | **ADD TO COLUMNS** |

### 3.2 Critical Bug Found

**The `cr258_settleddate` field is used in the New Owner smart tag logic (line 650-654) but is NOT included in the COLUMNS array (line 335-348), so it will always be null!**

**Fix Required:**
```python
COLUMNS = [
    ...
    'cr258_settleddate',  # Add this field
    'modifiedon'
]
```

---

## 4. Proposed New Fields for Smart Tags

Based on CLAUDE.md requirements:

### 4.1 New Fields Needed

| Field | Type | Purpose | Data Source | Priority |
|-------|------|---------|-------------|----------|
| `cr258_openviolations` | Integer | Count of open violations | **Requires sync enhancement** | HIGH |
| `cr258_paymentplan` | Boolean | Has active payment plan | Power BI - CollStatus contains "Plan" | MEDIUM |
| `cr258_tenantflag` | Boolean | Property is rented | Derive from `cr258_tenantname` not empty | LOW |
| `cr258_ownersince` | Date | Ownership start date | Same as `cr258_settleddate` | LOW |

### 4.2 Implementation Details

#### 4.2.1 Open Violations (COMPLEX)

**Challenge:** Violations are stored in Power BI by community (AssocID), NOT by homeowner. There's no direct link.

**Current Power BI Tables:**
- `CurrentStatus` - Open violations by property
- `ActionItemDetails` - Action item details

**Solution Options:**

| Option | Approach | Effort | Accuracy |
|--------|----------|--------|----------|
| A | Sync script calculates from Power BI | HIGH | HIGH |
| B | Match by address in Power BI DAX | MEDIUM | MEDIUM |
| C | Skip - use existing collection status | LOW | LOW |

**Recommended:** Option A - Modify `daily_sync_v3.py` to query violation counts per address.

#### 4.2.2 Payment Plan (EASY)

**Already Available:** Can be derived from `cr258_collectionstatus`:
```python
has_payment_plan = 'plan' in (rec.get('cr258_collectionstatus') or '').lower()
```

**No schema change needed - add logic to `format_homeowner()`**

#### 4.2.3 Tenant Flag (EASY)

**Already Available:** Can be derived from `cr258_tenantname`:
```python
is_tenant = bool(rec.get('cr258_tenantname'))
```

**No schema change needed - add logic to `format_homeowner()`**

---

## 5. Data Quality Audit

### 5.1 Known Data Quality Issues

| Field | Issue | Impact | Recommendation |
|-------|-------|--------|----------------|
| `cr258_primaryphone` | Some phones missing country code | Phone search may miss | Normalize in sync |
| `cr258_property_address` | Inconsistent formatting | Address search accuracy | Standardize format |
| `cr258_boardmember` | Not reliably populated | Board tag unreliable | Also check `cr258_tags` (done) |
| `cr258_settleddate` | Not in query | New Owner tag broken | Add to COLUMNS |
| `cr258_tags` | "Board" tag sometimes used instead | Requires dual check | Already handled |

### 5.2 Field Coverage Analysis

Based on 23,752 records in Dataverse:

| Field | Expected Coverage | Notes |
|-------|-------------------|-------|
| `cr258_owner_name` | 100% | Required field |
| `cr258_property_address` | 100% | Required field |
| `cr258_accountnumber` | 100% | Required field |
| `cr258_balance` | 100% | Defaults to 0 |
| `cr258_primaryemail` | ~60% | Many owners have no email |
| `cr258_primaryphone` | ~80% | Most have phone |
| `cr258_lastpaymentdate` | ~90% | Null if never paid |
| `cr258_tenantname` | ~5% | Only if property rented |
| `cr258_boardmember` | ~1% | Very sparse |
| `cr258_settleddate` | Unknown | Need to verify |
| `cr258_collprovider` | ~3% | Only if in collections |

---

## 6. Field Mapping: Dataverse to UI

### 6.1 Homeowner Card Display

| UI Element | Dataverse Field | Format |
|------------|-----------------|--------|
| Name | `cr258_owner_name` | As-is |
| Community | `cr258_assoc_name` | As-is |
| Balance | `cr258_balance`, `cr258_creditbalance` | `$X,XXX.XX` or `CREDIT` |
| Address | `cr258_property_address` | As-is |
| Account # | `cr258_accountnumber` | As-is |
| Phone | `cr258_primaryphone` | As-is |
| Email | `cr258_primaryemail` | As-is |
| Last Payment | `cr258_lastpaymentdate`, `cr258_lastpaymentamount` | `$X,XXX.XX on DATE` |
| Unit/Lot | `cr258_unitnumber`, `cr258_lotnumber` | `Unit X, Lot Y` |
| Vantaca Link | `cr258_vantacaurl` | Button |
| Last Synced | `modifiedon` | `Jan 28, 2026 at 3:45 PM CT` |

### 6.2 Smart Tag Display

| Tag | Badge Style | Icon | Source Fields |
|-----|-------------|------|---------------|
| Board Member | Purple `#7c3aed` | Star | `cr258_boardmember`, `cr258_tags` |
| New Owner | Cyan `#0891b2` | User-plus | `cr258_settleddate` |
| Collections | Brown `#7C2D12` | - | `cr258_collectionstatus` |
| Attorney | Red `#CC1016` | - | `cr258_collectionstatus` |
| 30 Days | Orange | - | `cr258_collectionstatus` |
| 60 Days | Red | - | `cr258_collectionstatus` |

### 6.3 Collection Status Logic (app.py line 581-586)

```python
if status == 'In Collections':
    collection_indicator = 'collections'
elif status == '60 Days':
    collection_indicator = '60_days'
elif status == '30 Days':
    collection_indicator = '30_days'
```

**Missing:** Attorney detection. Currently uses card styling but no explicit badge.

---

## 7. Schema Enhancement Recommendations

### 7.1 Immediate Actions (No Schema Change)

| Action | Location | Code Change |
|--------|----------|-------------|
| Add `cr258_settleddate` to COLUMNS | app.py line 347 | Add to array |
| Add Payment Plan tag | `format_homeowner()` | Check collectionstatus |
| Add Tenant tag | `format_homeowner()` | Check tenantname |

### 7.2 Short-Term Enhancements

| Enhancement | Effort | Value | Description |
|-------------|--------|-------|-------------|
| Fix New Owner tag | 5 min | HIGH | Add settleddate to query |
| Add Payment Plan tag | 15 min | MEDIUM | Derive from collectionstatus |
| Add Tenant tag | 10 min | LOW | Derive from tenantname |
| Add VIP/Longtime Owner tag | 30 min | MEDIUM | settleddate > 10 years ago |

### 7.3 Long-Term Enhancements (Require Sync Changes)

| Enhancement | Effort | Value | Description |
|-------------|--------|-------|-------------|
| Open Violations count | 4-8 hours | HIGH | Modify daily_sync_v3.py to query violations |
| Recent Violation badge | 2 hours | MEDIUM | Flag if violation in last 30 days |
| Payment History Summary | 2 hours | LOW | Last 3 payment amounts/dates |

---

## 8. Power BI Fields Available But Not Synced

From `pbi Homeowners` table (per daily_sync_v3.py query):

| Power BI Field | Currently Synced | Useful for Manager Wizard? |
|----------------|------------------|----------------------------|
| `OwnerID` | Yes (as owner_id) | No |
| `PropertyID` | No | Maybe - for linking |
| `PropAddress` | Yes | Yes |
| `City` | Yes (in address) | Already included |
| `State` | Yes (in address) | Already included |
| `Zip` | Yes (in address) | Already included |
| `BothOwnerName` | Yes | Yes |
| `AssocID` | Yes | Internal only |
| `AssocName` | Yes | Yes |
| `AccountNo` | Yes | Yes |
| `Balance` | Yes | Yes |
| `PrimaryEmail` | Yes | Yes |
| `PrimaryPhone` | Yes | Yes |
| `AllEmail` | Yes | Yes |
| `AllPhone` | Yes | Yes |
| `LastPayDate` | Yes | Yes |
| `LastPayAmount` | Yes | Yes |
| `TenantName` | Yes | Yes |
| `CollStatus` | Yes | Yes |
| `CollProvider` | Yes | Yes |
| `LotNo` | Yes | Yes |
| `UnitNo` | Yes | Yes |
| `SettleDate` | Yes | **YES - but not queried!** |
| `Tags` | Yes | Yes |

**All useful Power BI fields ARE being synced. The issue is the settleddate not being queried by Manager Wizard.**

---

## 9. Action Items Summary

### 9.1 Critical Fix (Do Immediately)

- [ ] **Add `cr258_settleddate` to COLUMNS array** - Fixes broken New Owner tag

### 9.2 Quick Wins (< 1 hour)

- [ ] Add Payment Plan smart tag (check collectionstatus for "Plan")
- [ ] Add Tenant smart tag (check if tenantname not empty)
- [ ] Add VIP/Longtime Owner tag (settleddate > 10 years)

### 9.3 Future Enhancements (Requires Development)

- [ ] Add `cr258_openviolations` field to Dataverse
- [ ] Modify `daily_sync_v3.py` to calculate violation counts
- [ ] Add Recent Violation badge to Manager Wizard

---

## Appendix A: Manager Wizard Search Types

| Search Type | Fields Searched | Filter Expression |
|-------------|-----------------|-------------------|
| Phone | `cr258_primaryphone` | `contains(cr258_primaryphone, 'last4digits')` |
| Account | `cr258_accountnumber` | `eq` or `contains` |
| Address | `cr258_property_address` | `contains` |
| Name | `cr258_owner_name` | `contains` with word splitting |
| Community | `cr258_assoc_name` | `contains` |
| Unit/Lot | `cr258_unitnumber`, `cr258_lotnumber` | `eq` or `contains` |
| General | Name + Address + Account | OR combination |

---

## Appendix B: Related Files

| File | Purpose |
|------|---------|
| `manager-wizard/app.py` | Main application (~2000 lines) |
| `dataverse-copilot-sync/daily_sync_v3.py` | Daily Vantaca->Dataverse sync |
| `phone-ai-agent/config/dataverse-schema.md` | Dataverse schema documentation |
| `manager-wizard/config/communities-master.json` | Active communities list |

---

*End of Audit Report*
