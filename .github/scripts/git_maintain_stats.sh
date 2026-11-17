#!/usr/bin/env bash
set -euo pipefail

# 1. Configure Git maintenance
git config maintenance.repack.enabled true
git config maintenance.gc.enabled true
git config maintenance.commit-graph.enabled true
git config maintenance.prefetch.enabled true

# 2. Run standard maintenance
git maintenance run

# 3. Run repack with cruft objects using script to preserve terminal progress
LOG_FILE="/tmp/git_repack.log"
REPORT_FILE="/tmp/git_maintenance_report.md"

script -qec "git repack -a -d --cruft" "$LOG_FILE" > /dev/null

# 4. Parse log file into Markdown table
TABLE=$(tr '\r' '\n' < "$LOG_FILE" | awk '
BEGIN {
    print "| Operation | Value |"
    print "|:---|:---|"
    cruft_total = ""
}
/Enumerating objects: [0-9]+, done/ {
    match($0, /Enumerating objects: ([0-9]+)/, m)
    print "| Enumerating objects | " m[1] " |"
}
/Counting objects:.*done/ && !cruft {
    match($0, /Counting objects: ([^,]+)/, m)
    print "| Counting objects | " m[1] " |"
}
/Delta compression/ && !cruft {
    match($0, /([0-9]+) threads/, m)
    threads = (m[1] ? m[1] " threads" : "8 threads")
    print "| Delta compression | " threads " |"
}
/Compressing objects:.*done/ && !cruft {
    match($0, /Compressing objects: ([^,]+)/, m)
    print "| Compressing objects | " m[1] " |"
}
/Writing objects:.*done/ && !cruft {
    match($0, /Writing objects: ([^,]+)/, m)
    print "| Writing objects | " m[1] " |"
}
/^Total [0-9]+/ && /reused/ && !cruft {
    match($0, /Total ([0-9]+)/, m_tot)
    match($0, /reused ([^,]+)/, m_reu)
    match($0, /pack-reused ([^\n]+)/, m_pck)
    if (m_reu[1]) print "| Reused objects | " m_reu[1] " |"
    if (m_pck[1]) print "| pack-reused | " m_pck[1] " |"
    if (m_tot[1]) print "| Total objects | `" m_tot[1] "` |"
}
/Enumerating cruft objects:/ {
    cruft = 1
    match($0, /Enumerating cruft objects: ([0-9]+)/, m)
    print "| Enumerating cruft objects | " m[1] ", |"
}
/Traversing cruft objects:/ {
    match($0, /Traversing cruft objects: ([0-9]+)/, m)
    print "| Traversing cruft objects | " m[1] ", |"
}
/Counting objects:.*done/ && cruft {
    match($0, /Counting objects: ([^,]+)/, m)
    print "| Counting objects | " m[1] " |"
}
/Delta compression/ && cruft {
    match($0, /([0-9]+) threads/, m)
    threads = (m[1] ? "using up to " m[1] " threads" : "using up to 8 threads")
    print "| Delta compression | " threads " |"
}
/Compressing objects:.*done/ && cruft {
    match($0, /Compressing objects: ([^,]+)/, m)
    print "| Compressing objects | " m[1] " |"
}
/Writing objects:.*done/ && cruft {
    match($0, /Writing objects: ([^,]+)/, m)
    print "| Writing objects | " m[1] " |"
}
/^Total [0-9]+/ && /reused/ && cruft {
    cruft_total = $0
}
END {
    if (cruft_total != "") {
        print "\n" cruft_total
    }
}
')

# 5. Build full report
cat <<EOF > "$REPORT_FILE"
# 🛠️ Git Maintenance Statistics

**Notification**: cc @krr0ption

$TABLE
EOF

# 6. Publish to GITHUB_STEP_SUMMARY if available
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    cat "$REPORT_FILE" >> "$GITHUB_STEP_SUMMARY"
fi

cat "$REPORT_FILE"

# 7. Notify krr0ption via GitHub Issue
if [ -n "${GITHUB_TOKEN:-}" ] && command -v gh >/dev/null 2>&1; then
    EXISTING_ISSUE=$(gh issue list --search "Git Maintenance Statistics in:title" --json number --jq '.[0].number' 2>/dev/null || true)
    if [ -n "$EXISTING_ISSUE" ]; then
        gh issue comment "$EXISTING_ISSUE" --body-file "$REPORT_FILE" || true
        echo "Added maintenance report comment to issue #$EXISTING_ISSUE"
    else
        gh issue create --title "🛠️ Git Maintenance Statistics" --body-file "$REPORT_FILE" --assignee "krr0ption" || true
        echo "Created Git Maintenance Statistics issue assigned to krr0ption"
    fi
fi
