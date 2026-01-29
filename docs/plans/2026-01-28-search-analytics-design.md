# Manager Wizard Search Analytics System - Design Document

**Created:** 2026-01-28
**Author:** Claude Opus 4.5
**Status:** DESIGN COMPLETE - Ready for Implementation
**Supabase Project:** hthaomwoizcyfeduptqm

---

## Executive Summary

This document defines a comprehensive search analytics system for Manager Wizard to track usage patterns, measure search effectiveness, and drive continuous improvement. The system will capture every search event, analyze success/failure patterns, and provide actionable recommendations for knowledge base expansion.

**Key Goals:**
1. Track 100% of searches with full context
2. Define clear success metrics (found vs not found, AI answer quality)
3. Surface popular searches to prioritize KB content creation
4. Identify failed searches to guide document coverage expansion
5. Provide real-time dashboard for Command Center integration

---

## 1. Analytics Schema (Supabase)

### Core Tables

```sql
-- ============================================
-- SEARCH EVENTS (main analytics table)
-- ============================================
CREATE TABLE IF NOT EXISTS mw_search_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    -- Timing
    searched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    response_time_ms INTEGER, -- Total API response time

    -- User Context
    user_email TEXT, -- SSO email (psprop.net)
    user_name TEXT, -- From SSO display name
    session_id TEXT, -- Browser session for grouping related searches

    -- Query Details
    query_raw TEXT NOT NULL, -- Exact user input
    query_normalized TEXT, -- Lowercase, trimmed
    query_type TEXT, -- 'homeowner', 'document', 'both', 'auto'
    detected_type TEXT, -- What we auto-detected

    -- Community Context
    community_filter TEXT, -- User-selected community filter
    community_detected TEXT, -- Community extracted from query
    community_normalized TEXT, -- Normalized for matching

    -- Search Parameters
    search_mode TEXT, -- 'unified', 'homeowner', 'document', 'suggest'
    include_ai_answer BOOLEAN DEFAULT true,

    -- Results Summary
    homeowner_count INTEGER DEFAULT 0,
    document_count INTEGER DEFAULT 0,
    has_ai_answer BOOLEAN DEFAULT false,

    -- AI Answer Details (if applicable)
    ai_answer_text TEXT, -- The extracted answer
    ai_answer_source TEXT, -- Document name
    ai_answer_confidence TEXT, -- 'high', 'medium', 'low'
    ai_extraction_type TEXT, -- 'fence', 'pool', 'pet', etc.

    -- Success Metrics
    result_status TEXT, -- 'found', 'partial', 'not_found', 'error'
    is_success BOOLEAN GENERATED ALWAYS AS (
        result_status IN ('found', 'partial')
    ) STORED,

    -- Error Details (if applicable)
    error_type TEXT, -- 'dataverse_timeout', 'azure_search_error', etc.
    error_message TEXT,

    -- User Feedback (populated later via feedback API)
    user_rating INTEGER, -- 1-5 stars (null if no feedback)
    user_feedback TEXT, -- Optional comment
    feedback_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_search_events_searched_at ON mw_search_events(searched_at DESC);
CREATE INDEX IF NOT EXISTS idx_search_events_user ON mw_search_events(user_email);
CREATE INDEX IF NOT EXISTS idx_search_events_query ON mw_search_events(query_normalized);
CREATE INDEX IF NOT EXISTS idx_search_events_community ON mw_search_events(community_detected);
CREATE INDEX IF NOT EXISTS idx_search_events_result ON mw_search_events(result_status);
CREATE INDEX IF NOT EXISTS idx_search_events_type ON mw_search_events(detected_type);
CREATE INDEX IF NOT EXISTS idx_search_events_success ON mw_search_events(is_success);

-- ============================================
-- SEARCH RESULTS DETAIL (for deep analysis)
-- ============================================
CREATE TABLE IF NOT EXISTS mw_search_results (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    search_event_id UUID NOT NULL REFERENCES mw_search_events(id) ON DELETE CASCADE,

    -- Result type
    result_type TEXT NOT NULL, -- 'homeowner', 'document'
    result_position INTEGER, -- 1-indexed position in results

    -- Homeowner result details (if applicable)
    homeowner_name TEXT,
    homeowner_account TEXT,
    homeowner_community TEXT,
    homeowner_address TEXT,

    -- Document result details (if applicable)
    document_title TEXT,
    document_path TEXT,
    document_community TEXT,
    document_type TEXT, -- 'ccr', 'rules', 'pool', etc.
    document_score NUMERIC(10,4), -- Azure search score

    -- User interaction (tracked via click events)
    was_clicked BOOLEAN DEFAULT false,
    clicked_at TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_search_results_event ON mw_search_results(search_event_id);
CREATE INDEX IF NOT EXISTS idx_search_results_clicked ON mw_search_results(was_clicked) WHERE was_clicked = true;

-- ============================================
-- POPULAR SEARCHES (pre-aggregated hourly)
-- ============================================
CREATE TABLE IF NOT EXISTS mw_popular_searches (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    -- Time bucket
    hour_bucket TIMESTAMP WITH TIME ZONE NOT NULL, -- Truncated to hour

    -- Query grouping
    query_normalized TEXT NOT NULL,
    detected_type TEXT,
    community_detected TEXT,

    -- Aggregated metrics
    search_count INTEGER DEFAULT 1,
    success_count INTEGER DEFAULT 0,
    avg_response_time_ms NUMERIC(10,2),

    -- User diversity
    unique_users INTEGER DEFAULT 1,
    user_emails TEXT[], -- Array of unique users

    -- Result patterns
    avg_homeowner_results NUMERIC(10,2),
    avg_document_results NUMERIC(10,2),
    ai_answer_rate NUMERIC(5,2), -- % with AI answer

    UNIQUE(hour_bucket, query_normalized, community_detected)
);

CREATE INDEX IF NOT EXISTS idx_popular_hour ON mw_popular_searches(hour_bucket DESC);
CREATE INDEX IF NOT EXISTS idx_popular_query ON mw_popular_searches(query_normalized);
CREATE INDEX IF NOT EXISTS idx_popular_count ON mw_popular_searches(search_count DESC);

-- ============================================
-- FAILED SEARCHES (for KB improvement)
-- ============================================
CREATE TABLE IF NOT EXISTS mw_failed_searches (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    -- Query pattern
    query_normalized TEXT NOT NULL,
    query_examples TEXT[], -- Sample raw queries

    -- Failure context
    failure_type TEXT, -- 'no_documents', 'no_homeowners', 'no_results', 'ai_extraction_failed'
    community_filter TEXT,
    detected_type TEXT,

    -- Aggregated metrics
    failure_count INTEGER DEFAULT 1,
    first_failed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_failed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- User impact
    unique_users INTEGER DEFAULT 1,
    user_emails TEXT[],

    -- Improvement tracking
    status TEXT DEFAULT 'new', -- 'new', 'acknowledged', 'in_progress', 'resolved'
    assigned_to TEXT, -- Staff member handling
    resolution_notes TEXT,
    resolved_at TIMESTAMP WITH TIME ZONE,

    -- Link to KB improvements
    kb_doc_created TEXT, -- Path to doc if created
    kb_doc_created_at TIMESTAMP WITH TIME ZONE,

    UNIQUE(query_normalized, community_filter, failure_type)
);

CREATE INDEX IF NOT EXISTS idx_failed_count ON mw_failed_searches(failure_count DESC);
CREATE INDEX IF NOT EXISTS idx_failed_status ON mw_failed_searches(status);
CREATE INDEX IF NOT EXISTS idx_failed_recent ON mw_failed_searches(last_failed_at DESC);

-- ============================================
-- DAILY STATS (pre-computed for dashboard)
-- ============================================
CREATE TABLE IF NOT EXISTS mw_daily_stats (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    stat_date DATE NOT NULL UNIQUE,

    -- Volume metrics
    total_searches INTEGER DEFAULT 0,
    unique_users INTEGER DEFAULT 0,
    unique_sessions INTEGER DEFAULT 0,

    -- Success metrics
    found_count INTEGER DEFAULT 0,
    partial_count INTEGER DEFAULT 0,
    not_found_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    success_rate NUMERIC(5,2), -- % (found + partial) / total

    -- Type breakdown
    homeowner_searches INTEGER DEFAULT 0,
    document_searches INTEGER DEFAULT 0,
    unified_searches INTEGER DEFAULT 0,

    -- AI metrics
    ai_answer_count INTEGER DEFAULT 0,
    ai_answer_rate NUMERIC(5,2), -- % with AI answer
    avg_ai_confidence_score NUMERIC(5,2),

    -- Performance
    avg_response_time_ms NUMERIC(10,2),
    p95_response_time_ms INTEGER,
    slowest_query TEXT,
    slowest_time_ms INTEGER,

    -- Top patterns (JSONB for flexibility)
    top_queries JSONB, -- [{"query": "...", "count": 50, "success_rate": 0.85}, ...]
    top_communities JSONB, -- [{"name": "Falcon Pointe", "count": 30}, ...]
    top_failed_queries JSONB, -- [{"query": "...", "count": 10}, ...]

    -- User activity
    top_users JSONB, -- [{"email": "...", "count": 25}, ...]
    peak_hour INTEGER, -- 0-23, hour with most searches

    computed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON mw_daily_stats(stat_date DESC);

-- ============================================
-- IMPROVEMENT RECOMMENDATIONS (AI-generated)
-- ============================================
CREATE TABLE IF NOT EXISTS mw_improvement_recommendations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    -- Recommendation type
    recommendation_type TEXT NOT NULL, -- 'create_doc', 'update_doc', 'add_alias', 'improve_prompt'
    priority TEXT DEFAULT 'medium', -- 'critical', 'high', 'medium', 'low'

    -- Details
    title TEXT NOT NULL,
    description TEXT,

    -- Impact analysis
    affected_queries TEXT[], -- Normalized queries this would help
    estimated_searches_impacted INTEGER, -- Based on failure count
    estimated_success_improvement NUMERIC(5,2), -- Projected % improvement

    -- Evidence
    evidence_query_samples TEXT[], -- Example failed queries
    evidence_communities TEXT[], -- Communities affected

    -- Action items
    suggested_action TEXT, -- Detailed instructions
    document_template TEXT, -- If type is 'create_doc'

    -- Status tracking
    status TEXT DEFAULT 'new', -- 'new', 'approved', 'in_progress', 'completed', 'rejected'
    assigned_to TEXT,
    approved_by TEXT,
    approved_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    rejection_reason TEXT,

    -- Metrics after completion
    post_completion_success_rate NUMERIC(5,2),
    verified_improvement BOOLEAN,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recommendations_status ON mw_improvement_recommendations(status);
CREATE INDEX IF NOT EXISTS idx_recommendations_priority ON mw_improvement_recommendations(priority);
CREATE INDEX IF NOT EXISTS idx_recommendations_type ON mw_improvement_recommendations(recommendation_type);
```

