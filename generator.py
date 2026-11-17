"""Idea and storyboard generation.

Two sources:
* the idea bank (idea_templates and scene_templates tables), always available;
* Gemini AI (optional), used only when GEMINI_API_KEY is set.
"""
import json
import re

import requests

import config
import stickfigure as sf
from db import execute, get_db, query_all

PLACEHOLDER = re.compile(r"\{(topic|Topic|audience|niche|platform|hook|title)\}")
LIMITS = {"title": 150, "hook": 200, "description": 500, "action_text": 250, "dialogue": 250,
          "on_screen_text": 80}


class AIError(Exception):
    """Raised when the AI service is unavailable or returns something unusable."""


def clean_topic(topic):
    """Trim and tidy what the user typed as their topic."""
    return re.sub(r"\s+", " ", (topic or "").strip())[:60]


def fill(template, ctx):
    """Replace {placeholders} in a template with values from ctx."""
    return PLACEHOLDER.sub(lambda m: str(ctx.get(m.group(1), m.group(0))), template)


def clip(text, field):
    """Shorten text to fit its database column."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    limit = LIMITS[field]
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def context_for(project, idea=None):
    """Build the placeholder values for one project (and optionally an idea)."""
    topic = project["topic"]
    ctx = {"topic": topic, "Topic": topic[:1].upper() + topic[1:], "audience": project["target_audience"],
           "niche": project["niche"], "platform": project["platform"]}
    if idea:
        ctx.update(hook=idea["hook"], title=idea["title"])
    return ctx


# ---------------------------------------------------------------- idea bank
def bank_ideas(project, count=5):
    """Pick unused templates for this project's format and niche and save them as ideas.

    Niche-specific templates come first, then general ones, in random order.
    Returns the number of ideas added (0 when the bank has run out).
    """
    templates = query_all(
        """
        SELECT t.template_id, t.title_template, t.hook_template, t.description_template
        FROM idea_templates t
        WHERE t.format_id = %s
          AND t.is_active = 1
          AND (t.niche_id = %s OR t.niche_id IS NULL)
          AND t.template_id NOT IN (
                SELECT i.template_id FROM ideas i
                WHERE i.project_id = %s AND i.template_id IS NOT NULL)
        ORDER BY (t.niche_id IS NULL), RAND()
        LIMIT %s
        """,
        (project["format_id"], project["niche_id"], project["project_id"], count),
    )
    ctx = context_for(project)
    conn = get_db()
    with conn.cursor() as cur:
        for t in templates:
            cur.execute(
                "INSERT INTO ideas (project_id, template_id, title, hook, description, source) "
                "VALUES (%s, %s, %s, %s, %s, 'bank')",
                (project["project_id"], t["template_id"], clip(fill(t["title_template"], ctx), "title"),
                 clip(fill(t["hook_template"], ctx), "hook"), clip(fill(t["description_template"], ctx), "description")),
            )
    conn.commit()
    return len(templates)


def bank_storyboard(project, idea):
    """Create storyboard frames for an idea from its format's scene templates."""
    scenes = query_all(
        "SELECT scene_order, shot_type, pose, prop, action_template, dialogue_template, text_template, duration_sec "
        "FROM scene_templates WHERE format_id = %s ORDER BY scene_order",
        (project["format_id"],),
    )
    ctx = context_for(project, idea)
    frames = [{
        "shot_type": s["shot_type"], "pose": s["pose"], "prop": s["prop"],
        "action_text": fill(s["action_template"], ctx), "dialogue": fill(s["dialogue_template"], ctx),
        "on_screen_text": fill(s["text_template"], ctx), "duration_sec": s["duration_sec"],
    } for s in scenes]
    save_frames(idea["idea_id"], frames)
    return len(frames)


def save_frames(idea_id, frames):
    """Replace an idea's storyboard with the given frames (one transaction)."""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM storyboard_frames WHERE idea_id = %s", (idea_id,))
        for no, f in enumerate(frames, start=1):
            cur.execute(
                "INSERT INTO storyboard_frames (idea_id, frame_no, shot_type, pose, prop, action_text, dialogue, "
                "on_screen_text, duration_sec) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (idea_id, no, f["shot_type"], f["pose"], f["prop"], clip(f["action_text"], "action_text"),
                 clip(f["dialogue"], "dialogue"), clip(f["on_screen_text"], "on_screen_text"),
                 max(1, min(60, int(f["duration_sec"])))),
            )
        cur.execute("UPDATE ideas SET is_selected = 1 WHERE idea_id = %s", (idea_id,))
    conn.commit()


