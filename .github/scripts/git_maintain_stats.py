#!/usr/bin/env python3
import os
import pty
import re
import subprocess
import sys


def run_cmd(cmd):
    """Run a shell command silently or return output."""
    res = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True)
    return res.stdout.strip()


def run_repack_with_pty():
    """Run git repack with a pty to capture interactive progress messages."""
    master, slave = pty.openpty()
    proc = subprocess.Popen(
        ["git", "repack", "-a", "-d", "--cruft"],
        stdout=slave,
        stderr=slave,
        close_fds=True,
    )
    os.close(slave)
    output = b""
    while True:
        try:
            data = os.read(master, 1024)
            if not data:
                break
            output += data
        except OSError:
            break
    os.close(master)
    proc.wait()
    return output.decode("utf-8", errors="replace")


def parse_repack_output(text):
    """Parse git repack output lines into the requested markdown table."""
    lines = [l.strip() for l in text.replace("\r", "\n").split("\n") if l.strip()]

    main_lines = []
    cruft_lines = []
    in_cruft = False

    for l in lines:
        if "cruft" in l.lower():
            in_cruft = True
        if in_cruft:
            cruft_lines.append(l)
        else:
            main_lines.append(l)

    table_rows = []

    # Process main pack
    for l in main_lines:
        if "Enumerating objects:" in l and "done" in l:
            m = re.search(r"Enumerating objects:\s*(\d+)", l)
            if m:
                table_rows.append(f"|[x]| Enumerating objects| {m.group(1)}|")
        elif "Counting objects:" in l and "done" in l:
            m = re.search(r"Counting objects:\s*([^\,]+)", l)
            if m:
                table_rows.append(f"|[x]| Counting objects| {m.group(1)}|")
        elif "Delta compression" in l:
            m = re.search(r"(\d+)\s*threads", l)
            threads = f"{m.group(1)} threads" if m else "8 threads"
            table_rows.append(f"|[x]| Delta compression | {threads} |")
        elif "Compressing objects:" in l and "done" in l:
            m = re.search(r"Compressing objects:\s*([^\,]+)", l)
            if m:
                table_rows.append(f"|[x]| Compressing objects| {m.group(1)}|")
        elif "Writing objects:" in l and "done" in l:
            m = re.search(r"Writing objects:\s*([^\,]+)", l)
            if m:
                table_rows.append(f"|[x]| Writing objects| {m.group(1)}|")
        elif l.startswith("Total ") and "reused" in l:
            m_tot = re.search(r"Total\s+(\d+)", l)
            m_reused = re.search(r"reused\s+([^,]+)", l)
            m_pack = re.search(r"pack-reused\s+([^\n]+)", l)
            if m_reused:
                table_rows.append(f"| | Reused objects| {m_reused.group(1)}|")
            if m_pack:
                table_rows.append(f"| | pack-reused| {m_pack.group(1)}|")
            if m_tot:
                table_rows.append(f"| | Total objects| `{m_tot.group(1)}`|")

    # Process cruft pack
    cruft_total_summary = ""
    for l in cruft_lines:
        if "Enumerating cruft objects:" in l:
            m = re.search(r"Enumerating cruft objects:\s*(\d+)", l)
            if m:
                table_rows.append(f"|[x]| Enumerating cruft objects| {m.group(1)},|")
        elif "Traversing cruft objects:" in l:
            m = re.search(r"Traversing cruft objects:\s*(\d+)", l)
            if m:
                table_rows.append(f"|[x]| Traversing cruft objects| {m.group(1)},|")
        elif "Counting objects:" in l and "done" in l:
            m = re.search(r"Counting objects:\s*([^\,]+)", l)
            if m:
                table_rows.append(f"|[x]| Counting objects| {m.group(1)}|")
        elif "Delta compression" in l:
            table_rows.append(f"|[x]| Delta compression using up to 8 threads| |")
        elif "Compressing objects:" in l and "done" in l:
            m = re.search(r"Compressing objects:\s*([^\,]+)", l)
            if m:
                table_rows.append(f"|[x]| Compressing objects| {m.group(1)}|")
        elif "Writing objects:" in l and "done" in l:
            m = re.search(r"Writing objects:\s*([^\,]+)", l)
            if m:
                table_rows.append(f"|[x]| Writing objects| {m.group(1)}|")
        elif l.startswith("Total ") and "reused" in l:
            cruft_total_summary = l

    # If any fields were missed due to empty delta/cruft, provide sensible fallbacks
    if not table_rows:
        count_obj = run_cmd(["git", "count-objects", "-v"])
        table_rows.append(f"| [x] | Git count-objects | {count_obj} |")

    header = [
        "| Status | Operation | Value |",
        "|:---:|:---|:---|",
    ]

    report_content = "\n".join(header + table_rows)
    if cruft_total_summary:
        report_content += "\n\n" + cruft_total_summary

    return report_content


def notify_github(report_md):
    """Notify krr0ption via GitHub issue or step summary."""
    full_message = f"""# 🛠️ Git Maintenance Statistics

**Notification**: cc @krr0ption

{report_md}
"""
    # 1. Write to GITHUB_STEP_SUMMARY if running in GitHub Actions
    step_summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary_path and os.path.exists(os.path.dirname(step_summary_path)):
        with open(step_summary_path, "a", encoding="utf-8") as f:
            f.write(full_message + "\n")

    # 2. Write to local report file
    report_file = "git_maintenance_report.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(full_message)

    print(full_message)

    # 3. Create or comment on an issue to notify @krr0ption
    token = os.getenv("GITHUB_TOKEN")
    if token:
        try:
            # Check if an existing maintenance issue exists
            find_issue_cmd = [
                "gh",
                "issue",
                "list",
                "--search",
                "Git Maintenance Statistics in:title",
                "--json",
                "number",
                "--jq",
                ".[0].number",
            ]
            existing_issue = run_cmd(find_issue_cmd)
            if existing_issue and existing_issue.isdigit():
                subprocess.run(
                    [
                        "gh",
                        "issue",
                        "comment",
                        existing_issue,
                        "--body-file",
                        report_file,
                    ],
                    check=False,
                )
                print(f"Added maintenance report comment to issue #{existing_issue}")
            else:
                subprocess.run(
                    [
                        "gh",
                        "issue",
                        "create",
                        "--title",
                        "🛠️ Git Maintenance Statistics",
                        "--body-file",
                        report_file,
                        "--assignee",
                        "krr0ption",
                    ],
                    check=False,
                )
                print("Created new Git Maintenance Statistics issue assigned to krr0ption")
        except Exception as e:
            print(f"Warning: Issue notification could not be dispatched: {e}")


def main():
    # 1. Run git maintenance configuration and tasks
    run_cmd(["git", "config", "maintenance.repack.enabled", "true"])
    run_cmd(["git", "config", "maintenance.gc.enabled", "true"])
    run_cmd(["git", "config", "maintenance.commit-graph.enabled", "true"])
    run_cmd(["git", "config", "maintenance.prefetch.enabled", "true"])

    print("Running git maintenance...")
    run_cmd(["git", "maintenance", "run"])

    print("Running git repack --cruft...")
    repack_output = run_repack_with_pty()

    print("Parsing maintenance statistics...")
    report_table = parse_repack_output(repack_output)

    print("Publishing notification...")
    notify_github(report_table)


if __name__ == "__main__":
    main()