### Row Level Security (RLS)

```sql
-- Enable RLS on all tables
ALTER TABLE mw_search_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE mw_search_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE mw_popular_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE mw_failed_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE mw_daily_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE mw_improvement_recommendations ENABLE ROW LEVEL SECURITY;

-- Service role has full access (for Python scripts)
CREATE POLICY "Service role full access" ON mw_search_events FOR ALL USING (true);
CREATE POLICY "Service role full access" ON mw_search_results FOR ALL USING (true);
CREATE POLICY "Service role full access" ON mw_popular_searches FOR ALL USING (true);
CREATE POLICY "Service role full access" ON mw_failed_searches FOR ALL USING (true);
CREATE POLICY "Service role full access" ON mw_daily_stats FOR ALL USING (true);
CREATE POLICY "Service role full access" ON mw_improvement_recommendations FOR ALL USING (true);
```

### Useful Views

```sql
-- Real-time search success rate (last 24 hours)
CREATE OR REPLACE VIEW v_search_success_rate_24h AS
SELECT
    DATE_TRUNC('hour', searched_at) as hour,
    COUNT(*) as total_searches,
    SUM(CASE WHEN is_success THEN 1 ELSE 0 END) as successful_searches,
    ROUND(100.0 * SUM(CASE WHEN is_success THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate,
    AVG(response_time_ms)::INTEGER as avg_response_ms
FROM mw_search_events
WHERE searched_at > NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', searched_at)
ORDER BY hour DESC;

-- Most common failed queries (actionable)
CREATE OR REPLACE VIEW v_actionable_failed_queries AS
SELECT
    query_normalized,
    failure_type,
    community_filter,
    failure_count,
    unique_users,
    last_failed_at,
    status,
    CASE
        WHEN failure_count >= 10 AND unique_users >= 3 THEN 'critical'
        WHEN failure_count >= 5 AND unique_users >= 2 THEN 'high'
        WHEN failure_count >= 3 THEN 'medium'
        ELSE 'low'
    END as calculated_priority
FROM mw_failed_searches
WHERE status IN ('new', 'acknowledged')
ORDER BY failure_count DESC, unique_users DESC;

-- Community search patterns
CREATE OR REPLACE VIEW v_community_search_patterns AS
SELECT
    COALESCE(community_detected, 'No Community') as community,
    COUNT(*) as total_searches,
    SUM(CASE WHEN is_success THEN 1 ELSE 0 END) as successful,
    ROUND(100.0 * SUM(CASE WHEN is_success THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate,
    COUNT(DISTINCT user_email) as unique_users,
    AVG(document_count)::NUMERIC(10,2) as avg_docs_returned,
    SUM(CASE WHEN has_ai_answer THEN 1 ELSE 0 END) as ai_answers_provided
FROM mw_search_events
WHERE searched_at > NOW() - INTERVAL '30 days'
GROUP BY community_detected
ORDER BY total_searches DESC;

-- User activity leaderboard
CREATE OR REPLACE VIEW v_user_activity AS
SELECT
    user_email,
    user_name,
    COUNT(*) as search_count,
    COUNT(DISTINCT DATE(searched_at)) as active_days,
    ROUND(100.0 * SUM(CASE WHEN is_success THEN 1 ELSE 0 END) / COUNT(*), 2) as personal_success_rate,
    AVG(response_time_ms)::INTEGER as avg_response_ms,
    MAX(searched_at) as last_search
FROM mw_search_events
WHERE searched_at > NOW() - INTERVAL '30 days'
  AND user_email IS NOT NULL
GROUP BY user_email, user_name
ORDER BY search_count DESC;
```

