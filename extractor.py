"""
extractor.py
============
Core extraction logic for Bridge to Success — No-Login.
All original functions from `bridgetosuccess_nologin_extractor.py`
are preserved here unchanged (just without the CLI/coloring code),
so both the Flask API (main.py) and the Telegram bot (bot.py) can
share the exact same logic.

How this works (confirmed from APK reverse engineering):
  - Every request adds two headers from AppManager.getT():
      ktx  = "com.lct.bmightc"   (app package name)
      ktxx = "12.0"               (app version key)
  - AppManager.getUserId() returns "" (empty string) when not logged in
  - allCourses / topCourses / getCategory all accept userId=""
  - The server trusts the ktx/ktxx headers to identify the app
"""

import io
import re
import time
import logging

import requests

log = logging.getLogger("bridgetosuccess")

# ─── Constants ────────────────────────────────────────────────────────────────
API_BASE    = "https://bridgetosuccess.learncentre.tech/public/study_api_sprint13_security_promo/"
COURSE_HOST = "https://bridgetosuccess.learncentre.tech/public/storage/course/"
VIDEO_HOST  = "https://bridgetosuccess.learncentre.tech/public/storage/video/"
PDF_HOST    = "https://bridgetosuccess.learncentre.tech/public/storage/pdf/"

# Injected on every request by AppManager.getT() — confirmed from smali
APP_HEADERS = {
    "ktx":  "com.lct.bmightc",   # package name
    "ktxx": "12.0",               # version key
}

HEADERS = {
    "User-Agent":   "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
    "Accept":       "application/json, text/plain, */*",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer":      "https://bridgetosuccess.learncentre.tech/",
    "Origin":       "https://bridgetosuccess.learncentre.tech",
    **APP_HEADERS,
}


