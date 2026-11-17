import json
import logging
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

logger = logging.getLogger(__name__)

BOLOGNA_COURSES_URL = (
    "https://obs.acibadem.edu.tr/oibs/bologna/progCourses.aspx?curSunit=6246&lang=en"
)
SEED_DATA_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = SEED_DATA_DIR / "acibadem_courses.json"


class BolognaTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_td = False
        self.in_tr = False
        self.current_row = []
        self.rows = []
        self.cell_data = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.in_tr = True
            self.current_row = []
        elif tag == "td" and self.in_tr:
            self.in_td = True
            self.cell_data = []

    def handle_endtag(self, tag):
        if tag == "td" and self.in_td:
            self.in_td = False
            self.current_row.append(" ".join("".join(self.cell_data).split()))
        elif tag == "tr" and self.in_tr:
            self.in_tr = False
            if self.current_row:
                self.rows.append(self.current_row)

    def handle_data(self, data):
        if self.in_td:
            self.cell_data.append(data)


def crawl_acibadem_courses(output_path: Path | None = None) -> list[dict]:
    # Crawl course catalog for Computer Engineering from Acibadem University Bologna system
    target_path = output_path or OUTPUT_FILE
    logger.info("Fetching Acibadem courses from %s", BOLOGNA_COURSES_URL)

    req = urllib.request.Request(
        BOLOGNA_COURSES_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    parser = BolognaTableParser()
    parser.feed(html)

    courses = []
    for tds in parser.rows:
        if len(tds) >= 6 and tds[1] and re.match(r"^[A-Z]{2,4}\s*\d+", tds[1]):
            raw_code = tds[1].strip()
            code = raw_code.replace(" ", "")
            title = tds[2].strip()
            tal = tds[3].strip()
            ctype = tds[4].strip()
            ects_str = tds[5].strip()
            ects = int(ects_str) if ects_str.isdigit() else 3

            m = re.match(r"(\d+)\+(\d+)\+(\d+)", tal)
            if m:
                t, a, l = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if "internship" in title.lower() or "staj" in title.lower() or a > 20:
                    credits = 0
                else:
                    credits = t + (a // 2) + (l // 2)
                    if credits == 0:
                        credits = t
            else:
                credits = max(1, ects // 2)

            if credits == 0 and "internship" not in title.lower() and "staj" not in title.lower():
                credits = 1

            courses.append(
                {
                    "code": code,
                    "raw_code": raw_code,
                    "title": title,
                    "tal": tal,
                    "credits": credits,
                    "ects": ects,
                    "type": ctype,
                }
            )

    unique = {}
    for c in courses:
        if c["code"] not in unique:
            unique[c["code"]] = c
        else:
            if c["type"] == "Compulsory":
                unique[c["code"]] = c

    course_list = list(unique.values())
    course_list.sort(key=lambda x: x["code"])

    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(course_list, f, indent=2, ensure_ascii=False)

    logger.info("Successfully saved %d courses to %s", len(course_list), target_path)
    return course_list


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    crawl_acibadem_courses()