### Database Functions

```sql
-- Log a search event (returns event ID)
CREATE OR REPLACE FUNCTION log_search_event(
    p_user_email TEXT,
    p_user_name TEXT,
    p_session_id TEXT,
    p_query_raw TEXT,
    p_query_type TEXT,
    p_detected_type TEXT,
    p_community_filter TEXT,
    p_community_detected TEXT,
    p_homeowner_count INTEGER,
    p_document_count INTEGER,
    p_has_ai_answer BOOLEAN,
    p_ai_answer_text TEXT,
    p_ai_answer_source TEXT,
    p_response_time_ms INTEGER
)
RETURNS UUID AS $$
DECLARE
    v_id UUID;
    v_result_status TEXT;
BEGIN
    -- Determine result status
    IF p_homeowner_count > 0 OR (p_document_count > 0 AND p_has_ai_answer) THEN
        v_result_status := 'found';
    ELSIF p_document_count > 0 THEN
        v_result_status := 'partial';
    ELSE
        v_result_status := 'not_found';
    END IF;

    -- Insert event
    INSERT INTO mw_search_events (
        user_email, user_name, session_id,
        query_raw, query_normalized, query_type, detected_type,
        community_filter, community_detected,
        homeowner_count, document_count,
        has_ai_answer, ai_answer_text, ai_answer_source,
        response_time_ms, result_status
    ) VALUES (
        p_user_email, p_user_name, p_session_id,
        p_query_raw, LOWER(TRIM(p_query_raw)), p_query_type, p_detected_type,
        p_community_filter, p_community_detected,
        p_homeowner_count, p_document_count,
        p_has_ai_answer, p_ai_answer_text, p_ai_answer_source,
        p_response_time_ms, v_result_status
    )
    RETURNING id INTO v_id;

    -- Update failed searches if no results
    IF v_result_status = 'not_found' THEN
        INSERT INTO mw_failed_searches (
            query_normalized, query_examples, failure_type,
            community_filter, detected_type, failure_count, user_emails
        ) VALUES (
            LOWER(TRIM(p_query_raw)),
            ARRAY[p_query_raw],
            CASE
                WHEN p_detected_type = 'homeowner' THEN 'no_homeowners'
                WHEN p_detected_type = 'document' THEN 'no_documents'
                ELSE 'no_results'
            END,
            p_community_filter, p_detected_type, 1,
            CASE WHEN p_user_email IS NOT NULL THEN ARRAY[p_user_email] ELSE NULL END
        )
        ON CONFLICT (query_normalized, community_filter, failure_type) DO UPDATE SET
            failure_count = mw_failed_searches.failure_count + 1,
            last_failed_at = NOW(),
            query_examples = CASE
                WHEN array_length(mw_failed_searches.query_examples, 1) < 5
                    AND NOT p_query_raw = ANY(mw_failed_searches.query_examples)
                THEN array_append(mw_failed_searches.query_examples, p_query_raw)
                ELSE mw_failed_searches.query_examples
            END,
            unique_users = CASE
                WHEN p_user_email IS NOT NULL AND NOT p_user_email = ANY(mw_failed_searches.user_emails)
                THEN mw_failed_searches.unique_users + 1
                ELSE mw_failed_searches.unique_users
            END,
            user_emails = CASE
                WHEN p_user_email IS NOT NULL
                    AND array_length(mw_failed_searches.user_emails, 1) < 20
                    AND NOT p_user_email = ANY(mw_failed_searches.user_emails)
                THEN array_append(mw_failed_searches.user_emails, p_user_email)
                ELSE mw_failed_searches.user_emails
            END;
    END IF;

    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- Compute daily stats (run via cron at midnight)
CREATE OR REPLACE FUNCTION compute_daily_stats(p_date DATE)
RETURNS UUID AS $$
DECLARE
    v_id UUID;
BEGIN
    INSERT INTO mw_daily_stats (
        stat_date,
        total_searches, unique_users, unique_sessions,
        found_count, partial_count, not_found_count, error_count,
        success_rate,
        homeowner_searches, document_searches, unified_searches,
        ai_answer_count, ai_answer_rate,
        avg_response_time_ms, p95_response_time_ms,
        top_queries, top_communities, top_failed_queries, top_users
    )
    SELECT
        p_date,
        COUNT(*),
        COUNT(DISTINCT user_email),
        COUNT(DISTINCT session_id),
        SUM(CASE WHEN result_status = 'found' THEN 1 ELSE 0 END),
        SUM(CASE WHEN result_status = 'partial' THEN 1 ELSE 0 END),
        SUM(CASE WHEN result_status = 'not_found' THEN 1 ELSE 0 END),
        SUM(CASE WHEN result_status = 'error' THEN 1 ELSE 0 END),
        ROUND(100.0 * SUM(CASE WHEN is_success THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2),
        SUM(CASE WHEN detected_type = 'homeowner' THEN 1 ELSE 0 END),
        SUM(CASE WHEN detected_type = 'document' THEN 1 ELSE 0 END),
        SUM(CASE WHEN detected_type = 'both' THEN 1 ELSE 0 END),
        SUM(CASE WHEN has_ai_answer THEN 1 ELSE 0 END),
        ROUND(100.0 * SUM(CASE WHEN has_ai_answer THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2),
        AVG(response_time_ms),
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms),
        (SELECT jsonb_agg(q) FROM (
            SELECT query_normalized as query, COUNT(*) as count,
                   ROUND(100.0 * SUM(CASE WHEN is_success THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
            FROM mw_search_events
            WHERE DATE(searched_at) = p_date
            GROUP BY query_normalized
            ORDER BY count DESC LIMIT 10
        ) q),
        (SELECT jsonb_agg(c) FROM (
            SELECT community_detected as name, COUNT(*) as count
            FROM mw_search_events
            WHERE DATE(searched_at) = p_date AND community_detected IS NOT NULL
            GROUP BY community_detected
            ORDER BY count DESC LIMIT 10
        ) c),
        (SELECT jsonb_agg(f) FROM (
            SELECT query_normalized as query, COUNT(*) as count
            FROM mw_search_events
            WHERE DATE(searched_at) = p_date AND NOT is_success
            GROUP BY query_normalized
            ORDER BY count DESC LIMIT 10
        ) f),
        (SELECT jsonb_agg(u) FROM (
            SELECT user_email as email, COUNT(*) as count
            FROM mw_search_events
            WHERE DATE(searched_at) = p_date AND user_email IS NOT NULL
            GROUP BY user_email
            ORDER BY count DESC LIMIT 10
        ) u)
    FROM mw_search_events
    WHERE DATE(searched_at) = p_date
    ON CONFLICT (stat_date) DO UPDATE SET
        total_searches = EXCLUDED.total_searches,
        unique_users = EXCLUDED.unique_users,
        unique_sessions = EXCLUDED.unique_sessions,
        found_count = EXCLUDED.found_count,
        partial_count = EXCLUDED.partial_count,
        not_found_count = EXCLUDED.not_found_count,
        error_count = EXCLUDED.error_count,
        success_rate = EXCLUDED.success_rate,
        homeowner_searches = EXCLUDED.homeowner_searches,
        document_searches = EXCLUDED.document_searches,
        unified_searches = EXCLUDED.unified_searches,
        ai_answer_count = EXCLUDED.ai_answer_count,
        ai_answer_rate = EXCLUDED.ai_answer_rate,
        avg_response_time_ms = EXCLUDED.avg_response_time_ms,
        p95_response_time_ms = EXCLUDED.p95_response_time_ms,
        top_queries = EXCLUDED.top_queries,
        top_communities = EXCLUDED.top_communities,
        top_failed_queries = EXCLUDED.top_failed_queries,
        top_users = EXCLUDED.top_users,
        computed_at = NOW()
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$ LANGUAGE plpgsql;
```

