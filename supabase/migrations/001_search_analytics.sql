-- Manager Wizard Search Analytics Schema
-- Supabase Project: hthaomwoizcyfeduptqm
-- Run in Supabase SQL Editor
-- Created: 2026-01-28

-- ============================================
-- SEARCH EVENTS (main analytics table)
-- ============================================
CREATE TABLE IF NOT EXISTS mw_search_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    -- Timing
    searched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    response_time_ms INTEGER,

    -- User Context
    user_email TEXT,
    user_name TEXT,
    session_id TEXT,

    -- Query Details
    query_raw TEXT NOT NULL,
    query_normalized TEXT,
    query_type TEXT,
    detected_type TEXT,

    -- Community Context
    community_filter TEXT,
    community_detected TEXT,
    community_normalized TEXT,

    -- Search Parameters
    search_mode TEXT,
    include_ai_answer BOOLEAN DEFAULT true,

    -- Results Summary
    homeowner_count INTEGER DEFAULT 0,
    document_count INTEGER DEFAULT 0,
    has_ai_answer BOOLEAN DEFAULT false,

    -- AI Answer Details
    ai_answer_text TEXT,
    ai_answer_source TEXT,
    ai_answer_confidence TEXT,
    ai_extraction_type TEXT,

    -- Success Metrics
    result_status TEXT,
    is_success BOOLEAN GENERATED ALWAYS AS (
        result_status IN ('found', 'partial')
    ) STORED,

    -- Error Details
    error_type TEXT,
    error_message TEXT,

    -- User Feedback (populated via feedback API)
    user_rating INTEGER CHECK (user_rating >= 1 AND user_rating <= 5),
    user_feedback TEXT,
    feedback_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_mw_search_events_searched_at ON mw_search_events(searched_at DESC);
CREATE INDEX IF NOT EXISTS idx_mw_search_events_user ON mw_search_events(user_email);
CREATE INDEX IF NOT EXISTS idx_mw_search_events_query ON mw_search_events(query_normalized);
CREATE INDEX IF NOT EXISTS idx_mw_search_events_community ON mw_search_events(community_detected);
CREATE INDEX IF NOT EXISTS idx_mw_search_events_result ON mw_search_events(result_status);
CREATE INDEX IF NOT EXISTS idx_mw_search_events_type ON mw_search_events(detected_type);
CREATE INDEX IF NOT EXISTS idx_mw_search_events_success ON mw_search_events(is_success);

COMMENT ON TABLE mw_search_events IS 'Every search performed in Manager Wizard with full context and results';