# ─── Core API Call ────────────────────────────────────────────────────────────
def post(tag: str, extra: dict = None) -> dict | None:
    """POST to the API. userId="" works for all public endpoints."""
    extra = extra or {}
    payload = {"tag": tag, "userId": "", **extra}
    try:
        r = requests.post(API_BASE, data=payload, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        log.error("Timeout on tag=%s", tag)
    except requests.exceptions.HTTPError as e:
        log.error("HTTP %s on tag=%s", e.response.status_code, tag)
    except Exception as e:
        log.error("Error on tag=%s: %s", tag, e)
    return None


def safe_list(data, *keys) -> list:
    """Extract a list from nested dict keys, trying each key."""
    if not data:
        return []
    for k in keys:
        val = data.get(k)
        if isinstance(val, list) and val:
            return val
    return []


def sanitize(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    return re.sub(r'[\s_]+', '_', name).strip('_. ') or "Unknown"


# ─── Fetch Functions ──────────────────────────────────────────────────────────
def fetch_all_courses() -> list:
    """tag: allCourses | userId: "" | isEBook: 0"""
    log.info("Fetching all courses...")
    data = post("allCourses", {"isEBook": "0"})
    return safe_list(data, "data", "courses", "course")


def fetch_top_courses() -> list:
    """tag: topCourses | userId: "" | isEBook: 0"""
    log.info("Fetching top/featured courses...")
    data = post("topCourses", {"isEBook": "0"})
    return safe_list(data, "data", "courses", "course")


def fetch_course_info(course_id: str) -> dict:
    """tag: courseInfo | courseId, userId: ""  — description, faculty, etc."""
    data = post("courseInfo", {"courseId": course_id})
    if data:
        return data.get("data") or {}
    return {}


def fetch_subjects(course_id: str) -> list:
    """tag: getCategory | courseId, categoryId: ""  — subject list"""
    data = post("getCategory", {"courseId": course_id, "categoryId": ""})
    result = safe_list(data, "data", "categories", "category", "subjects")
    if not result:
        # fallback: getAllCategory
        data2 = post("getAllCategory", {"courseId": course_id})
        result = safe_list(data2, "data", "categories", "category")
    return result


def fetch_free_videos(user_id: str = "") -> list:
    """tag: freeCourseVideo | userId: ""  — publicly listed free videos"""
    data = post("freeCourseVideo", {"userId": user_id})
    return safe_list(data, "data", "videos", "video")


def fetch_free_pdfs(user_id: str = "") -> list:
    """tag: freeCoursePdf | userId: ""  — publicly listed free PDFs"""
    data = post("freeCoursePdf", {"userId": user_id})
    return safe_list(data, "data", "pdfs", "pdf")


def fetch_configuration() -> dict:
    """tag: configuration  — app settings, player config"""
    data = post("configuration")
    return data or {}


def fetch_banners() -> list:
    """tag: banner | userId: "", bannerType: ""  — home banners"""
    data = post("banner", {"bannerType": ""})
    return safe_list(data, "data", "banners", "banner")


# ─── Helpers ──────────────────────────────────────────────────────────────────
def get_field(obj: dict, *keys):
    """Try multiple keys, return first non-empty value."""
    for k in keys:
        v = obj.get(k)
        if v and str(v).strip():
            return str(v).strip()
    return ""


def get_combined_courses() -> list:
    """Fetch + merge + dedupe allCourses and topCourses."""
    all_courses = fetch_all_courses()
    top_courses = fetch_top_courses()

    seen = set()
    combined = []
    for c in (all_courses + top_courses):
        cid = c.get("id") or c.get("courseId") or id(c)
        if cid not in seen:
            seen.add(cid)
            combined.append(c)
    return combined


# ─── Extraction (text report builders) ────────────────────────────────────────
def extract_single_course(course: dict, outfile, depth: int = 0) -> tuple[int, int, int]:
    """
    Extract subjects + free videos/PDFs for one course.
    Writes a human-readable report to `outfile` (any file-like object
    with .write, e.g. io.StringIO).
    Returns (videos, pdfs, subjects).
    """
    pad = "  " * depth

    course_id    = get_field(course, "id", "courseId", "course_id")
    course_title = get_field(course, "title", "courseName", "name") or f"Course_{course_id}"
    course_img   = get_field(course, "courseImage", "image", "thumbnail", "thumb")
    course_price = get_field(course, "price", "coursePrice", "amount") or "N/A"
    course_desc  = get_field(course, "description", "courseDescription", "about") or ""
    faculty      = get_field(course, "facultyName", "faculty", "teacher", "instructor") or ""
    is_free      = str(course.get("isFree", course.get("free", "0"))) in ("1", "true", "True")

    outfile.write(f"{pad}┌{'─'*74}┐\n")
    outfile.write(f"{pad}│  COURSE  : {course_title}\n")
    outfile.write(f"{pad}│  ID      : {course_id}\n")
    outfile.write(f"{pad}│  Price   : {'FREE' if is_free else course_price}\n")
    if faculty:
        outfile.write(f"{pad}│  Faculty : {faculty}\n")
    if course_img:
        img_url = COURSE_HOST + course_img if not course_img.startswith("http") else course_img
        outfile.write(f"{pad}│  Image   : {img_url}\n")
    if course_desc:
        outfile.write(f"{pad}│  About   : {course_desc[:200]}\n")
    outfile.write(f"{pad}└{'─'*74}┘\n\n")

    total_videos = 0
    total_pdfs   = 0

    if not course_id:
        outfile.write(f"{pad}  [!] No course ID — cannot fetch subjects.\n\n")
        return 0, 0, 0

    # ── Fetch Subjects ──
    subjects = fetch_subjects(course_id)
    outfile.write(f"{pad}  Subjects found: {len(subjects)}\n\n")
    time.sleep(0.3)

    for s_idx, subj in enumerate(subjects, 1):
        sub_id   = get_field(subj, "id", "categoryId", "subjectId", "subject_id")
        sub_name = get_field(subj, "categoryName", "name", "subjectName", "title") or f"Subject {s_idx}"
        sub_count = get_field(subj, "classCount", "videoCount", "count") or ""

        outfile.write(f"{pad}  {'─'*70}\n")
        outfile.write(f"{pad}  ► SUBJECT [{s_idx}]: {sub_name}\n")
        outfile.write(f"{pad}    ID: {sub_id}")
        if sub_count:
            outfile.write(f"  |  Items: {sub_count}")
        outfile.write("\n\n")

        # Try myCourseVideo with empty userId - returns content list
        vdata = post("myCourseVideo", {"categoryId": sub_id, "userId": ""})
        sub_videos = safe_list(vdata, "data", "videos", "video")

        pdata = post("myCoursePdf", {"categoryId": sub_id, "userId": ""})
        sub_pdfs = safe_list(pdata, "data", "pdfs", "pdf")

        if sub_videos:
            outfile.write(f"{pad}    ── VIDEOS ({len(sub_videos)}) ──\n")
            for v in sub_videos:
                v_title = get_field(v, "title", "videoTitle", "name") or "Untitled"
                v_id    = get_field(v, "id", "videoId")
                v_link  = get_field(v, "videoLink", "link", "url", "streamUrl")
                v_file  = get_field(v, "videoFile", "file", "fileName")
                v_ytid  = get_field(v, "ytvideoId", "youtubeId", "yt_id")
                v_type  = get_field(v, "videoType", "type", "playerType")
                v_dur   = get_field(v, "duration", "videoDuration")
                v_lock  = get_field(v, "isLock", "locked", "isPurchased")

                outfile.write(f"{pad}    • {v_title}\n")
                outfile.write(f"{pad}      ID    : {v_id}  |  Type: {v_type}  |  Duration: {v_dur or 'N/A'}\n")
                outfile.write(f"{pad}      Locked: {v_lock or 'N/A'}\n")

                if v_link:
                    outfile.write(f"{pad}      Link  : {v_link}\n")
                if v_file:
                    full = VIDEO_HOST + v_file if not v_file.startswith("http") else v_file
                    outfile.write(f"{pad}      File  : {full}\n")
                if v_ytid:
                    outfile.write(f"{pad}      YT    : https://www.youtube.com/watch?v={v_ytid}\n")
                outfile.write("\n")
                total_videos += 1
        else:
            outfile.write(f"{pad}    (No videos or access required)\n")

        if sub_pdfs:
            outfile.write(f"\n{pad}    ── PDFs ({len(sub_pdfs)}) ──\n")
            for p in sub_pdfs:
                p_title = get_field(p, "title", "pdfTitle", "name") or "Untitled"
                p_id    = get_field(p, "id", "pdfId")
                p_file  = get_field(p, "pdfFile", "file", "url", "fileName")
                p_lock  = get_field(p, "isLock", "locked", "isPurchased")

                outfile.write(f"{pad}    • {p_title}\n")
                outfile.write(f"{pad}      ID    : {p_id}  |  Locked: {p_lock or 'N/A'}\n")
                if p_file:
                    full = PDF_HOST + p_file if not p_file.startswith("http") else p_file
                    outfile.write(f"{pad}      PDF   : {full}\n")
                outfile.write("\n")
                total_pdfs += 1
        else:
            outfile.write(f"{pad}    (No PDFs or access required)\n")

        outfile.write("\n")
        time.sleep(0.35)

    return total_videos, total_pdfs, len(subjects)


def extract_free_section(outfile):
    """Extract globally listed free videos and PDFs."""
    log.info("Fetching free videos & PDFs...")

    free_videos = fetch_free_videos()
    free_pdfs   = fetch_free_pdfs()

    outfile.write(f"\n{'═'*80}\n")
    outfile.write(f"  FREE VIDEOS & PDFs (No Login Required)\n")
    outfile.write(f"{'═'*80}\n\n")

    if free_videos:
        outfile.write(f"── FREE VIDEOS ({len(free_videos)}) ──\n\n")
        for v in free_videos:
            v_title = get_field(v, "title", "videoTitle", "name") or "Untitled"
            v_link  = get_field(v, "videoLink", "link", "url")
            v_file  = get_field(v, "videoFile", "file")
            v_ytid  = get_field(v, "ytvideoId", "youtubeId")
            v_type  = get_field(v, "videoType", "type") or "N/A"
            outfile.write(f"  • {v_title}  [type: {v_type}]\n")
            if v_link:  outfile.write(f"    Link : {v_link}\n")
            if v_file:  outfile.write(f"    File : {VIDEO_HOST + v_file}\n")
            if v_ytid:  outfile.write(f"    YT   : https://www.youtube.com/watch?v={v_ytid}\n")
            outfile.write("\n")
    else:
        outfile.write("  (No free videos found)\n\n")

    if free_pdfs:
        outfile.write(f"── FREE PDFs ({len(free_pdfs)}) ──\n\n")
        for p in free_pdfs:
            p_title = get_field(p, "title", "pdfTitle", "name") or "Untitled"
            p_file  = get_field(p, "pdfFile", "file", "url")
            outfile.write(f"  • {p_title}\n")
            if p_file:  outfile.write(f"    PDF  : {PDF_HOST + p_file}\n")
            outfile.write("\n")
    else:
        outfile.write("  (No free PDFs found)\n\n")

    log.info("Free videos: %d | Free PDFs: %d", len(free_videos), len(free_pdfs))
    return len(free_videos), len(free_pdfs)


def build_full_report(targets: list) -> tuple[str, dict]:
    """
    Build the same text report the CLI wrote to disk for options 1/2,
    for a given list of course dicts. Returns (report_text, stats).
    """
    buf = io.StringIO()
    buf.write(f"{'='*80}\n")
    buf.write(f"  BRIDGE TO SUCCESS — BATCH EXTRACTION\n")
    buf.write(f"  Extracted : {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    buf.write(f"  Courses   : {len(targets)}\n")
    buf.write(f"{'='*80}\n\n")

    fv, fp = extract_free_section(buf)

    buf.write(f"\n{'='*80}\n")
    buf.write(f"  COURSE DETAILS\n")
    buf.write(f"{'='*80}\n\n")

    total_v = total_p = total_s = 0
    for i, course in enumerate(targets, 1):
        title = get_field(course, "title", "courseName", "name") or f"Course {i}"
        log.info("[%d/%d] Extracting: %s", i, len(targets), title)

        v, p, s = extract_single_course(course, buf)
        total_v += v
        total_p += p
        total_s += s

    buf.write(f"\n{'='*80}\n")
    buf.write(f"  SUMMARY\n")
    buf.write(f"{'='*80}\n")
    buf.write(f"  Courses extracted : {len(targets)}\n")
    buf.write(f"  Total Subjects    : {total_s}\n")
    buf.write(f"  Total Videos      : {total_v}\n")
    buf.write(f"  Total PDFs        : {total_p}\n")
    buf.write(f"  Free Videos       : {fv}\n")
    buf.write(f"  Free PDFs         : {fp}\n")
    buf.write(f"  Grand Total Links : {total_v + total_p + fv + fp}\n")
    buf.write(f"{'='*80}\n")

    stats = {
        "courses_extracted": len(targets),
        "total_subjects": total_s,
        "total_videos": total_v,
        "total_pdfs": total_p,
        "free_videos": fv,
        "free_pdfs": fp,
        "grand_total_links": total_v + total_p + fv + fp,
    }
    return buf.getvalue(), stats


def build_course_list_report(combined: list) -> str:
    """Same as CLI option 4 — info-only listing of all courses."""
    buf = io.StringIO()
    buf.write("BRIDGE TO SUCCESS — COURSE LIST\n")
    buf.write(f"Extracted: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    buf.write(f"Total Courses: {len(combined)}\n\n")
    buf.write(f"{'─'*80}\n\n")
    for i, c in enumerate(combined, 1):
        title    = get_field(c, "title", "courseName", "name") or "N/A"
        cid      = get_field(c, "id", "courseId") or "N/A"
        price    = get_field(c, "price", "coursePrice", "amount") or "N/A"
        faculty  = get_field(c, "facultyName", "faculty", "teacher") or "N/A"
        img      = get_field(c, "courseImage", "image", "thumbnail") or ""
        is_free  = str(c.get("isFree", c.get("free", "0"))) in ("1", "true", "True")
        desc     = get_field(c, "description", "courseDescription", "about") or ""
        buf.write(f"[{i}] {title}\n")
        buf.write(f"    ID      : {cid}\n")
        buf.write(f"    Price   : {'FREE' if is_free else price}\n")
        buf.write(f"    Faculty : {faculty}\n")
        if img:
            buf.write(f"    Image   : {COURSE_HOST + img if not img.startswith('http') else img}\n")
        if desc:
            buf.write(f"    About   : {desc[:300]}\n")
        buf.write("\n")
    return buf.getvalue()
