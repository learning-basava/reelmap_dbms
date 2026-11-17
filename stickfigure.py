"""Stick-figure storyboard drawings.

Every frame is a 9:16 phone screen, 90 x 160 units. ``frame_shapes`` turns a
pose, a shot type and a prop into simple shapes (lines, circles, rectangles,
polygons and short labels). Two renderers draw those same shapes:
``to_svg`` for the website and ``draw_pdf`` for the PDF export, so the
storyboard looks the same in both places.
"""
from html import escape

FRAME_W, FRAME_H = 90, 160

POSES = {
    "stand": "Standing", "wave": "Waving", "talk": "Talking", "point": "Pointing",
    "think": "Thinking", "hold_phone": "Holding phone (selfie)", "hold_product": "Holding product",
    "thumbs_up": "Thumbs up", "excited": "Excited", "sit_laptop": "Sitting at laptop",
    "walk": "Walking", "shrug": "Shrugging",
}
PROPS = {
    "none": "No prop", "phone": "Phone", "product": "Product box", "laptop": "Laptop",
    "speech": "Speech bubble", "sparkle": "Sparkles", "arrow": "Arrow", "before_after": "Before / after split",
    "mirror": "Mirror", "cup": "Cup",
}
SHOTS = {"wide": "Wide shot", "medium": "Medium shot", "close_up": "Close-up"}

# Body points in figure units: top of head y=0, feet y=100, centre line x=0.
BASE = {
    "head": (0, 10), "neck": (0, 19), "shoulder": (0, 24), "hip": (0, 56),
    "l_elbow": (-11, 37), "l_hand": (-14, 53), "r_elbow": (11, 37), "r_hand": (14, 53),
    "l_knee": (-6, 78), "l_foot": (-10, 100), "r_knee": (6, 78), "r_foot": (10, 100),
}
POSE_POINTS = {
    "stand": {},
    "wave": {"r_elbow": (17, 27), "r_hand": (21, 9)},
    "talk": {"l_elbow": (-14, 37), "l_hand": (-24, 32), "r_elbow": (14, 37), "r_hand": (24, 32)},
    "point": {"r_elbow": (16, 28), "r_hand": (32, 24)},
    "think": {"r_elbow": (11, 38), "r_hand": (5, 19), "l_elbow": (-9, 39), "l_hand": (8, 41)},
    "hold_phone": {"r_elbow": (15, 31), "r_hand": (20, 13)},
    "hold_product": {"l_elbow": (-12, 38), "l_hand": (-7, 41), "r_elbow": (12, 38), "r_hand": (7, 41)},
    "thumbs_up": {"r_elbow": (15, 37), "r_hand": (19, 25)},
    "excited": {"l_elbow": (-14, 21), "l_hand": (-20, 4), "r_elbow": (14, 21), "r_hand": (20, 4),
                "l_foot": (-15, 100), "r_foot": (15, 100)},
    "sit_laptop": {"l_elbow": (-12, 45), "l_hand": (-7, 58), "r_elbow": (12, 45), "r_hand": (7, 58)},
    "walk": {"l_elbow": (-9, 38), "l_hand": (-3, 53), "r_elbow": (13, 37), "r_hand": (19, 50),
             "l_knee": (-7, 77), "l_foot": (-17, 99), "r_knee": (8, 78), "r_foot": (14, 99)},
    "shrug": {"l_elbow": (-15, 33), "l_hand": (-21, 21), "r_elbow": (15, 33), "r_hand": (21, 21)},
}
FACES = {"think": "flat", "shrug": "flat", "excited": "open"}

# How each shot type places the figure inside the 90 x 160 frame.
SHOT_LAYOUT = {
    "wide": {"scale": 1.0, "top": 40},
    "medium": {"scale": 1.6, "top": 30},
    "close_up": {"scale": 2.4, "top": 30},
}


def _transform(shot):
    layout = SHOT_LAYOUT.get(shot, SHOT_LAYOUT["medium"])
    s, top = layout["scale"], layout["top"]
    return (lambda x, y: (FRAME_W / 2 + x * s, top + y * s)), s