-- ============================================
-- SEARCH RESULTS DETAIL (for click tracking)
-- ============================================
CREATE TABLE IF NOT EXISTS mw_search_results (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    search_event_id UUID NOT NULL REFERENCES mw_search_events(id) ON DELETE CASCADE,

    result_type TEXT NOT NULL,
    result_position INTEGER,

    -- Homeowner result details
    homeowner_name TEXT,
    homeowner_account TEXT,
    homeowner_community TEXT,
    homeowner_address TEXT,

    -- Document result details
    document_title TEXT,
    document_path TEXT,
    document_community TEXT,
    document_type TEXT,
    document_score NUMERIC(10,4),

    -- User interaction
    was_clicked BOOLEAN DEFAULT false,
    clicked_at TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mw_search_results_event ON mw_search_results(search_event_id);
CREATE INDEX IF NOT EXISTS idx_mw_search_results_clicked ON mw_search_results(was_clicked) WHERE was_clicked = true;

COMMENT ON TABLE mw_search_results IS 'Individual results returned for each search, with click tracking';

-- ============================================
-- POPULAR SEARCHES (pre-aggregated hourly)
-- ============================================
CREATE TABLE IF NOT EXISTS mw_popular_searches (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    hour_bucket TIMESTAMP WITH TIME ZONE NOT NULL,

    query_normalized TEXT NOT NULL,
    detected_type TEXT,
    community_detected TEXT,

    search_count INTEGER DEFAULT 1,
    success_count INTEGER DEFAULT 0,
    avg_response_time_ms NUMERIC(10,2),

    unique_users INTEGER DEFAULT 1,
    user_emails TEXT[],

    avg_homeowner_results NUMERIC(10,2),
    avg_document_results NUMERIC(10,2),
    ai_answer_rate NUMERIC(5,2),

    UNIQUE(hour_bucket, query_normalized, community_detected)
);

CREATE INDEX IF NOT EXISTS idx_mw_popular_hour ON mw_popular_searches(hour_bucket DESC);
CREATE INDEX IF NOT EXISTS idx_mw_popular_query ON mw_popular_searches(query_normalized);
CREATE INDEX IF NOT EXISTS idx_mw_popular_count ON mw_popular_searches(search_count DESC);

COMMENT ON TABLE mw_popular_searches IS 'Hourly aggregation of popular search queries';

-- ============================================
-- FAILED SEARCHES (for KB improvement)
-- ============================================
CREATE TABLE IF NOT EXISTS mw_failed_searches (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    query_normalized TEXT NOT NULL,
    query_examples TEXT[],

    failure_type TEXT,
    community_filter TEXT,
    detected_type TEXT,

    failure_count INTEGER DEFAULT 1,
    first_failed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_failed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    unique_users INTEGER DEFAULT 1,
    user_emails TEXT[],

    -- Improvement tracking
    status TEXT DEFAULT 'new',
    assigned_to TEXT,
    resolution_notes TEXT,
    resolved_at TIMESTAMP WITH TIME ZONE,

    -- Link to KB improvements
    kb_doc_created TEXT,
    kb_doc_created_at TIMESTAMP WITH TIME ZONE,

    UNIQUE(query_normalized, community_filter, failure_type)
);

CREATE INDEX IF NOT EXISTS idx_mw_failed_count ON mw_failed_searches(failure_count DESC);
CREATE INDEX IF NOT EXISTS idx_mw_failed_status ON mw_failed_searches(status);
CREATE INDEX IF NOT EXISTS idx_mw_failed_recent ON mw_failed_searches(last_failed_at DESC);

COMMENT ON TABLE mw_failed_searches IS 'Aggregated failed search patterns for knowledge base improvement';

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
    success_rate NUMERIC(5,2),

    -- Type breakdown
    homeowner_searches INTEGER DEFAULT 0,
    document_searches INTEGER DEFAULT 0,
    unified_searches INTEGER DEFAULT 0,

    -- AI metrics
    ai_answer_count INTEGER DEFAULT 0,
    ai_answer_rate NUMERIC(5,2),
    avg_ai_confidence_score NUMERIC(5,2),

    -- Performance
    avg_response_time_ms NUMERIC(10,2),
    p95_response_time_ms INTEGER,
    slowest_query TEXT,
    slowest_time_ms INTEGER,

    -- Top patterns (JSONB for flexibility)
    top_queries JSONB,
    top_communities JSONB,
    top_failed_queries JSONB,
    top_users JSONB,
    peak_hour INTEGER,

    computed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mw_daily_stats_date ON mw_daily_stats(stat_date DESC);

COMMENT ON TABLE mw_daily_stats IS 'Pre-computed daily analytics for fast dashboard loading';

-- ============================================
-- IMPROVEMENT RECOMMENDATIONS
-- ============================================
CREATE TABLE IF NOT EXISTS mw_improvement_recommendations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    recommendation_type TEXT NOT NULL,
    priority TEXT DEFAULT 'medium',

    title TEXT NOT NULL,
    description TEXT,

    affected_queries TEXT[],
    estimated_searches_impacted INTEGER,
    estimated_success_improvement NUMERIC(5,2),

    evidence_query_samples TEXT[],
    evidence_communities TEXT[],

    suggested_action TEXT,
    document_template TEXT,

    -- Status tracking
    status TEXT DEFAULT 'new',
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

CREATE INDEX IF NOT EXISTS idx_mw_recommendations_status ON mw_improvement_recommendations(status);
CREATE INDEX IF NOT EXISTS idx_mw_recommendations_priority ON mw_improvement_recommendations(priority);
CREATE INDEX IF NOT EXISTS idx_mw_recommendations_type ON mw_improvement_recommendations(recommendation_type);

COMMENT ON TABLE mw_improvement_recommendations IS 'AI-generated recommendations for improving search coverage';

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================
ALTER TABLE mw_search_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE mw_search_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE mw_popular_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE mw_failed_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE mw_daily_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE mw_improvement_recommendations ENABLE ROW LEVEL SECURITY;

-- Service role has full access (for Python scripts)
CREATE POLICY "Service role full access on mw_search_events" ON mw_search_events FOR ALL USING (true);
CREATE POLICY "Service role full access on mw_search_results" ON mw_search_results FOR ALL USING (true);
CREATE POLICY "Service role full access on mw_popular_searches" ON mw_popular_searches FOR ALL USING (true);
CREATE POLICY "Service role full access on mw_failed_searches" ON mw_failed_searches FOR ALL USING (true);
CREATE POLICY "Service role full access on mw_daily_stats" ON mw_daily_stats FOR ALL USING (true);
CREATE POLICY "Service role full access on mw_improvement_recommendations" ON mw_improvement_recommendations FOR ALL USING (true);

-- ============================================
-- USEFUL VIEWS
-- ============================================

-- Real-time search success rate (last 24 hours)
CREATE OR REPLACE VIEW v_mw_search_success_rate_24h AS
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
CREATE OR REPLACE VIEW v_mw_actionable_failed_queries AS
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
CREATE OR REPLACE VIEW v_mw_community_search_patterns AS
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
CREATE OR REPLACE VIEW v_mw_user_activity AS
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

-- ============================================
-- FUNCTIONS
-- ============================================

-- Log a search event (atomic insert + failed search update)
CREATE OR REPLACE FUNCTION log_mw_search_event(
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
                WHEN p_user_email IS NOT NULL AND NOT p_user_email = ANY(COALESCE(mw_failed_searches.user_emails, ARRAY[]::TEXT[]))
                THEN mw_failed_searches.unique_users + 1
                ELSE mw_failed_searches.unique_users
            END,
            user_emails = CASE
                WHEN p_user_email IS NOT NULL
                    AND COALESCE(array_length(mw_failed_searches.user_emails, 1), 0) < 20
                    AND NOT p_user_email = ANY(COALESCE(mw_failed_searches.user_emails, ARRAY[]::TEXT[]))
                THEN array_append(COALESCE(mw_failed_searches.user_emails, ARRAY[]::TEXT[]), p_user_email)
                ELSE mw_failed_searches.user_emails
            END;
    END IF;

    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION log_mw_search_event IS 'Atomically log a search event and update failed search aggregates';

-- Compute daily stats (run via cron at midnight)
CREATE OR REPLACE FUNCTION compute_mw_daily_stats(p_date DATE)
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
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms)::INTEGER,
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

COMMENT ON FUNCTION compute_mw_daily_stats IS 'Compute daily aggregated stats for the dashboard';

-- Get high-impact failed searches for recommendation generation
CREATE OR REPLACE FUNCTION get_mw_high_impact_failures()
RETURNS TABLE (
    query_normalized TEXT,
    failure_type TEXT,
    community_filter TEXT,
    detected_type TEXT,
    failure_count INTEGER,
    unique_users INTEGER,
    query_examples TEXT[],
    calculated_priority TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        f.query_normalized,
        f.failure_type,
        f.community_filter,
        f.detected_type,
        f.failure_count,
        f.unique_users,
        f.query_examples,
        CASE
            WHEN f.failure_count >= 10 AND f.unique_users >= 3 THEN 'critical'
            WHEN f.failure_count >= 5 AND f.unique_users >= 2 THEN 'high'
            WHEN f.failure_count >= 3 THEN 'medium'
            ELSE 'low'
        END as calculated_priority
    FROM mw_failed_searches f
    WHERE f.status = 'new'
      AND f.failure_count >= 3
      AND f.last_failed_at > NOW() - INTERVAL '7 days'
    ORDER BY f.failure_count DESC, f.unique_users DESC
    LIMIT 50;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_mw_high_impact_failures IS 'Get failed searches that need attention based on count and user impact';

-- ============================================
-- DONE
-- ============================================

-- Verify tables created
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name LIKE 'mw_%'
ORDER BY table_name;