---

## 2. Search Event Logging - What to Capture

### Every Search Event

| Field | Source | Purpose |
|-------|--------|---------|
| **Timing** |||
| `searched_at` | Server timestamp | When search occurred |
| `response_time_ms` | `time.time()` diff | Performance tracking |
| **User Context** |||
| `user_email` | SSO session | Who searched |
| `user_name` | SSO session | Display name |
| `session_id` | Session cookie | Group related searches |
| **Query Details** |||
| `query_raw` | User input | Exact search text |
| `query_normalized` | `lower(trim(query))` | For aggregation |
| `query_type` | Request param | Explicit type if specified |
| `detected_type` | `detect_query_type()` | Auto-detected type |
| **Community** |||
| `community_filter` | Dropdown selection | User-selected filter |
| `community_detected` | `extract_community_from_query()` | Extracted from query |
| **Results** |||
| `homeowner_count` | Response | Number of homeowner results |
| `document_count` | Response | Number of document results |
| `has_ai_answer` | Response | Whether AI extracted an answer |
| `ai_answer_text` | Response | The extracted answer |
| `ai_answer_source` | Response | Source document name |
| `result_status` | Computed | 'found', 'partial', 'not_found', 'error' |

### Python Integration Points

Modify these endpoints in `app.py`:

1. **`/api/unified-search`** - Main unified search
2. **`/api/search`** - Homeowner-only search
3. **`/api/documents/search`** - Document-only search

