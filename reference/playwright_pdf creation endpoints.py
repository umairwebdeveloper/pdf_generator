# ──────────────────────────────────────────────────────────────────────────────
# PDF CREATION
# ──────────────────────────────────────────────────────────────────────────────

def _html_to_pdf(html: str, base_url: str | None = None) -> bytes:                           
    """Render *html* with headless Chromium & return the PDF bytes with background support."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Inject <base> tag to handle relative paths
        if base_url:
            base_tag = f'<base href="{base_url}">'
            html = html.replace("<head>", f"<head>{base_tag}")

        # Set content and wait for background image to load
        page.set_content(html, wait_until="networkidle")
        page.wait_for_load_state("networkidle")  # Ensure all network requests are complete

        # Generate PDF with background printing enabled
        pdf = page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"}
        )

        browser.close()
        return pdf





def _build_offer_data(link: CustomerLink,
                      cfg: Configuration) -> dict:
    """
    Produces exactly the data structure that the old
    `/offer_website` template expected (areas, prices …).
    """
    product = cfg.product
    company = product.company
    creation_date = cfg.created_at.strftime("%d.%m.%Y")

    # base price (frozen snapshot if possible)
    if cfg.product_price_snapshot is not None:
        base_price = cfg.product_price_snapshot
    else:
        base_price, _ = get_display_prices(product, link.price_list_id)

    total_price = base_price
    sel_map     = {s.group_id: s for s in cfg.selections}

    areas = []
    for area in sorted(product.areas, key=lambda a: a.order_index or 0):
        groups = []
        for g in sorted(area.groups, key=lambda g: g.order_index or 0):
            snap = sel_map.get(g.id)

            if snap:
                opt_price = snap.option_price_snapshot or 0
                total_price += opt_price
                selected_opt = {
                    "option_name":        snap.option_name_snapshot,
                    "option_description": snap.option_description_snapshot,
                    "option_img":         snap.option_img_snapshot,
                }
            else:
                opt_price    = 0
                selected_opt = None

            groups.append({
                "group_name":        g.group_name,
                "group_description": g.group_description,
                "selected_option":   selected_opt,
                "selected_price":    opt_price,
            })

        areas.append({
            "area_name":        area.area_name,
            "area_description": area.area_description,
            "area_img":         area.area_img,
            "groups":           groups,
        })

    return dict(
        product       = product,
        company       = company,
        creation_date = creation_date,
        areas         = areas,
        base_price    = base_price,
        total_price   = total_price,
    )


# ──────────────────────────────────────────────────────────────
# NEW public endpoint that replaces /offer_website
# ──────────────────────────────────────────────────────────────
@public.route("/offer_pdf", methods=["GET"])
def offer_pdf():
    """
    Public – no login required.
    Query-params: ?company=…&token=…&config_token=…
    Generates the same offer as `/offer_website` but returns a PDF.
    """
    company_id   = request.args.get("company", type=int)
    token        = request.args.get("token",          type=str)
    config_token = request.args.get("config_token",   type=str)

    if not all([company_id, token, config_token]):
        return "Missing ?company, ?token or ?config_token.", 400

    link   = CustomerLink.query.filter_by(
                 company_id=company_id, token=token).first_or_404()
    cfg    = Configuration.query.filter_by(
                 config_token=config_token).first_or_404()

    # cross-check that the link really belongs to this configuration
    if cfg.product.company_id != company_id:
        abort(403)

    ctx  = _build_offer_data(link, cfg)                       # build payload
    html = render_template("offer_template.html", **ctx)
    pdf  = _html_to_pdf(html, base_url=request.url_root)      # ← Playwright

    filename = f"Offer_{cfg.config_token}.pdf"
    resp = make_response(pdf)
    resp.headers["Content-Type"]        = "application/pdf"
    resp.headers["Content-Disposition"] = f"inline; filename={filename}"
    return resp