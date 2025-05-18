from flask import Flask, render_template, make_response, url_for
from playwright.sync_api import sync_playwright
import base64, datetime, os

app = Flask(__name__, static_folder="static", static_url_path="/static")

# — 1) load your real data here…
company = {
    "company_name": "Acme GmbH",
    "company_bg": "bg.png",
    "company_logo": "logo.png",
    "custom_design_enabled": False,
    "custom_css_offer": None,
}
product = {
    "product_name": "SuperWidget 3000",
    "product_description": "Das allerbeste Widget …",
    "product_img": "product.png",
}
creation_date = datetime.datetime.now().strftime("%d.%m.%Y")
base_price = 1234.00
total_price = 2345.00
areas = [
    {
        "area_name": "Modul A",
        "area_img": "modul_a.png",
        "area_description": "Beschreibung zu Modul A",
        "groups": [
            {
                "group_name": "Option 1",
                "group_description": "Premium Variante",
                "selected_option": {
                    "option_name": "Premium",
                    "option_description": "…",
                    "option_img": "prem.png",
                },
                "selected_price": 500.00,
            },
            {
                "group_name": "Option 2",
                "group_description": "Standard Variante",
                "selected_option": {
                    "option_name": "Standard",
                    "option_description": "…",
                    "option_img": "stand.png",
                },
                "selected_price": 300.00,
            },
            {
                "group_name": "Option 3",
                "group_description": "Basic Variante",
                "selected_option": {
                    "option_name": "Basic",
                    "option_description": "…",
                    "option_img": "basic.png",
                },
                "selected_price": 100.00,
            },
        ],
    },
    {
        "area_name": "Modul B",
        "area_img": "modul_b.png",
        "area_description": "Beschreibung zu Modul B",
        "groups": [
            {
                "group_name": "Option 1",
                "group_description": "Premium Variante",
                "selected_option": {
                    "option_name": "Premium",
                    "option_description": "…",
                    "option_img": "prem.png",
                },
                "selected_price": 500.00,
            },
            {
                "group_name": "Option 2",
                "group_description": "Standard Variante",
                "selected_option": {
                    "option_name": "Standard",
                    "option_description": "…",
                    "option_img": "stand.png",
                },
                "selected_price": 300.00,
            },
            {
                "group_name": "Option 3",
                "group_description": "Basic Variante",
                "selected_option": {
                    "option_name": "Basic",
                    "option_description": "…",
                    "option_img": "basic.png",
                },
                "selected_price": 100.00,
            },
        ],
    },
]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/offer_html/", defaults={"offer_id": 1})
@app.route("/offer_html/<int:offer_id>")
def offer_html(offer_id):
    # render just the content (cover, overview, summary, areas)
    return render_template(
        "content.html",
        company=company,
        product=product,
        creation_date=creation_date,
        base_price=base_price,
        total_price=total_price,
        areas=areas,
    )


@app.route("/offer/", defaults={"offer_id": 1})
@app.route("/offer/<int:offer_id>")
def offer_pdf(offer_id=1):

    # — 2) Render JUST the content (no TOC) into a string —
    content_html = render_template(
        "content.html",
        company=company,
        product=product,
        creation_date=creation_date,
        base_price=base_price,
        total_price=total_price,
        areas=areas,
    )

    # — 3) Launch Playwright, load content-html to measure positions —
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()

        # embed base64-logo for header
        logo_path = os.path.join(app.static_folder, "img", "logo.png")
        logo_b64 = base64.b64encode(open(logo_path, "rb").read()).decode()

        # load the content-only HTML
        page.set_content(content_html, wait_until="networkidle")
        # emulate A4 dimensions (at 96dpi)
        page.set_viewport_size({"width": 794, "height": 1122})

        # compute page-height in px
        page_height = 1122

        # find each section’s offset, compute page = floor(offsetY/page_height)+1
        positions = page.evaluate(
            f"""
            () => {{
              const secs = Array.from(document.querySelectorAll('section[id]'));
              const result = {{}};
              secs.forEach(s => {{
                const rect = s.getBoundingClientRect();
                // rect.top relative to viewport; plus scrollY to get absolute
                const y = rect.top + window.scrollY;
                result[s.id] = Math.floor(y / {page_height}) + 1;
              }});
              return result;
            }}
        """
        )
        browser.close()

    # — 4) Build your TOC list with computed pages —
    toc = [
        {"id": "coverPage", "title": "Deckblatt", "page": positions["coverPage"]},
        {
            "id": "productOverview",
            "title": "Preisübersicht",
            "page": positions["productOverview"],
        },
        {
            "id": "summaryTable",
            "title": "Preistabelle",
            "page": positions["summaryTable"],
        },
    ] + [
        {"id": f"area_{i+1}", "title": a["area_name"], "page": positions[f"area_{i+1}"]}
        for i, a in enumerate(areas)
    ]

    # — 5) Render the *full* HTML including the TOC —
    full_html = render_template(
        "offer.html",
        toc=toc,
        content_html=content_html,
        company=company,
        product=product,
        creation_date=creation_date,
        base_price=base_price,
        total_price=total_price,
        areas=areas,
    )

    # — 6) Finally generate the PDF with header/footer —
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()

        # load the fully rendered HTML (TOC + sections) all at once
        page.set_content(full_html, wait_until="networkidle")
        pdf_bytes = page.pdf(
            format="A4",
            display_header_footer=True,
            print_background=True,
            margin={"top": "100px", "bottom": "80px", "left": "40px", "right": "40px"},
            header_template=f"""
              <style>
              /* force background-colors in print */
                * {{
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
                }}
                .h{{width:100%;padding:0 40px;}}
                .logo{{float:right;height:40px;}}
              </style>
              <div class="h">
                <img src="data:image/png;base64,{logo_b64}" class="logo"/>
              </div>
            """,
            footer_template=f"""
                <style>
                /* force background-colors in print */
                * {{
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
                }}
                .footer {{
                    position: absolute;
                    bottom: 10px;
                    left: 40px;    /* ← page.pdf left margin */
                    right: 40px;   /* ← page.pdf right margin */
                    height: 80px;
                    font-family: sans-serif;
                    font-size: 9px;
                    color: #555;
                }}
                .footer-line {{
                    position: absolute;
                    top: 40px;
                    left: 0;
                    right: 40px;
                    height: 1px;
                    background: #d31f2d;
                }}
                .footer-vertical {{
                    position: absolute;
                    top: 0;
                    right: 39px;
                    width: 1px;
                    height: 79px;
                    background: #d31f2d;
                }}
                .doc-id {{
                    position: absolute;
                    top: 20px;
                    right: 60px;
                }}
                .footer-date {{
                    position: absolute;
                    top: 52px;
                    right: 60px;
                }}
                .page-box {{
                    position: absolute;
                    bottom: 0;
                    right: 0;
                    width: 40px;
                    height: 40px;
                    background: #d31f2d;
                    color: #fff;
                    font-size: 14px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                </style>
                <div class="footer">
                <div class="footer-line"></div>
                <div class="footer-vertical"></div>
                <div class="doc-id">QU-2932</div>
                <div class="footer-date">{datetime.datetime.now():%d.%m.%Y}</div>
                <div class="page-box"><span class="pageNumber"></span></div>
                </div>
                """,
        )
        browser.close()

    # 7) Stream inline
    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = "inline; filename=offer_{}.pdf".format(
        offer_id
    )
    return resp


if __name__ == "__main__":
    app.run(debug=True)