### Sample Integration Code

```python
# Add to app.py imports
import uuid
from supabase import create_client, Client

# Supabase client
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://hthaomwoizcyfeduptqm.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')

_supabase_client = None

def get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is None and SUPABASE_KEY:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client

def log_search_analytics(
    user_email: str,
    user_name: str,
    query_raw: str,
    query_type: str,
    detected_type: str,
    community_filter: str,
    community_detected: str,
    homeowner_count: int,
    document_count: int,
    has_ai_answer: bool,
    ai_answer_text: str,
    ai_answer_source: str,
    response_time_ms: int
):
    """Log search event to Supabase asynchronously."""
    supabase = get_supabase()
    if not supabase:
        logger.warning("Supabase not configured, skipping analytics")
        return

    try:
        # Use the database function for atomic upsert
        supabase.rpc('log_search_event', {
            'p_user_email': user_email,
            'p_user_name': user_name,
            'p_session_id': session.get('session_id', str(uuid.uuid4())),
            'p_query_raw': query_raw,
            'p_query_type': query_type,
            'p_detected_type': detected_type,
            'p_community_filter': community_filter,
            'p_community_detected': community_detected,
            'p_homeowner_count': homeowner_count,
            'p_document_count': document_count,
            'p_has_ai_answer': has_ai_answer,
            'p_ai_answer_text': ai_answer_text,
            'p_ai_answer_source': ai_answer_source,
            'p_response_time_ms': response_time_ms
        }).execute()
    except Exception as e:
        logger.error(f"Failed to log search analytics: {e}")
```

---

## 3. Success Metrics (KPIs)

### Primary KPIs

| Metric | Definition | Target | Current Baseline |
|--------|------------|--------|------------------|
| **Search Success Rate** | (found + partial) / total | >80% | ~16% (from test doc) |
| **AI Answer Rate** | has_ai_answer / document_searches | >60% | Unknown |
| **Avg Response Time** | Mean response_time_ms | <500ms | Unknown |
| **Zero Result Rate** | not_found / total | <10% | ~84% (from test doc) |

### Secondary KPIs

| Metric | Definition | Purpose |
|--------|------------|---------|
| **User Adoption** | unique_users per week | Measure tool usage |
| **Repeat Searches** | Same query >1x per session | Indicates poor results |
| **Click-Through Rate** | results clicked / results shown | Result relevance |
| **Feedback Score** | Average user_rating | Direct satisfaction |
| **P95 Response Time** | 95th percentile latency | Performance tail |

### KPI Formulas (SQL)

```sql
-- Primary KPIs for a date range
SELECT
    -- Success Rate
    ROUND(100.0 * SUM(CASE WHEN is_success THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate,

    -- AI Answer Rate (for document searches only)
    ROUND(100.0 * SUM(CASE WHEN has_ai_answer THEN 1 ELSE 0 END) /
          NULLIF(SUM(CASE WHEN detected_type = 'document' THEN 1 ELSE 0 END), 0), 2) as ai_answer_rate,

    -- Avg Response Time
    ROUND(AVG(response_time_ms), 0) as avg_response_ms,

    -- Zero Result Rate
    ROUND(100.0 * SUM(CASE WHEN result_status = 'not_found' THEN 1 ELSE 0 END) / COUNT(*), 2) as zero_result_rate,

    -- Unique Users
    COUNT(DISTINCT user_email) as unique_users,

    -- P95 Response Time
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) as p95_response_ms

FROM mw_search_events
WHERE searched_at BETWEEN '2026-01-01' AND '2026-01-31';
```

---

## 4. Dashboard Design (Command Center Integration)

