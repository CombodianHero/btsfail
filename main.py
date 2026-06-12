"""
main.py
=======
Flask API for the Bridge to Success — No-Login Extractor.
Uses the shared `extractor` module (same functions as the Telegram bot).

Run locally:
    python main.py

On Koyeb this also serves as the health-check endpoint when running
alongside the Telegram bot via app.py.
"""

import os
import time
import logging
from functools import wraps

from flask import Flask, jsonify, request, Response

import extractor as ext

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("bridgetosuccess.api")

app = Flask(__name__)


def jsonp(success=True, **kwargs):
    payload = {"success": success}
    payload.update(kwargs)
    return jsonify(payload)


def handle_errors(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            log.exception("Unhandled error in %s", fn.__name__)
            return jsonp(success=False, error=str(e)), 500
    return wrapper


@app.route("/")
def index():
    return jsonp(
        message="Bridge to Success — No-Login Extractor API",
        endpoints={
            "GET /health":                      "Health check",
            "GET /api/courses":                 "All available courses (allCourses + topCourses, merged & deduped)",
            "GET /api/courses/all":             "Raw allCourses response",
            "GET /api/courses/top":             "Raw topCourses response",
            "GET /api/course/<course_id>/info": "Course info (description, faculty, etc.)",
            "GET /api/course/<course_id>/subjects": "Subjects/categories for a course",
            "GET /api/free-content":            "Free videos & PDFs (no login)",
            "GET /api/configuration":           "App configuration",
            "GET /api/banners":                 "Home banners",
            "GET /api/course/<course_id>/report": "Full text report for one course (?download=1 for .txt)",
            "GET /api/report/all":              "Full text report for ALL courses (?download=1 for .txt) — slow!",
            "GET /api/report/list":             "Course list (info-only) report (?download=1 for .txt)",
        },
    )


@app.route("/health")
def health():
    return jsonp(status="ok", time=time.strftime("%Y-%m-%d %H:%M:%S"))


@app.route("/api/courses")
@handle_errors
def api_courses():
    combined = ext.get_combined_courses()
    return jsonp(count=len(combined), courses=combined)


@app.route("/api/courses/all")
@handle_errors
def api_courses_all():
    courses = ext.fetch_all_courses()
    return jsonp(count=len(courses), courses=courses)


@app.route("/api/courses/top")
@handle_errors
def api_courses_top():
    courses = ext.fetch_top_courses()
    return jsonp(count=len(courses), courses=courses)


@app.route("/api/course/<course_id>/info")
@handle_errors
def api_course_info(course_id):
    info = ext.fetch_course_info(course_id)
    if not info:
        return jsonp(success=False, error="No info found for this course"), 404
    return jsonp(course_id=course_id, info=info)


@app.route("/api/course/<course_id>/subjects")
@handle_errors
def api_course_subjects(course_id):
    subjects = ext.fetch_subjects(course_id)
    return jsonp(course_id=course_id, count=len(subjects), subjects=subjects)


@app.route("/api/free-content")
@handle_errors
def api_free_content():
    videos = ext.fetch_free_videos()
    pdfs = ext.fetch_free_pdfs()
    return jsonp(
        videos={"count": len(videos), "items": videos},
        pdfs={"count": len(pdfs), "items": pdfs},
    )


@app.route("/api/configuration")
@handle_errors
def api_configuration():
    return jsonp(configuration=ext.fetch_configuration())


@app.route("/api/banners")
@handle_errors
def api_banners():
    banners = ext.fetch_banners()
    return jsonp(count=len(banners), banners=banners)


@app.route("/api/course/<course_id>/report")
@handle_errors
def api_course_report(course_id):
    combined = ext.get_combined_courses()
    course = next(
        (c for c in combined if ext.get_field(c, "id", "courseId", "course_id") == str(course_id)),
        None,
    )
    if not course:
        return jsonp(success=False, error="Course not found"), 404

    report, stats = ext.build_full_report([course])

    if request.args.get("download"):
        title_slug = ext.sanitize(ext.get_field(course, "title", "courseName", "name") or "course")
        fname = f"BridgeToSuccess_{title_slug}.txt"
        return Response(
            report,
            mimetype="text/plain",
            headers={"Content-Disposition": f"attachment; filename={fname}"},
        )

    return jsonp(course_id=course_id, stats=stats, report=report)


@app.route("/api/report/all")
@handle_errors
def api_report_all():
    combined = ext.get_combined_courses()
    if not combined:
        return jsonp(success=False, error="Could not fetch any courses"), 502

    report, stats = ext.build_full_report(combined)

    if request.args.get("download"):
        return Response(
            report,
            mimetype="text/plain",
            headers={"Content-Disposition": "attachment; filename=BridgeToSuccess_ALL_Courses.txt"},
        )

    return jsonp(stats=stats, report=report)


@app.route("/api/report/list")
@handle_errors
def api_report_list():
    combined = ext.get_combined_courses()
    report = ext.build_course_list_report(combined)

    if request.args.get("download"):
        return Response(
            report,
            mimetype="text/plain",
            headers={"Content-Disposition": "attachment; filename=BridgeToSuccess_CourseList.txt"},
        )

    return jsonp(count=len(combined), report=report)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