# ---------------------------------------------------------------- Gemini AI
def ai_enabled():
    return bool(config.GEMINI_API_KEY)


def _ask_gemini(prompt):
    """Send one prompt to Gemini and return the parsed JSON reply."""
    if not ai_enabled():
        raise AIError("AI is not set up. Add GEMINI_API_KEY to use it.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.9, "responseMimeType": "application/json"}}
    try:
        r = requests.post(url, json=body, timeout=40,
                          headers={"x-goog-api-key": config.GEMINI_API_KEY, "Content-Type": "application/json"})
    except requests.RequestException as e:
        raise AIError("Couldn't reach the AI service. Check your internet connection.") from e
    if r.status_code != 200:
        raise AIError(f"The AI service returned an error ({r.status_code}). Try again later.")
    try:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except (KeyError, IndexError, ValueError) as e:
        raise AIError("The AI reply couldn't be read. Try again.") from e


WRITING_RULES = ("Write in simple, natural English for short-form video creators. Sound like a real person. "
                 "No emojis, no hashtags, no em dashes, no hype words like 'game-changer' or 'unlock'.")


def ai_ideas(project, count=5):
    """Ask Gemini for new ideas and save them. Returns the number saved."""
    prompt = (
        f"You are a content strategist. Suggest {count} different short-form video ideas.\n"
        f"Topic: {project['topic']}\nNiche: {project['niche']}\nVideo format: {project['format_name']}\n"
        f"Platform: {project['platform']}\nAudience: {project['target_audience']}\n{WRITING_RULES}\n"
        'Reply with JSON only: {"ideas": [{"title": "max 80 characters", "hook": "first line, max 15 words", '
        '"description": "2 sentences on what the video shows"}]}'
    )
    data = _ask_gemini(prompt)
    ideas = [i for i in data.get("ideas", []) if isinstance(i, dict) and i.get("title") and i.get("hook")]
    if not ideas:
        raise AIError("The AI didn't return any ideas. Try again.")
    for i in ideas[:count]:
        execute("INSERT INTO ideas (project_id, title, hook, description, source) VALUES (%s, %s, %s, %s, 'ai')",
                (project["project_id"], clip(i["title"], "title"), clip(i["hook"], "hook"),
                 clip(i.get("description", ""), "description")))
    return len(ideas[:count])


def ai_storyboard(project, idea):
    """Ask Gemini for a 6-frame storyboard and save it (poses and props are validated)."""
    prompt = (
        "You are a storyboard artist for short vertical (9:16) UGC videos. Plan exactly 6 frames.\n"
        f"Video title: {idea['title']}\nHook (frame 1 dialogue): {idea['hook']}\nIdea: {idea['description']}\n"
        f"Format: {project['format_name']}\nAudience: {project['target_audience']}\n{WRITING_RULES}\n"
        f"shot_type must be one of {list(sf.SHOTS)}. pose must be one of {list(sf.POSES)}. "
        f"prop must be one of {list(sf.PROPS)}. Total duration should be about {project['default_duration']} seconds.\n"
        'Reply with JSON only: {"frames": [{"shot_type": "", "pose": "", "prop": "", "action_text": "what the '
        'creator does", "dialogue": "what they say", "on_screen_text": "max 5 words", "duration_sec": 5}]}'
    )
    data = _ask_gemini(prompt)
    frames = []
    for f in data.get("frames", [])[:8]:
        if not isinstance(f, dict):
            continue
        frames.append({
            "shot_type": f.get("shot_type") if f.get("shot_type") in sf.SHOTS else "medium",
            "pose": f.get("pose") if f.get("pose") in sf.POSES else "talk",
            "prop": f.get("prop") if f.get("prop") in sf.PROPS else "none",
            "action_text": f.get("action_text") or "Film this scene.",
            "dialogue": f.get("dialogue") or "",
            "on_screen_text": f.get("on_screen_text") or "",
            "duration_sec": f.get("duration_sec") if isinstance(f.get("duration_sec"), int) else 5,
        })
    if len(frames) < 3:
        raise AIError("The AI storyboard was incomplete. Try again.")
    save_frames(idea["idea_id"], frames)
    return len(frames)