def frame_shapes(pose, shot="medium", prop="none"):
    """Return the list of shapes that draw one storyboard frame."""
    pose = pose if pose in POSE_POINTS else "stand"
    pts = {**BASE, **POSE_POINTS[pose]}
    tf, s = _transform(shot)
    stroke = round(1.3 + 0.55 * s, 2)
    shapes = []

    def line(a, b, w=stroke, color="ink"):
        shapes.append(("line", *tf(*a), *tf(*b), w, color))

    def poly(points, w=stroke, color="ink", fill=None, closed=False):
        shapes.append(("poly", [tf(*p) for p in points], w, color, fill, closed))

    if shot == "wide":  # floor line gives a sense of space
        shapes.append(("line", 6, tf(0, 100)[1] + 1, FRAME_W - 6, tf(0, 100)[1] + 1, 0.8, "muted"))

    if prop == "mirror":
        shapes.append(("rect", 62, 26, 22, 70, 1.2, "muted", "soft", 10))
    if prop == "before_after":
        shapes.append(("line", FRAME_W / 2, 8, FRAME_W / 2, FRAME_H - 8, 1.0, "muted"))
        shapes.append(("text", 22, 150, 6, "BEFORE", "ink", "middle"))
        shapes.append(("text", 68, 150, 6, "AFTER", "accent", "middle"))

    # Desk and laptop for the sitting pose (drawn behind the arms).
    if pose == "sit_laptop":
        poly([(-30, 60), (30, 60), (30, 64), (-30, 64)], w=stroke * 0.8, fill="soft", closed=True)
        line((-26, 64), (-26, 100), w=stroke * 0.8)
        line((26, 64), (26, 100), w=stroke * 0.8)

    # Body.
    hx, hy = tf(*pts["head"])
    shapes.append(("circle", hx, hy, 8 * s, stroke, "ink", "paper"))
    line(pts["neck"], pts["hip"])
    for side in ("l", "r"):
        line(pts["shoulder"], pts[f"{side}_elbow"])
        line(pts[f"{side}_elbow"], pts[f"{side}_hand"])
        if pose != "sit_laptop":
            line(pts["hip"], pts[f"{side}_knee"])
            line(pts[f"{side}_knee"], pts[f"{side}_foot"])

    # Face.
    eye_r = max(0.5, 0.9 * s)
    for ex in (-3, 3):
        x, y = tf(ex, 8.5)
        shapes.append(("circle", x, y, eye_r, 0, "ink", "ink"))
    face = FACES.get(pose, "smile")
    if face == "smile":
        poly([(-3.2, 12.6), (-1.5, 14.2), (1.5, 14.2), (3.2, 12.6)], w=stroke * 0.6)
    elif face == "flat":
        line((-2.6, 13.6), (2.6, 13.6), w=stroke * 0.6)
    else:
        x, y = tf(0, 13.6)
        shapes.append(("circle", x, y, 1.7 * s, stroke * 0.6, "ink", "paper"))

    # Thumb for the thumbs-up pose.
    if pose == "thumbs_up":
        hx2, hy2 = pts["r_hand"]
        line((hx2, hy2), (hx2, hy2 - 5))

    # Laptop on the desk.
    if pose == "sit_laptop" or prop == "laptop":
        lx, ly = (0, 60) if pose == "sit_laptop" else (24, 56)
        poly([(lx - 13, ly - 14), (lx + 13, ly - 14), (lx + 13, ly), (lx - 13, ly)],
             w=stroke * 0.8, fill="soft", closed=True)
        line((lx - 2, ly - 8), (lx + 2, ly - 8), w=stroke * 0.5, color="muted")

    # Props held in the hands.
    if prop == "phone":
        px, py = pts["r_hand"] if pose in ("hold_phone", "wave", "thumbs_up") else pts["r_hand"]
        poly([(px - 3, py - 6), (px + 3, py - 6), (px + 3, py + 4), (px - 3, py + 4)],
             w=stroke * 0.7, fill="ink", closed=True)
    if prop == "product":
        if pose == "hold_product":
            bx, by = 0, 34
        else:
            bx, by = pts["r_hand"][0], pts["r_hand"][1] - 8
        poly([(bx - 8, by), (bx + 8, by), (bx + 8, by + 13), (bx - 8, by + 13)],
             w=stroke * 0.8, fill="accent_soft", closed=True)
        line((bx - 8, by + 4), (bx + 8, by + 4), w=stroke * 0.5)
    if prop == "cup":
        cx, cy = pts["r_hand"]
        poly([(cx - 3, cy - 7), (cx + 3, cy - 7), (cx + 2.4, cy + 1), (cx - 2.4, cy + 1)],
             w=stroke * 0.7, fill="paper", closed=True)

    # Frame-level props.
    if prop == "speech":
        bx, by = (FRAME_W - 29, 34) if shot != "close_up" else (FRAME_W - 27, 40)
        shapes.append(("rect", bx, by, 26, 15, 1.1, "ink", "paper", 6))
        shapes.append(("poly", [(bx + 6, by + 15), (bx + 3, by + 21), (bx + 11, by + 15)], 1.1, "ink", "paper", True))
        shapes.append(("text", bx + 13, by + 10, 7, "...", "ink", "middle"))
    if prop == "sparkle":
        for sx, sy, r in ((14, 30, 4.5), (76, 40, 3.5), (70, 98, 3), (18, 104, 2.6)):
            shapes.append(("poly", [(sx, sy - r), (sx + r * 0.3, sy - r * 0.3), (sx + r, sy),
                                    (sx + r * 0.3, sy + r * 0.3), (sx, sy + r), (sx - r * 0.3, sy + r * 0.3),
                                    (sx - r, sy), (sx - r * 0.3, sy - r * 0.3)], 0.6, "accent", "accent", True))
    if prop == "arrow":
        ay = 84
        shapes.append(("line", 84, ay, 68, ay, 1.8, "accent"))
        shapes.append(("poly", [(66, ay), (72, ay - 4), (72, ay + 4)], 0.8, "accent", "accent", True))
    return shapes


