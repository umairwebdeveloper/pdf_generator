from flask import Flask, render_template, make_response, url_for
from playwright.sync_api import sync_playwright
import base64, datetime, os
from io import BytesIO
from PyPDF2 import PdfReader, PdfWriter

from flask import Flask, render_template, make_response
from playwright.sync_api import sync_playwright
import datetime, os, base64

app = Flask(__name__, static_folder="static", static_url_path="/static")

MARGIN_TOP = 100
MARGIN_BOTTOM = 80
MARGIN_LEFT = 60
MARGIN_RIGHT = 60

PAGE_HEIGHT = 1122  # A4 height in px at 96dpi
PAGE_WIDTH = 794  # A4 width in px at 96dpi

# your company info
COMPANY = {
    "name": "torebest GmbH & Co. KG",
    "tagline": "Zuführen, Sägen und Entgraten",
    "doc_id": "QU-29352",
    "date": "09.10.20",
    "cover_photo": None,  # set below
    "logo": None,
}

# your static TOC entries—make sure the `id` values match your <section id="…">s
TOC = [
    {"id": "coverPage", "title": "Deckblatt", "page": 1},
    {
        "id": "project-responsibles",
        "title": "Unsere Projekt-verantwort-lichen im Außen- und Innendienst",
        "page": 2,
    },
    {"id": "bundloader-section", "title": "1. Bundlader – RASALOAD", "page": 3},
    {"id": "zusatz-section", "title": "Zusatzausrüstung", "page": 4},
    {"id": "zusatz-img-section", "title": "Zusatzausrüstung (Bilder)", "page": 5},
    {
        "id": "rasacut-section",
        "title": "4. Hochleistungskreissäge – RASACUT SC",
        "page": 6,
    },
    {
        "id": "not-included-section",
        "title": "Nicht im Lieferumfang enthalten",
        "page": 7,
    },
    {"id": "delivery-terms", "title": "Lieferbedingungen", "page": 8},
]
# your static list of ids + titles
SECTIONS = [
    # ("coverPage", "Deckblatt"),
    # ("productOverview", "Preisübersicht"),
    # ("summaryTable", "Preistabelle"),
    ("project-responsibles", "Unsere Projektverantwortlichen"),
    ("bundloader-section", "1. Bundlader – RASALOAD"),
    ("zusatz-section", "Zusatzausrüstung"),
    ("zusatz-img-section", "Zusatzausrüstung (Bilder)"),
    ("rasacut-section", "4. Hochleistungskreissäge – RASACUT SC"),
    ("not-included-section", "Nicht im Lieferumfang enthalten"),
    ("delivery-terms", "Lieferbedingungen"),
]


def _img_to_data_uri(name):
    path = os.path.join(app.static_folder, "img", name)
    ext = os.path.splitext(name)[1].lstrip(".")
    data = base64.b64encode(open(path, "rb").read()).decode()
    return f"data:image/{ext};base64,{data}"