### Widget Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    MANAGER WIZARD SEARCH ANALYTICS                        │
├──────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │ Success Rate │  │ AI Answers  │  │ Avg Response│  │ Zero Results│      │
│  │    16.2%    │  │    42.5%    │  │   312ms     │  │   38.5%     │      │
│  │  ▼ -2.1%    │  │  ▲ +5.3%    │  │  ▲ -45ms    │  │  ▼ -3.2%    │      │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘      │
├──────────────────────────────────────────────────────────────────────────┤
│  Search Volume (7 days)              │  Top Failed Queries               │
│  ┌───────────────────────────────┐   │  ┌────────────────────────────┐   │
│  │  ▄▄  ▄▄                       │   │  │ 1. pet policy vista vera   │   │
│  │ ▄██▄▄██▄ ▄▄ ▄▄▄▄▄▄▄          │   │  │    12 failures · 4 users   │   │
│  │▄████████▄██▄██████████        │   │  │ 2. rental restrictions     │   │
│  │Mon Tue Wed Thu Fri Sat Sun    │   │  │    8 failures · 3 users    │   │
│  └───────────────────────────────┘   │  │ 3. pool hours falcon       │   │
│                                      │  │    6 failures · 2 users    │   │
│                                      │  └────────────────────────────┘   │
├──────────────────────────────────────────────────────────────────────────┤
│  Top Searches Today                  │  Top Communities                  │
│  ┌────────────────────────────────┐  │  ┌────────────────────────────┐   │
│  │ 1. falcon pointe pool ━━━━ 23 │  │  │ Falcon Pointe ━━━━━━━━ 45  │   │
│  │ 2. avalon fence ━━━━━━━━━ 18  │  │  │ Chandler Creek ━━━━━━ 32   │   │
│  │ 3. heritage park rules ━━ 15  │  │  │ Vista Vera ━━━━━━━━━━ 28   │   │
│  │ 4. wildhorse ranch ━━━━━━ 12  │  │  │ Heritage Park ━━━━━━━ 21   │   │
│  │ 5. smith account ━━━━━━━━  9  │  │  │ Highpointe ━━━━━━━━━━ 18   │   │
│  └────────────────────────────────┘  │  └────────────────────────────┘   │
├──────────────────────────────────────────────────────────────────────────┤
│  Improvement Recommendations (3 Critical)                    [View All]   │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ 🔴 CRITICAL: Create Pet Policy for Vista Vera                     │  │
│  │    12 failed searches from 4 users in past 7 days                  │  │
│  │    [Create Doc] [Dismiss]                                          │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ 🟠 HIGH: Add Rental Restrictions standalone for Highpointe         │  │
│  │    8 failed searches, currently buried in CC&Rs                    │  │
│  │    [Create Doc] [Dismiss]                                          │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

### Color Scheme

```css
:root {
  --analytics-primary: #6366f1;     /* Indigo - main accent */
  --analytics-success: #10b981;     /* Green - good metrics */
  --analytics-warning: #f59e0b;     /* Amber - warnings */
  --analytics-danger: #ef4444;      /* Red - critical */
  --analytics-neutral: #64748b;     /* Slate - neutral */
  --analytics-bg: #f8fafc;          /* Light background */
  --analytics-card: #ffffff;        /* Card background */
}
```

### Chart Types

| Metric | Chart Type | Library |
|--------|------------|---------|
| Volume over time | Area chart | Recharts |
| Success rate trend | Line chart | Recharts |
| Search type breakdown | Donut chart | Recharts |
| Top queries | Horizontal bar | Recharts |
| Community distribution | Treemap | Recharts |
| Response time histogram | Histogram | Recharts |

---

## 5. Popular Searches Report

### API Endpoint

```
GET /api/analytics/popular-searches
```

**Query Parameters:**
- `period`: `today`, `week`, `month` (default: `week`)
- `limit`: 10-100 (default: 25)
- `community`: Filter by community (optional)
- `type`: `homeowner`, `document`, `all` (default: `all`)

**Response:**

```json
{
  "period": "week",
  "start_date": "2026-01-21",
  "end_date": "2026-01-28",
  "searches": [
    {
      "rank": 1,
      "query": "falcon pointe pool rules",
      "count": 47,
      "unique_users": 8,
      "success_rate": 85.1,
      "avg_response_ms": 312,
      "has_ai_answer_rate": 72.3,
      "detected_type": "document",
      "community": "Falcon Pointe",
      "trend": "up",           // up, down, stable
      "trend_delta": 12        // % change from prior period
    },
    // ... more results
  ],
  "summary": {
    "total_unique_queries": 234,
    "total_searches": 1456,
    "avg_success_rate": 62.3
  }
}
```

### SQL Query

```sql
SELECT
    query_normalized as query,
    COUNT(*) as count,
    COUNT(DISTINCT user_email) as unique_users,
    ROUND(100.0 * SUM(CASE WHEN is_success THEN 1 ELSE 0 END) / COUNT(*), 1) as success_rate,
    ROUND(AVG(response_time_ms), 0) as avg_response_ms,
    ROUND(100.0 * SUM(CASE WHEN has_ai_answer THEN 1 ELSE 0 END) /
          NULLIF(SUM(CASE WHEN detected_type = 'document' THEN 1 ELSE 0 END), 0), 1) as ai_answer_rate,
    MODE() WITHIN GROUP (ORDER BY detected_type) as detected_type,
    MODE() WITHIN GROUP (ORDER BY community_detected) as community
FROM mw_search_events
WHERE searched_at > NOW() - INTERVAL '7 days'
GROUP BY query_normalized
ORDER BY count DESC
LIMIT 25;
```

