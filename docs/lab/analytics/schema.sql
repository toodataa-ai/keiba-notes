-- Anonymous day × event aggregates for keiba-notes ONLY.
-- No user IDs, URLs, IP addresses, user agents, session identifiers or raw logs.
CREATE TABLE IF NOT EXISTS event_counts (
  day TEXT NOT NULL,
  event TEXT NOT NULL CHECK (event IN (
    'page_home','page_this_week','page_results','page_schedule',
    'page_methodology','page_research','page_other','session_start'
  )),
  count INTEGER NOT NULL DEFAULT 0 CHECK (count >= 0),
  PRIMARY KEY (day, event)
);
