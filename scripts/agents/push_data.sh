#!/bin/bash
# Pushes latest JSON reports to GitHub so the dashboard on GitHub Pages stays live
REPO="/Users/owner/Desktop/MBH--CRM-"
cd "$REPO" || exit 1

git add scripts/agents/reports/marketing_today.json \
        scripts/agents/reports/marketing_latest.json \
        scripts/agents/reports/marketing_weekly.json \
        scripts/agents/reports/hourly_snapshots.json \
        scripts/agents/reports/poster_status.json \
        scripts/agents/reports/live.json \
        scripts/agents/reports/research_latest.json \
        scripts/agents/reports/daily_history.json \
        scripts/agents/campaign_knowledge.json \
        scripts/agents/dashboard.html \
        2>/dev/null

if git diff --cached --quiet; then
  exit 0
fi

git commit -m "data: live update $(date '+%H:%M')" --no-verify 2>/dev/null
git push origin main --quiet 2>/dev/null
