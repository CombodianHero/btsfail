"""
bot.py
======
Telegram bot for the Bridge to Success — No-Login Extractor.

Commands:
  /start            - welcome message + command list
  /help             - same as /start
  /courses          - list all available courses with their IDs
  /free             - free videos & PDFs (no login required)
  /info <id>        - course info (description, faculty, etc.)
  /subjects <id>    - subjects/categories inside a course
  /report <id>      - full extraction report for one course (.txt file)
  /courselist       - info-only listing of all courses (.txt file)
  /reportall        - full extraction report for ALL courses (.txt file, slow!)

Environment variables:
  TELEGRAM_BOT_TOKEN - your bot token from @BotFather (required)
"""

import io
import os
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

import extractor as ext

log = logging.getLogger("bridgetosuccess.bot")

MAX_LIST_ITEMS = 30  # avoid hitting Telegram's 4096-char message limit


# ─── Helper: format course list ───────────────────────────────────────────────
def format_course_list(courses: list) -> str:
    if not courses:
        return "No courses found."

    lines = [f"📚 *Available Courses* ({len(courses)} found)\n"]
    for i, c in enumerate(courses[:MAX_LIST_ITEMS], 1):
        title = ext.get_field(c, "title", "courseName", "name", "course_name") or "Untitled"
        cid   = ext.get_field(c, "id", "courseId", "course_id") or "N/A"
        price = ext.get_field(c, "price", "coursePrice", "amount", "fee") or "N/A"
        is_free = str(c.get("isFree", c.get("free", "0"))) in ("1", "true", "True")
        price_str = "FREE" if is_free else price
        lines.append(f"{i}. *{title}*\n   ID: `{cid}`  |  Price: {price_str}")

    if len(courses) > MAX_LIST_ITEMS:
        lines.append(f"\n...and {len(courses) - MAX_LIST_ITEMS} more.")

    lines.append("\nUse /subjects <id>, /info <id> or /report <id> with a course ID above.")
    return "\n".join(lines)


# ─── Command Handlers ──────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *Bridge to Success — No-Login Extractor Bot*\n\n"
        "Available commands:\n"
        "/courses — list all available courses & their IDs\n"
        "/free — free videos & PDFs (no login)\n"
        "/info <id> — course info (description, faculty, etc.)\n"
        "/subjects <id> — subjects/categories inside a course\n"
        "/report <id> — full extraction report for a course (.txt)\n"
        "/courselist — info-only listing of all courses (.txt)\n"
        "/reportall — full report for ALL courses (.txt, slow!)\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def courses_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Fetching courses...")
    combined = ext.get_combined_courses()
    await update.message.reply_text(format_course_list(combined), parse_mode=ParseMode.MARKDOWN)