COLORS = {"ink": "#1f2328", "muted": "#9aa0a6", "accent": "#e4572e", "accent_soft": "#fde3da",
          "soft": "#eef0f2", "paper": "#ffffff"}


def to_svg(pose, shot="medium", prop="none", css_class="sf"):
    """Return an inline SVG drawing of one frame (without on-screen text)."""
    parts = [f'<svg class="{css_class}" viewBox="0 0 {FRAME_W} {FRAME_H}" role="img" '
             f'aria-label="{escape(POSES.get(pose, pose))}, {escape(SHOTS.get(shot, shot))}" '
             'preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">']
    for sh in frame_shapes(pose, shot, prop):
        kind = sh[0]
        if kind == "line":
            _, x1, y1, x2, y2, w, c = sh
            parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                         f'stroke="{COLORS[c]}" stroke-width="{w}" stroke-linecap="round"/>')
        elif kind == "circle":
            _, cx, cy, r, w, c, fill = sh
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{COLORS[fill]}" '
                         f'stroke="{COLORS[c]}" stroke-width="{w}"/>')
        elif kind == "poly":
            _, points, w, c, fill, closed = sh
            tag = "polygon" if closed else "polyline"
            pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
            parts.append(f'<{tag} points="{pts}" fill="{COLORS[fill] if fill else "none"}" '
                         f'stroke="{COLORS[c]}" stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"/>')
        elif kind == "rect":
            _, x, y, w_, h, w, c, fill, r = sh
            parts.append(f'<rect x="{x}" y="{y}" width="{w_}" height="{h}" rx="{r}" fill="{COLORS[fill]}" '
                         f'stroke="{COLORS[c]}" stroke-width="{w}"/>')
        elif kind == "text":
            _, x, y, size, txt, c, anchor = sh
            parts.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="700" fill="{COLORS[c]}" '
                         f'text-anchor="{anchor}" font-family="Helvetica, Arial, sans-serif">{escape(txt)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def draw_pdf(pdf, x, y, w, pose, shot="medium", prop="none"):
    """Draw one frame into an fpdf2 document. The box is w wide and 16:9 tall."""
    k = w / FRAME_W
    h = FRAME_H * k
    with pdf.rect_clip(x, y, w, h):
        for sh in frame_shapes(pose, shot, prop):
            kind = sh[0]
            if kind == "line":
                _, x1, y1, x2, y2, lw, c = sh
                pdf.set_draw_color(*_rgb(COLORS[c]))
                pdf.set_line_width(lw * k)
                pdf.line(x + x1 * k, y + y1 * k, x + x2 * k, y + y2 * k)
            elif kind == "circle":
                _, cx, cy, r, lw, c, fill = sh
                pdf.set_fill_color(*_rgb(COLORS[fill]))
                pdf.set_draw_color(*_rgb(COLORS[c]))
                pdf.set_line_width(max(lw, 0.01) * k)
                pdf.circle(x + cx * k, y + cy * k, r * k, style="DF" if lw else "F")  # fpdf2 places circles by centre
            elif kind == "poly":
                _, points, lw, c, fill, closed = sh
                pdf.set_draw_color(*_rgb(COLORS[c]))
                pdf.set_line_width(lw * k)
                pts = [(x + px * k, y + py * k) for px, py in points]
                if fill:
                    pdf.set_fill_color(*_rgb(COLORS[fill]))
                    pdf.polygon(pts, style="DF")
                else:
                    pdf.polyline(pts, polygon=closed)
            elif kind == "rect":
                _, rx, ry, rw, rh, lw, c, fill, r = sh
                pdf.set_fill_color(*_rgb(COLORS[fill]))
                pdf.set_draw_color(*_rgb(COLORS[c]))
                pdf.set_line_width(lw * k)
                pdf.rect(x + rx * k, y + ry * k, rw * k, rh * k, style="DF", round_corners=True, corner_radius=r * k)
            elif kind == "text":
                _, tx, ty, size, txt, c, _anchor = sh
                pdf.set_text_color(*_rgb(COLORS[c]))
                pdf.set_font("Helvetica", "B", size * k * 2.835)
                tw = pdf.get_string_width(txt)
                pdf.text(x + tx * k - tw / 2, y + ty * k, txt)
    pdf.set_text_color(0, 0, 0)
    return h