---

## 6. Failed Searches Report

### API Endpoint

```
GET /api/analytics/failed-searches
```

**Query Parameters:**
- `period`: `today`, `week`, `month` (default: `week`)
- `limit`: 10-100 (default: 25)
- `status`: `new`, `acknowledged`, `in_progress`, `resolved`, `all` (default: `new`)
- `priority`: `critical`, `high`, `medium`, `low`, `all` (default: `all`)

**Response:**

```json
{
  "period": "week",
  "failed_searches": [
    {
      "id": "uuid-here",
      "query": "pet policy vista vera",
      "examples": [
        "pet policy vista vera",
        "Vista Vera pet rules",
        "VV pets allowed"
      ],
      "failure_type": "no_documents",
      "community": "Vista Vera",
      "failure_count": 12,
      "unique_users": 4,
      "first_failed": "2026-01-22T10:15:00Z",
      "last_failed": "2026-01-28T14:30:00Z",
      "calculated_priority": "critical",
      "status": "new",
      "suggested_action": "Create standalone pet policy document for Vista Vera. CC&Rs Section 5.3 contains pet rules but extraction fails."
    },
    // ... more results
  ],
  "summary": {
    "total_failed_patterns": 45,
    "critical_count": 3,
    "high_count": 8,
    "medium_count": 15,
    "low_count": 19,
    "total_impact_searches": 156
  }
}
```

### Priority Calculation

```sql
CASE
    WHEN failure_count >= 10 AND unique_users >= 3 THEN 'critical'
    WHEN failure_count >= 5 AND unique_users >= 2 THEN 'high'
    WHEN failure_count >= 3 THEN 'medium'
    ELSE 'low'
END as calculated_priority
```

### Workflow Integration

1. **Auto-create recommendations** when failure_count hits thresholds
2. **Email alerts** to admin for critical failures
3. **Kanban board** in dashboard for tracking resolution status
4. **Link to SharePoint** for document creation

---

## 7. Improvement Recommendations Engine

### Recommendation Types

| Type | Trigger | Suggested Action |
|------|---------|------------------|
| `create_doc` | No doc exists for common query | Create standalone document |
| `update_doc` | Doc exists but extraction fails | Add clearer headings/structure |
| `add_alias` | Community name not recognized | Add alias to `COMMUNITY_ALIASES` |
| `improve_prompt` | AI extraction quality low | Refine Claude prompt |
| `expand_keywords` | Detection type wrong | Add keywords to `EXTRACTION_KEYWORDS` |

### Auto-Generation Algorithm

```python
def generate_recommendations():
    """Generate improvement recommendations from failed searches."""

    # Get high-impact failed searches (not already in recommendations)
    failed = supabase.rpc('get_high_impact_failures').execute()

    for failure in failed.data:
        # Skip if recommendation already exists
        existing = supabase.table('mw_improvement_recommendations') \
            .select('id') \
            .eq('title', f"Address: {failure['query_normalized']}") \
            .execute()

        if existing.data:
            continue

        # Determine recommendation type
        rec_type = 'create_doc'  # Default
        if failure['failure_type'] == 'ai_extraction_failed':
            rec_type = 'improve_prompt'
        elif failure['community_filter'] and not community_exists(failure['community_filter']):
            rec_type = 'add_alias'

        # Calculate priority
        priority = 'low'
        if failure['failure_count'] >= 10 and failure['unique_users'] >= 3:
            priority = 'critical'
        elif failure['failure_count'] >= 5:
            priority = 'high'
        elif failure['failure_count'] >= 3:
            priority = 'medium'

        # Generate action items
        suggested_action = generate_action_text(rec_type, failure)

        # Insert recommendation
        supabase.table('mw_improvement_recommendations').insert({
            'recommendation_type': rec_type,
            'priority': priority,
            'title': f"Address: {failure['query_normalized']}",
            'description': f"Users are searching for '{failure['query_normalized']}' but finding no results.",
            'affected_queries': [failure['query_normalized']],
            'estimated_searches_impacted': failure['failure_count'],
            'evidence_query_samples': failure['query_examples'],
            'evidence_communities': [failure['community_filter']] if failure['community_filter'] else [],
            'suggested_action': suggested_action
        }).execute()

def generate_action_text(rec_type, failure):
    """Generate specific action instructions."""

    if rec_type == 'create_doc':
        return f"""Create a standalone document for "{failure['query_normalized']}" queries.

Recommended Steps:
1. Check if this info exists in the CC&Rs (likely Section 5-7)
2. Extract relevant section into standalone PDF
3. Name it clearly: "{failure['community_filter'] or 'Community'} - {failure['query_normalized'].title()}.pdf"
4. Upload to SharePoint > Association Docs > {failure['community_filter'] or '[Community]'} > Public folder
5. Wait for indexer to pick up (runs hourly)

Expected Impact: ~{failure['failure_count']} searches/week will find answers."""

    elif rec_type == 'add_alias':
        return f"""Add community alias to app.py COMMUNITY_ALIASES dictionary.

Add this line:
    '{failure['community_filter'].lower()}': '{find_closest_community(failure['community_filter'])}',

Redeploy after change."""

    elif rec_type == 'improve_prompt':
        return f"""The AI extraction is failing for "{failure['query_normalized']}" queries.

Possible issues:
1. Document structure not conducive to extraction
2. Keywords not in EXTRACTION_KEYWORDS
3. Content too far into document (>2000 chars)

Try:
1. Add more keywords to EXTRACTION_KEYWORDS['{detect_type(failure['query_normalized'])}']
2. Increase content truncation limit
3. Create dedicated document if content is buried"""

    return "Review failed search pattern and determine appropriate action."
```