async def free_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Fetching free videos & PDFs...")
    videos = ext.fetch_free_videos()
    pdfs = ext.fetch_free_pdfs()

    lines = [f"🎬 *Free Videos* ({len(videos)})"]
    for v in videos[:MAX_LIST_ITEMS]:
        title = ext.get_field(v, "title", "videoTitle", "name") or "Untitled"
        lines.append(f"• {title}")

    lines.append(f"\n📄 *Free PDFs* ({len(pdfs)})")
    for p in pdfs[:MAX_LIST_ITEMS]:
        title = ext.get_field(p, "title", "pdfTitle", "name") or "Untitled"
        lines.append(f"• {title}")

    if not videos and not pdfs:
        lines = ["No free videos or PDFs found."]

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /info <course_id>\nGet IDs from /courses")
        return

    course_id = context.args[0]
    await update.message.reply_text(f"⏳ Fetching info for course {course_id}...")
    info = ext.fetch_course_info(course_id)
    if not info:
        await update.message.reply_text("No info found for this course.")
        return

    title   = ext.get_field(info, "title", "courseName", "name") or "N/A"
    faculty = ext.get_field(info, "facultyName", "faculty", "teacher", "instructor") or "N/A"
    price   = ext.get_field(info, "price", "coursePrice", "amount") or "N/A"
    desc    = ext.get_field(info, "description", "courseDescription", "about") or "N/A"

    text = (
        f"📘 *{title}*\n"
        f"ID: `{course_id}`\n"
        f"Faculty: {faculty}\n"
        f"Price: {price}\n\n"
        f"{desc[:1000]}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def subjects_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /subjects <course_id>\nGet IDs from /courses")
        return

    course_id = context.args[0]
    await update.message.reply_text(f"⏳ Fetching subjects for course {course_id}...")
    subjects = ext.fetch_subjects(course_id)

    if not subjects:
        await update.message.reply_text("No subjects found for this course.")
        return

    lines = [f"📂 *Subjects for course {course_id}* ({len(subjects)})\n"]
    for i, s in enumerate(subjects[:MAX_LIST_ITEMS], 1):
        name = ext.get_field(s, "categoryName", "name", "subjectName", "title") or f"Subject {i}"
        sid  = ext.get_field(s, "id", "categoryId", "subjectId", "subject_id") or "N/A"
        lines.append(f"{i}. {name} (ID: `{sid}`)")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /report <course_id>\nGet IDs from /courses")
        return

    course_id = context.args[0]
    await update.message.reply_text(
        f"⏳ Extracting full report for course {course_id}... this may take a minute."
    )

    combined = ext.get_combined_courses()
    course = next(
        (c for c in combined if ext.get_field(c, "id", "courseId", "course_id") == str(course_id)),
        None,
    )
    if not course:
        await update.message.reply_text("Course not found. Check the ID with /courses.")
        return

    report, stats = ext.build_full_report([course])
    title_slug = ext.sanitize(ext.get_field(course, "title", "courseName", "name") or "course")
    fname = f"BridgeToSuccess_{title_slug}.txt"

    file_bytes = io.BytesIO(report.encode("utf-8"))
    file_bytes.name = fname

    summary = (
        f"✅ Done!\n"
        f"Subjects: {stats['total_subjects']} | "
        f"Videos: {stats['total_videos']} | "
        f"PDFs: {stats['total_pdfs']}"
    )
    await update.message.reply_document(document=file_bytes, filename=fname, caption=summary)


async def courselist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Building course list report...")
    combined = ext.get_combined_courses()
    report = ext.build_course_list_report(combined)

    file_bytes = io.BytesIO(report.encode("utf-8"))
    file_bytes.name = "BridgeToSuccess_CourseList.txt"

    await update.message.reply_document(
        document=file_bytes,
        filename="BridgeToSuccess_CourseList.txt",
        caption=f"✅ {len(combined)} courses listed.",
    )


async def reportall_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⏳ Extracting full report for ALL courses... this can take several minutes, please wait."
    )

    combined = ext.get_combined_courses()
    if not combined:
        await update.message.reply_text("Could not fetch any courses.")
        return

    report, stats = ext.build_full_report(combined)

    file_bytes = io.BytesIO(report.encode("utf-8"))
    file_bytes.name = "BridgeToSuccess_ALL_Courses.txt"

    summary = (
        f"✅ Done!\n"
        f"Courses: {stats['courses_extracted']} | "
        f"Subjects: {stats['total_subjects']} | "
        f"Videos: {stats['total_videos']} | "
        f"PDFs: {stats['total_pdfs']} | "
        f"Free Videos: {stats['free_videos']} | "
        f"Free PDFs: {stats['free_pdfs']}\n"
        f"Grand total links: {stats['grand_total_links']}"
    )
    await update.message.reply_document(
        document=file_bytes, filename="BridgeToSuccess_ALL_Courses.txt", caption=summary
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Update %s caused error %s", update, context.error)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(
            "⚠️ Something went wrong while processing that command. Please try again."
        )


# ─── App Builder ────────────────────────────────────────────────────────────────
def build_application() -> Application:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("courses", courses_cmd))
    application.add_handler(CommandHandler("free", free_cmd))
    application.add_handler(CommandHandler("info", info_cmd))
    application.add_handler(CommandHandler("subjects", subjects_cmd))
    application.add_handler(CommandHandler("report", report_cmd))
    application.add_handler(CommandHandler("courselist", courselist_cmd))
    application.add_handler(CommandHandler("reportall", reportall_cmd))
    application.add_error_handler(error_handler)

    return application


def run_polling():
    """Blocking call — runs the bot with long polling."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    application = build_application()
    log.info("Starting Telegram bot (polling)...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    run_polling()
