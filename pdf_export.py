"""Build the downloadable content-plan PDF (idea, script and stick-figure storyboard)."""
from datetime import date

from fpdf import FPDF

import stickfigure as sf

INK = (31, 35, 40)
MUTED = (110, 116, 124)
ACCENT = (228, 87, 46)
SOFT = (244, 245, 246)
LINE = (222, 225, 229)

REPLACEMENTS = {"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                "…": "...", "₹": "Rs. ", "•": "-", " ": " "}


def latin1(text):
    """Make text safe for the PDF's built-in fonts."""
    text = str(text or "")
    for a, b in REPLACEMENTS.items():
        text = text.replace(a, b)
    return text.encode("latin-1", "replace").decode("latin-1")


def timecode(start, length):
    def fmt(t):
        return f"{t // 60}:{t % 60:02d}"
    return f"{fmt(start)}-{fmt(start + length)}"


class PlanPDF(FPDF):
    def __init__(self, title):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.plan_title = latin1(title)
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(True, margin=18)

    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*ACCENT)
        self.cell(0, 6, "REELMAP", new_x="LMARGIN", new_y="TOP")
        self.set_text_color(*MUTED)
        self.set_font("Helvetica", "", 9)
        self.cell(0, 6, f"Content plan  |  {date.today().strftime('%d %b %Y')}", align="R",
                  new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*LINE)
        self.set_line_width(0.3)
        self.line(15, self.get_y() + 1, 195, self.get_y() + 1)
        self.ln(5)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, f"{self.plan_title[:80]}  |  Page {self.page_no()}/{{nb}}", align="C")


def _label(pdf, text):
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, text.upper(), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)


def build_pdf(project, idea, frames):
    """Return the PDF as bytes."""
    pdf = PlanPDF(idea["title"])
    pdf.alias_nb_pages()
    pdf.add_page()

    # Title and hook
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 9, latin1(idea["title"]), align="L", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_fill_color(*SOFT)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*ACCENT)
    pdf.cell(0, 7, "  HOOK  (FIRST 3 SECONDS)", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 7, latin1(f'"{idea["hook"]}"'), fill=True, align="L", padding=(1, 3, 3, 3), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, latin1(idea["description"]), align="L", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Details table
    total = sum(f["duration_sec"] for f in frames)
    details = [("Topic", project["topic"]), ("Niche", project["niche"]), ("Format", project["format_name"]),
               ("Platform", project["platform"]), ("Audience", project["target_audience"]),
               ("Length", f"About {total} seconds, {len(frames)} scenes, vertical 9:16")]
    _label(pdf, "Video details")
    pdf.set_draw_color(*LINE)
    for k, v in details:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(35, 7, k, border="B")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, latin1(v), border="B", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Checklist
    props = sorted({sf.PROPS[f["prop"]] for f in frames if f["prop"] != "none"})
    shots = sorted({sf.SHOTS[f["shot_type"]] for f in frames})
    checklist = ["Film vertically (9:16) with good light facing you.",
                 f"Shots needed: {', '.join(shots)}.",
                 f"Props: {', '.join(props) if props else 'none needed'}.",
                 "Say the hook in the first 3 seconds.",
                 "Add the on-screen text from each scene as captions."]
    _label(pdf, "Before you film")
    pdf.set_font("Helvetica", "", 10)
    for item in checklist:
        pdf.set_draw_color(*INK)
        pdf.rect(16, pdf.get_y() + 1.6, 3, 3)
        pdf.set_x(22)
        pdf.multi_cell(0, 6, latin1(item), align="L", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Script
    _label(pdf, "Script")
    t = 0
    for f in frames:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*ACCENT)
        pdf.cell(28, 6, f"{f['frame_no']}.  {timecode(t, f['duration_sec'])}")
        pdf.set_text_color(*INK)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, latin1(f["dialogue"] or "(no dialogue)"), align="L", new_x="LMARGIN", new_y="NEXT")
        t += f["duration_sec"]

    # Storyboard pages: 3 columns x 2 rows
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 8, "Storyboard", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, "Stick figures show the pose, shot size and props for each scene.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_auto_page_break(False)  # the grid controls its own page breaks
    col_w, gap, draw_w = 56, 6, 38
    row_h = 122
    t = 0
    for idx, f in enumerate(frames):
        slot = idx % 6
        if idx and slot == 0:
            pdf.add_page()
        col, row = slot % 3, slot // 3
        top = (42 if idx < 6 else 28) + row * row_h
        left = 15 + col * (col_w + gap)
        fx = left + (col_w - draw_w) / 2
        # frame background + drawing
        pdf.set_fill_color(*SOFT)
        fh = draw_w * sf.FRAME_H / sf.FRAME_W
        pdf.set_draw_color(*LINE)
        pdf.set_line_width(0.3)
        pdf.rect(fx, top, draw_w, fh, style="DF", round_corners=True, corner_radius=2.5)
        sf.draw_pdf(pdf, fx, top, draw_w, f["pose"], f["shot_type"], f["prop"])
        # on-screen text overlay
        if f["on_screen_text"]:
            pdf.set_font("Helvetica", "B", 7.5)
            lines = pdf.multi_cell(draw_w - 8, 3.6, latin1(f["on_screen_text"]), dry_run=True, output="LINES")[:3]
            box_h = 2.4 + 3.6 * len(lines)
            pdf.set_fill_color(*INK)
            pdf.rect(fx + 3, top + 3, draw_w - 6, box_h, style="F", round_corners=True, corner_radius=1.5)
            pdf.set_text_color(255, 255, 255)
            pdf.set_xy(fx + 4, top + 4.2)
            pdf.multi_cell(draw_w - 8, 3.6, "\n".join(lines), align="C")
        # timecode
        pdf.set_font("Helvetica", "B", 6.5)
        pdf.set_fill_color(255, 255, 255)
        tc = timecode(t, f["duration_sec"])
        pdf.set_text_color(*INK)
        pdf.set_xy(fx + 2, top + fh - 6)
        pdf.cell(pdf.get_string_width(tc) + 3, 4, tc, fill=True, align="C")
        # text under the frame
        pdf.set_xy(left, top + fh + 2.5)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*ACCENT)
        pdf.cell(col_w, 5, f"Scene {f['frame_no']}  |  {sf.SHOTS[f['shot_type']]}", new_x="LEFT", new_y="NEXT")
        pdf.set_text_color(*INK)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.multi_cell(col_w, 4.2, latin1(f["action_text"]), align="L", new_x="LEFT", new_y="NEXT")
        if f["dialogue"]:
            pdf.set_font("Helvetica", "I", 8.5)
            pdf.set_text_color(*MUTED)
            pdf.multi_cell(col_w, 4.2, latin1(f'"{f["dialogue"]}"'), align="L", new_x="LEFT", new_y="NEXT")
        pdf.set_text_color(*INK)
        t += f["duration_sec"]
    return bytes(pdf.output())
