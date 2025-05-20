from flask import Flask, render_template, make_response, url_for
from playwright.sync_api import sync_playwright
import base64, datetime, os
from io import BytesIO
from PyPDF2 import PdfReader, PdfWriter

from flask import Flask, render_template, make_response
from playwright.sync_api import sync_playwright
import datetime, os, base64

app = Flask(__name__, static_folder="static", static_url_path="/static")

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


def _img_to_data_uri(name):
    path = os.path.join(app.static_folder, "img", name)
    ext = os.path.splitext(name)[1].lstrip(".")
    data = base64.b64encode(open(path, "rb").read()).decode()
    return f"data:image/{ext};base64,{data}"


@app.route("/", defaults={"offer_id": 1})
@app.route("/<int:offer_id>")
def offer_pdf(offer_id):
    # compute data URIs here
    COMPANY["logo"] = _img_to_data_uri("logo.png")
    COMPANY["cover_photo"] = _img_to_data_uri("cover.jpg")
    
    # 1) Render the full HTML (TOC + all your sections)
    full_html = render_template("offer.html", company=COMPANY, toc=TOC)

    # 2) Generate a single PDF (preserves links)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()

        page.set_content(full_html, wait_until="networkidle")
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            display_header_footer=True,
            margin={"top": "100px", "bottom": "80px", "left": "60px", "right": "60px"},
            header_template=f"""
              <style>
                *{{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}}
                .h{{width:100%;padding:0 20px;}}
                .logo{{float:right;height:60px;}}
              </style>
              <div class="h">
                <img src="{COMPANY['logo']}" class="logo"/>
              </div>
            """,
            footer_template=f"""
              <style>
                *{{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}}
                .footer{{position:absolute;bottom:10px;left:20px;right:20px;height:80px;
                         font-family:sans-serif;font-size:9px;color:#555}}
                .footer-line{{position:absolute;top:40px;left:0;right:40px;height:1px;background:#d31f2d}}
                .footer-vertical{{position:absolute;top:0;right:39px;width:1px;height:79px;background:#d31f2d}}
                .doc-id{{position:absolute;top:23px;right:60px}}
                .footer-date{{position:absolute;top:49px;right:60px}}
                .page-box{{position:absolute;bottom:0;right:0;width:40px;height:40px;
                           background:#d31f2d;color:#fff;font-size:14px;
                           display:flex;align-items:center;justify-content:center}}
              </style>
              <div class="footer">
                <div class="footer-line"></div>
                <div class="footer-vertical"></div>
                <div class="doc-id">{COMPANY['doc_id']}</div>
                <div class="footer-date">{datetime.datetime.now():%d.%m.%Y}</div>
                <div class="page-box"><span class="pageNumber"></span></div>
              </div>
            """,
        )
        browser.close()

    # 3) Send inline
    resp = make_response(pdf_bytes)
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


# @app.route("/", defaults={"offer_id": 1})
# @app.route("/<int:offer_id>")
# def offer_pdf(offer_id=1):
#     COMPANY["logo"] = _img_to_data_uri("logo.png")
#     COMPANY["cover_photo"] = _img_to_data_uri("cover.jpg")
#     logo_path = os.path.join(app.static_folder, "img", "logo.png")
#     logo_b64 = base64.b64encode(open(logo_path, "rb").read()).decode()
#     with sync_playwright() as pw:
#         browser = pw.chromium.launch()
#         page = browser.new_page()

#         # emulate A4 dimensions (at 96dpi)
#         page.set_viewport_size({"width": 794, "height": 1122})
#         browser.close()

#     # — 5) Render the *full* HTML including the TOC —
#     full_html = render_template(
#         "offer.html",
#         company=COMPANY,
#         toc=TOC,
#     )

#     with sync_playwright() as pw:
#         browser = pw.chromium.launch()
#         page = browser.new_page()
#         page.set_content(full_html, wait_until="networkidle")
#         common_opts = dict(
#             format="A4",
#             print_background=True,
#             margin={"top": "100px", "bottom": "80px", "left": "60px", "right": "60px"},
#         )
#         pdf_page1 = page.pdf(
#             format="A4",
#             print_background=True,
#             margin={"top": "0px", "bottom": "0px", "left": "0px", "right": "0px"},
#             display_header_footer=False,
#             page_ranges="1",
#         )
#         header_tpl = f"""
#           <style>
#             *, *::before, *::after {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
#             .h      {{ width:100%; padding:0 20px; }}
#             .logo   {{ float:right; height:60px; }}
#           </style>
#           <div class="h">
#             <img src="data:image/png;base64,{logo_b64}" class="logo" />
#           </div>
#         """
#         footer_tpl = f"""
#           <style>
#             *, *::before, *::after {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
#             .footer          {{ position:absolute; bottom:10px; left:20px; right:20px; height:80px;
#                                   font-family:sans-serif; font-size:9px; color:#555; }}
#             .footer-line     {{ position:absolute; top:40px; left:0; right:40px; height:1px; background:#d31f2d; }}
#             .footer-vertical {{ position:absolute; top:0;  right:39px; width:1px; height:79px; background:#d31f2d; }}
#             .doc-id          {{ position:absolute; top:23px; right:60px; }}
#             .footer-date     {{ position:absolute; top:49px; right:60px; }}
#             .page-box        {{ position:absolute; bottom:0; right:0; width:40px; height:40px;
#                                   background:#d31f2d; color:#fff; font-size:14px;
#                                   display:flex; align-items:center; justify-content:center; }}
#           </style>
#           <div class="footer">
#             <div class="footer-line"></div>
#             <div class="footer-vertical"></div>
#             <div class="doc-id">QU-2932</div>
#             <div class="footer-date">{datetime.datetime.now():%d.%m.%Y}</div>
#             <div class="page-box"><span class="pageNumber"></span></div>
#           </div>
#         """
#         pdf_rest = page.pdf(
#             **common_opts,
#             display_header_footer=True,
#             header_template=header_tpl,
#             footer_template=footer_tpl,
#             page_ranges="2-",
#         )

#         browser.close()

#     reader1 = PdfReader(BytesIO(pdf_page1))
#     reader2 = PdfReader(BytesIO(pdf_rest))
#     writer = PdfWriter()

#     for p in reader1.pages:
#         writer.add_page(p)
#     for p in reader2.pages:
#         writer.add_page(p)

#     merged_stream = BytesIO()
#     writer.write(merged_stream)
#     pdf_bytes = merged_stream.getvalue()

#     resp = make_response(pdf_bytes)
#     resp.headers["Content-Type"] = "application/pdf"
#     resp.headers["Content-Disposition"] = f"inline; filename=offer_{offer_id}.pdf"
#     return resp


if __name__ == "__main__":
    app.run(debug=True)