### Weekly Digest Email

```python
def send_weekly_recommendations_digest():
    """Send weekly email with top recommendations."""

    # Get critical/high priority recommendations
    recs = supabase.table('mw_improvement_recommendations') \
        .select('*') \
        .in_('priority', ['critical', 'high']) \
        .eq('status', 'new') \
        .order('estimated_searches_impacted', desc=True) \
        .limit(10) \
        .execute()

    if not recs.data:
        return

    # Get weekly stats
    stats = supabase.table('mw_daily_stats') \
        .select('*') \
        .gte('stat_date', (datetime.now() - timedelta(days=7)).date()) \
        .execute()

    # Calculate totals
    total_searches = sum(s['total_searches'] for s in stats.data)
    avg_success = statistics.mean(s['success_rate'] for s in stats.data if s['success_rate'])

    # Build email
    html = f"""
    <h2>Manager Wizard - Weekly Analytics Digest</h2>

    <h3>This Week's Performance</h3>
    <ul>
        <li>Total Searches: {total_searches:,}</li>
        <li>Success Rate: {avg_success:.1f}%</li>
        <li>Improvement Opportunities: {len(recs.data)}</li>
    </ul>

    <h3>Top Recommendations</h3>
    <table border="1" cellpadding="8">
        <tr><th>Priority</th><th>Issue</th><th>Impact</th><th>Action</th></tr>
    """

    for rec in recs.data:
        html += f"""
        <tr>
            <td>{rec['priority'].upper()}</td>
            <td>{rec['title']}</td>
            <td>~{rec['estimated_searches_impacted']} searches/week</td>
            <td>{rec['recommendation_type']}</td>
        </tr>
        """

    html += "</table>"

    # Send via MS Graph
    send_email(
        to=['rickyz@psprop.net'],
        subject=f"Manager Wizard Analytics - Week of {datetime.now().strftime('%b %d')}",
        body=html
    )
```

---

## 8. API Endpoints Summary

### Analytics Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analytics/summary` | GET | Dashboard summary (KPIs) |
| `/api/analytics/popular-searches` | GET | Top queries by volume |
| `/api/analytics/failed-searches` | GET | Queries with zero results |
| `/api/analytics/recommendations` | GET | Improvement recommendations |
| `/api/analytics/recommendations/{id}/status` | PATCH | Update recommendation status |
| `/api/analytics/daily-stats` | GET | Daily aggregated stats |
| `/api/analytics/user-activity` | GET | Per-user search stats |
| `/api/analytics/community-patterns` | GET | Per-community analytics |

### Internal Endpoints (for logging)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analytics/log-search` | POST | Log a search event (internal) |
| `/api/analytics/log-click` | POST | Log result click (internal) |
| `/api/analytics/log-feedback` | POST | Log user rating (internal) |

---

## 9. Implementation Phases

### Phase 1: Core Logging (Week 1)
- [ ] Create Supabase tables
- [ ] Add `supabase-py` to requirements.txt
- [ ] Implement `log_search_analytics()` function
- [ ] Integrate logging into `/api/unified-search`
- [ ] Integrate logging into `/api/search`
- [ ] Integrate logging into `/api/documents/search`
- [ ] Deploy to Cloud Run

### Phase 2: Dashboard (Week 2)
- [ ] Create `searchAnalyticsWidget.js` for Command Center
- [ ] Add `/api/analytics/summary` endpoint
- [ ] Add `/api/analytics/popular-searches` endpoint
- [ ] Add `/api/analytics/failed-searches` endpoint
- [ ] Create basic dashboard CSS

### Phase 3: Recommendations (Week 3)
- [ ] Implement recommendation generation algorithm
- [ ] Add `/api/analytics/recommendations` endpoints
- [ ] Create recommendation management UI
- [ ] Set up weekly digest email

### Phase 4: Advanced Analytics (Week 4)
- [ ] Click tracking for results
- [ ] User feedback system
- [ ] Community-level analytics
- [ ] Performance monitoring alerts

---

## 10. Environment Variables Needed

```bash
# Add to Cloud Run environment
SUPABASE_URL=https://hthaomwoizcyfeduptqm.supabase.co
SUPABASE_SERVICE_KEY=<service-role-key>
```

---

## Appendix: Sample Dashboard Data

### Mock Daily Stats Response

```json
{
  "date": "2026-01-28",
  "total_searches": 234,
  "unique_users": 18,
  "success_rate": 62.4,
  "ai_answer_rate": 48.2,
  "avg_response_time_ms": 312,
  "search_breakdown": {
    "homeowner": 98,
    "document": 112,
    "unified": 24
  },
  "result_breakdown": {
    "found": 98,
    "partial": 48,
    "not_found": 82,
    "error": 6
  },
  "top_queries": [
    {"query": "falcon pointe pool", "count": 12, "success_rate": 83.3},
    {"query": "avalon fence rules", "count": 9, "success_rate": 100},
    {"query": "heritage park ccr", "count": 7, "success_rate": 71.4}
  ],
  "top_communities": [
    {"name": "Falcon Pointe", "count": 45},
    {"name": "Chandler Creek", "count": 32},
    {"name": "Vista Vera", "count": 28}
  ]
}
```

---

*Design Document Complete - Ready for Implementation Review*