@app.route("/", defaults={"offer_id": 1})
@app.route("/<int:offer_id>")
def offer_pdf(offer_id):
    # inline images
    COMPANY["logo"] = _img_to_data_uri("logo.png")
    COMPANY["cover_photo"] = _img_to_data_uri("cover.jpg")

    # 1) render your content sections once
    content_html = render_template(
        "components/sections.html",
        company=COMPANY,
        # pass whatever that partial needs…
    )

    # 2) dummy TOC
    toc_dummy = [{"id": sid, "title": title, "page": 0} for sid, title in SECTIONS]

    # 3) skeleton HTML with dummy TOC
    html_skel = render_template(
        "offer.html", company=COMPANY, toc=toc_dummy, content_html=content_html
    )

    # 4) measure pages

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_viewport_size({"width": PAGE_WIDTH, "height": PAGE_HEIGHT})
        page.set_content(html_skel, wait_until="networkidle")
        content_height = PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM  # = 942

        positions = page.evaluate(
            f"""
            () => {{
              const secs = Array.from(document.querySelectorAll('section[id]'));
              const mTop = {MARGIN_TOP};
              const cH   = {content_height};

              // 1) map each section to its raw page + whether it forces a break
              let arr = secs.map(s => {{
                const y     = s.getBoundingClientRect().top + window.scrollY;
                const rawP  = Math.floor((y + mTop) / cH) + 1;
                const style = window.getComputedStyle(s);
                // detect either the old or the new break-after property
                const br    = style.pageBreakAfter || style.breakAfter;
                const force = (br === 'always');
                return {{ id: s.id, page: rawP, force }};
              }});
              // 2) apply forced breaks: if a section says "break-after", bump the next
              for (let i = 0; i < arr.length - 1; i++) {{
                if (arr[i].force && arr[i+1].page <= arr[i].page) {{
                  arr[i+1].page = arr[i].page + 1;
                }}
              }}
              // 3) reduce back to a simple id → page map
              return arr.reduce((map, e) => (map[e.id] = e.page, map), {{}}); 
                          
            }}
            """
        )
        browser.close()

    # 5) build real TOC
    toc = [
        {"id": sid, "title": title, "page": positions[sid]} for sid, title in SECTIONS
    ]

    # 6) final HTML with correct TOC
    html_final = render_template(
        "offer.html", company=COMPANY, toc=toc, content_html=content_html
    )

    # 7) single-shot PDF (links stay live)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_content(html_final, wait_until="networkidle")

        HEADER_TEMPLATE = f"""
                      <style>
                        *{{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}}
                        .h{{width:100%;padding:0 20px;}}
                        .logo{{float:right;height:60px;}}
                      </style>
                      <div class="h">
                        <img src="{COMPANY['logo']}" class="logo"/>
                      </div>
                      """
        FOOTER_TEMPLATE = f"""
                      <style>
                        *{{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}}
                        .footer{{position:absolute;bottom:10px;left:20px;right:20px;height:80px;
                                font-family:sans-serif;font-size:9px;color:#555}}
                        .footer-line{{position:absolute;top:40px;left:0;right:40px;height:1px;background:#d31f2d}}
                        .footer-vertical{{position:absolute;top:0;right:39px;width:1px;height:79px;background:#d31f2d}}
                        .doc-id{{position:absolute;top:20px;right:60px;font-size:12px;color:#666}}
                        .footer-date{{position:absolute;top:48px;right:60px;font-size:12px;color:#666}}
                        .page-box{{position:absolute;bottom:0;right:0;width:40px;height:40px;
                                  background:#d31f2d;color:#fff;font-size:14px;
                                  display:flex;align-items:center;justify-content:center}}
                        .pageNumber{{font-size:16px;}}
                        
                      </style>
                      <div class="footer">
                        <div class="footer-line"></div>
                        <div class="footer-vertical"></div>
                        <div class="doc-id">{COMPANY['doc_id']}</div>
                        <div class="footer-date">{datetime.datetime.now():%d.%m.%Y}</div>
                        <div class="page-box"><span class="pageNumber"></span></div>
                      </div>
        """
        pdf = page.pdf(
            format="A4",
            print_background=True,
            display_header_footer=True,
            margin={
                "top": f"{MARGIN_TOP}px",
                "bottom": f"{MARGIN_BOTTOM}px",
                "left": f"{MARGIN_LEFT}px",
                "right": f"{MARGIN_RIGHT}px",
            },
            header_template=HEADER_TEMPLATE,
            footer_template=FOOTER_TEMPLATE,
        )
        browser.close()

    # 8) return inline
    resp = make_response(pdf)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'inline; filename="offer_{offer_id}.pdf"'
    return resp


@app.route("/offer_html/", defaults={"offer_id": 1})
@app.route("/offer_html/<int:offer_id>")
def offer_html(offer_id):
    # render just the content (cover, overview, summary, areas)
    return render_template(
        "offer.html",
    )


if __name__ == "__main__":
    app.run(debug=True)
