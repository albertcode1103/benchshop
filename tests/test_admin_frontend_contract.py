import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADMIN_JS = (PROJECT_ROOT / "admin" / "admin.js").read_text(encoding="utf-8")
ADMIN_CATALOG_V2 = (PROJECT_ROOT / "admin" / "catalog-v2.js").read_text(encoding="utf-8")
ADMIN_HTML = (PROJECT_ROOT / "admin" / "index.html").read_text(encoding="utf-8")
ADMIN_CSS = (PROJECT_ROOT / "admin" / "admin.css").read_text(encoding="utf-8")
CUSTOMER_HTML = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
CUSTOMER_RENDERER = (PROJECT_ROOT / "js" / "renderer.js").read_text(encoding="utf-8")
CUSTOMER_CART = (PROJECT_ROOT / "js" / "cart.js").read_text(encoding="utf-8")
CUSTOMER_SCROLL_RESET = (PROJECT_ROOT / "js" / "scroll-reset.js").read_text(encoding="utf-8")
CUSTOMER_LANGUAGE = (PROJECT_ROOT / "js" / "language.js").read_text(encoding="utf-8")
CUSTOMER_MARKETPLACE = (PROJECT_ROOT / "js" / "catalog-marketplace.js").read_text(encoding="utf-8")
CUSTOMER_NAVIGATION_DRAWER = (PROJECT_ROOT / "js" / "navigation-drawer.js").read_text(encoding="utf-8")
CUSTOMER_SHARE_VIEWER = (PROJECT_ROOT / "js" / "share-viewer.js").read_text(encoding="utf-8")
CUSTOMER_LAYOUT_CSS = (PROJECT_ROOT / "css" / "layout.css").read_text(encoding="utf-8")
CUSTOMER_COMPONENTS_CSS = (PROJECT_ROOT / "css" / "components.css").read_text(encoding="utf-8")
ACCOUNT_HTML = (PROJECT_ROOT / "account" / "index.html").read_text(encoding="utf-8")
ACCOUNT_JS = (PROJECT_ROOT / "account" / "account.js").read_text(encoding="utf-8")
ACCOUNT_CSS = (PROJECT_ROOT / "account" / "account.css").read_text(encoding="utf-8")


class AdminFrontendContractTests(unittest.TestCase):
    def test_product_navigation_uses_a_two_level_accessible_drawer(self) -> None:
        self.assertIn('id="catalog-drawer-toggle"', CUSTOMER_HTML)
        self.assertIn('id="catalog-navigation-drawer"', CUSTOMER_HTML)
        self.assertIn('id="catalog-model-drawer"', CUSTOMER_HTML)
        self.assertIn('id="device-select" hidden', CUSTOMER_HTML)
        self.assertIn('data-catalog-drawer-select="catalog:tools"', CUSTOMER_HTML)
        self.assertIn('data-catalog-drawer-select="catalog:accessories"', CUSTOMER_HTML)
        self.assertIn("function renderModels()", CUSTOMER_NAVIGATION_DRAWER)
        self.assertIn('models.filter((model) => model.enabled !== false)', CUSTOMER_NAVIGATION_DRAWER)
        self.assertIn('select.dispatchEvent(new Event("change", { bubbles: true }))', CUSTOMER_NAVIGATION_DRAWER)
        self.assertIn('event.key === "Escape"', CUSTOMER_NAVIGATION_DRAWER)
        self.assertIn('.catalog-navigation-drawer', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('.catalog-model-drawer', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('visibility: hidden; pointer-events: none;', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('transform: translateX(-200%);', CUSTOMER_COMPONENTS_CSS)

    def test_signed_in_account_actions_use_an_accessible_anchored_menu(self) -> None:
        self.assertIn('id="account-menu"', CUSTOMER_HTML)
        self.assertIn('id="account-profile-entry" role="menuitem"', CUSTOMER_HTML)
        self.assertIn('id="account-share-entry" role="menuitem"', CUSTOMER_HTML)
        self.assertIn('id="account-logout" class="account-menu-logout" role="menuitem"', CUSTOMER_HTML)
        self.assertIn('.account-menu-anchor { position: relative; }', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('event.key === "Escape"', (PROJECT_ROOT / "js" / "auth.js").read_text(encoding="utf-8"))

    def test_profile_is_a_separate_hierarchical_page(self) -> None:
        self.assertIn('data-account-panel="profile"', ACCOUNT_HTML)
        self.assertIn('data-account-panel="account-contact"', ACCOUNT_HTML)
        self.assertIn('data-account-panel="account-security"', ACCOUNT_HTML)
        self.assertIn('/auth/profile/details', ACCOUNT_JS)
        self.assertIn('/auth/profile/contact', ACCOUNT_JS)
        self.assertIn('/auth/change-password', ACCOUNT_JS)
        self.assertIn('window.BOTEN_API_BASE || ""', ACCOUNT_JS)
        self.assertIn('error?.status === 401 || error?.code === "ACCOUNT_SESSION_EXPIRED"', ACCOUNT_JS)
        self.assertIn('id="profile-load-error"', ACCOUNT_HTML)
        self.assertIn('data-account-panel="my-shares"', ACCOUNT_HTML)
        self.assertIn('data-account-panel="my-quotes"', ACCOUNT_HTML)
        self.assertIn('/customer/me/shares?page=', ACCOUNT_JS)
        self.assertIn('/customer/me/quotes', ACCOUNT_JS)
        self.assertIn('data-download-quote', ACCOUNT_JS)
        self.assertIn('grid-template-columns: 240px minmax(0, 760px)', ACCOUNT_CSS)

    def test_customer_share_viewer_marks_unavailable_items_and_imports_safely(self) -> None:
        self.assertIn('id="customer-share-dialog"', CUSTOMER_HTML)
        self.assertIn('/customer/shares/${code}?lang=${lang}', CUSTOMER_SHARE_VIEWER)
        self.assertIn('/import', CUSTOMER_SHARE_VIEWER)
        self.assertIn('item.available', CUSTOMER_SHARE_VIEWER)
        self.assertIn('idempotency_key: customerShareImportKey', CUSTOMER_SHARE_VIEWER)

    def test_optional_configuration_grid_stays_two_columns_at_all_widths(self) -> None:
        self.assertGreaterEqual(
            CUSTOMER_COMPONENTS_CSS.count(
                'grid-template-columns: repeat(2, minmax(0, 1fr));'
            ),
            2,
        )

    def test_page_reload_resets_scroll_without_overriding_history_navigation(self) -> None:
        self.assertIn('js/scroll-reset.js', CUSTOMER_HTML)
        self.assertIn('navigation?.type !== "reload"', CUSTOMER_SCROLL_RESET)
        self.assertIn('window.history.scrollRestoration = "manual"', CUSTOMER_SCROLL_RESET)
        self.assertIn('window.addEventListener("pagehide"', CUSTOMER_SCROLL_RESET)
        self.assertIn('window.history.scrollRestoration = previousScrollRestoration', CUSTOMER_SCROLL_RESET)
        self.assertIn('window.addEventListener("pageshow"', CUSTOMER_SCROLL_RESET)
        customer_main = (PROJECT_ROOT / "js" / "main.js").read_text(encoding="utf-8")
        self.assertIn('requestAnimationFrame(window.botenResetReloadScroll)', customer_main)

    def test_sales_can_open_catalog_navigation(self) -> None:
        self.assertIn('data-view="products" type="button"', ADMIN_HTML)
        self.assertIn('data-view="config-catalog" type="button"', ADMIN_HTML)
        self.assertIn('data-view="tool-catalog" type="button"', ADMIN_HTML)
        self.assertIn('data-view="accessory-catalog" type="button"', ADMIN_HTML)
        self.assertNotIn('data-view="products" data-admin-only', ADMIN_HTML)
        self.assertNotIn('data-view="config-catalog" data-admin-only', ADMIN_HTML)
        self.assertNotIn('data-view="tool-catalog" data-admin-only', ADMIN_HTML)
        self.assertNotIn('data-view="accessory-catalog" data-admin-only', ADMIN_HTML)
        self.assertNotIn('state.products = [];\n      state.users = [];\n      state.configCatalog = [];', ADMIN_JS)

    def test_catalog_roots_use_separate_sidebar_routes(self) -> None:
        self.assertIn('"tool-catalog": { rootId: "catalog-tools"', ADMIN_JS)
        self.assertIn('"accessory-catalog": { rootId: "catalog-accessories"', ADMIN_JS)
        self.assertIn('window.selectCatalogRootFromNavigation?.(catalogView.rootId)', ADMIN_JS)
        self.assertIn('window.selectCatalogRootFromNavigation = function', ADMIN_CATALOG_V2)
        self.assertNotIn('class="catalog-root-tabs"', ADMIN_CATALOG_V2)
        self.assertNotIn('class="catalog-root-toolbar"', ADMIN_CATALOG_V2)
        self.assertIn('class="catalog-flat-list"', ADMIN_CATALOG_V2)
        self.assertIn('catalogAction.textContent = catalogView.rootId === "catalog-tools" ? "添加工具" : "添加附件"', ADMIN_JS)

    def test_catalog_prices_keep_table_layout_and_align_currency_tracks(self) -> None:
        self.assertIn('class="catalog-price-values"', ADMIN_CATALOG_V2)
        self.assertIn('class="catalog-currency-mark"', ADMIN_CATALOG_V2)
        self.assertIn('.catalog-price-values > span', ADMIN_CSS)
        self.assertIn('font-variant-numeric: tabular-nums', ADMIN_CSS)
        self.assertNotIn('.catalog-price-cell { display: grid;', ADMIN_CSS)

    def test_catalog_collapse_state_survives_language_rerender(self) -> None:
        self.assertIn('const content = $(".catalog-group-content", group);', ADMIN_JS)
        self.assertIn('if (content) content.hidden = collapsed;', ADMIN_JS)
        self.assertIn('group.dataset.catalogCategory', ADMIN_JS)
        self.assertIn('target.tagName !== "BUTTON"', ADMIN_JS)

    def test_admin_initial_load_is_independently_fault_tolerant(self) -> None:
        self.assertIn('Promise.allSettled(Object.values(requests))', ADMIN_JS)
        self.assertIn('部分数据加载失败', ADMIN_JS)
        self.assertIn('[502, 503, 504].includes(failure.status)', ADMIN_JS)

    def test_product_editor_uses_atomic_save_endpoint(self) -> None:
        self.assertIn('catalog-v2.js', ADMIN_HTML)
        self.assertIn('/api/v1/admin/products/${encodeURIComponent(product.id)}/editor', ADMIN_CATALOG_V2)
        self.assertIn('base_option_groups:', ADMIN_CATALOG_V2)
        self.assertIn('price_variants:', ADMIN_CATALOG_V2)
        self.assertIn('optional_config_ids:', ADMIN_CATALOG_V2)
        self.assertIn('translation_status: product.translation_status', ADMIN_CATALOG_V2)

    def test_quote_and_share_pdf_downloads_use_dom_links(self) -> None:
        self.assertIn('await exportQuote(savedQuote)', ADMIN_JS)
        self.assertIn('document.body.appendChild(link);', ADMIN_JS)
        self.assertNotIn('printWindow.document.write', ADMIN_JS)

    def test_admin_share_drawer_traps_focus_and_restores_background(self) -> None:
        self.assertIn('shareDrawerElement.setAttribute("role", "dialog")', ADMIN_JS)
        self.assertIn('shareDrawerElement.setAttribute("aria-hidden", "true")', ADMIN_JS)
        self.assertIn('shareDrawerElement.setAttribute("aria-hidden", "false")', ADMIN_JS)
        self.assertIn('if (app) app.inert = true', ADMIN_JS)
        self.assertIn('if (app) app.inert = false', ADMIN_JS)
        self.assertIn('event.key === "Escape"', ADMIN_JS)
        self.assertIn('previousShareFocus.focus()', ADMIN_JS)

    def test_quote_prefill_uses_selected_motor_snapshot_price(self) -> None:
        self.assertIn('const cnyPricing = pricing.CNY || {}', ADMIN_JS)
        self.assertIn('const usdPricing = pricing.USD || {}', ADMIN_JS)
        self.assertIn('price_cny: baseCny', ADMIN_JS)
        self.assertIn('price_usd: baseUsd', ADMIN_JS)
        self.assertIn('const snapshotPrice = selectedCurrency === "USD"', ADMIN_JS)

    def test_toast_is_promoted_above_open_dialogs(self) -> None:
        self.assertIn('document.querySelectorAll("dialog[open]")', ADMIN_JS)
        self.assertIn('host.appendChild(toast)', ADMIN_JS)

    def test_auth_ui_uses_country_selected_phone_inputs(self) -> None:
        customer_html = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
        customer_auth = (PROJECT_ROOT / "js" / "auth.js").read_text(encoding="utf-8")
        self.assertIn('data-auth-identifier="email"', customer_html)
        self.assertIn('id="auth-country"', customer_html)
        self.assertIn('id="auth-calling-code"', customer_html)
        self.assertIn('id="auth-phone"', customer_html)
        self.assertIn('id="auth-name"', customer_html)
        self.assertIn('register-only', customer_html)
        self.assertIn('phone_country: authPhone().country', customer_auth)
        self.assertIn('localStorage.getItem("boten-language") === "en" ? "email" : "phone"', customer_auth)
        self.assertIn('isRegister ? isEnglish : isEmail', customer_auth)
        self.assertIn('email: document.getElementById("auth-email").value.trim().toLowerCase() || null', customer_auth)

    def test_auth_failure_releases_submit_and_uses_structured_translation(self) -> None:
        customer_auth = (PROJECT_ROOT / "js" / "auth.js").read_text(encoding="utf-8")
        self.assertIn('let authSubmitting = false', customer_auth)
        self.assertIn('submit.setAttribute("aria-busy", "true")', customer_auth)
        self.assertIn('submit.removeAttribute("aria-busy")', customer_auth)
        self.assertIn('authSubmitting = false', customer_auth)
        self.assertIn('ACCOUNT_CREDENTIALS_INVALID', customer_auth)
        self.assertIn('X-UI-Language', customer_auth)
        self.assertIn('REQUEST_TIMEOUT', customer_auth)
        self.assertIn('NETWORK_UNAVAILABLE', customer_auth)

    def test_staff_can_enter_admin_with_their_customer_session(self) -> None:
        customer_html = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
        customer_auth = (PROJECT_ROOT / "js" / "auth.js").read_text(encoding="utf-8")
        self.assertIn('id="account-admin-entry"', customer_html)
        self.assertIn('sessionStorage.setItem(ADMIN_TOKEN_KEY, token)', customer_auth)
        self.assertIn('window.open("./admin/", "boten-admin-workspace", "popup,width=1280,height=900")', customer_auth)
        self.assertIn('["admin", "sales"].includes(currentUser.role)', customer_auth)
        self.assertIn('sessionStorage.getItem(CUSTOMER_TOKEN_KEY)', ADMIN_JS)

    def test_color_editor_uses_bilingual_names_and_image_preview(self) -> None:
        customer_api = (PROJECT_ROOT / "js" / "catalog-api.js").read_text(encoding="utf-8")
        self.assertIn('data-color-field="name_zh"', ADMIN_CATALOG_V2)
        self.assertIn('data-color-field="name_en"', ADMIN_CATALOG_V2)
        self.assertIn('data-color-field="display_color"', ADMIN_CATALOG_V2)
        self.assertIn('data-color-image-preview', ADMIN_CATALOG_V2)
        self.assertIn('设备至少需要保留一个启用的外观颜色', ADMIN_CATALOG_V2)
        self.assertIn('colorNames[color.code] = color.name || color.code', customer_api)

    def test_customer_catalog_v2_sales_contact_and_independent_catalog(self) -> None:
        customer_api = (PROJECT_ROOT / "js" / "catalog-api.js").read_text(encoding="utf-8")
        customer_price = (PROJECT_ROOT / "js" / "price.js").read_text(encoding="utf-8")
        runtime_config = (PROJECT_ROOT / "js" / "runtime-config.js").read_text(encoding="utf-8")
        self.assertIn('/snapshot?lang=${language}', customer_api)
        self.assertIn('base_option_groups', customer_api)
        self.assertIn('optional_categories', customer_api)
        self.assertNotIn('id="pricing-preview"', CUSTOMER_HTML)
        self.assertNotIn('/api/v1/pricing/preview', customer_price)
        self.assertIn('id="sales-contact-open"', CUSTOMER_HTML)
        self.assertIn('id="sales-contact-dialog"', CUSTOMER_HTML)
        self.assertIn('function initSalesContact()', customer_price)
        self.assertIn('window.BOTEN_SALES_CONTACT', runtime_config)
        self.assertIn('info@boten-diesel.com', runtime_config)
        self.assertNotIn('id="sales-contact-phone"', CUSTOMER_HTML)
        self.assertIn('class="btn btn-secondary btn-sm sales-whatsapp-button"', CUSTOMER_HTML)
        self.assertIn('https://wa.me/8617625542926', runtime_config)
        self.assertIn('id="catalog-marketplace"', CUSTOMER_HTML)
        self.assertIn('/api/v1/catalog/items?type=', CUSTOMER_MARKETPLACE)
        self.assertIn('/cart/catalog-options/${encodeURIComponent(optionId)}', CUSTOMER_MARKETPLACE)
        self.assertIn('window.refreshCatalogCartOnly', CUSTOMER_MARKETPLACE)
        self.assertNotIn('catalog-item-price', CUSTOMER_MARKETPLACE)
        self.assertIn('specialNote: option.special_note || ""', customer_api)
        self.assertIn('option-special-note', CUSTOMER_RENDERER)

    def test_saved_cart_requests_current_catalog_language(self) -> None:
        customer_cart = (PROJECT_ROOT / "js" / "cart.js").read_text(encoding="utf-8")
        customer_price = (PROJECT_ROOT / "js" / "price.js").read_text(encoding="utf-8")
        self.assertIn('/configs?lang=${cartLanguage()}', customer_cart)
        self.assertIn('/cart/catalog-items?lang=${cartLanguage()}', customer_cart)
        self.assertIn('/cart/share', customer_cart)
        self.assertIn('/cart/export/pdf', customer_cart)
        self.assertIn('/cart/batch-archive', customer_cart)
        self.assertIn('item_type: item.itemType', customer_cart)
        self.assertIn('getColorLabel(snapshot.currentColor, model)', customer_price)
        self.assertNotIn('Green 绿色', customer_price)

    def test_customer_cart_uses_device_tool_accessory_order(self) -> None:
        catalog_repository = (PROJECT_ROOT / "backend" / "catalog_cart_repository.py").read_text(encoding="utf-8")
        config_repository = (PROJECT_ROOT / "backend" / "config_repository.py").read_text(encoding="utf-8")
        commerce_repository = (PROJECT_ROOT / "backend" / "commerce_repository.py").read_text(encoding="utf-8")
        self.assertIn("function compareCartChronology", CUSTOMER_CART)
        self.assertIn("function compareCatalogSystemOrder", CUSTOMER_CART)
        self.assertIn("function orderCartItems(items)", CUSTOMER_CART)
        self.assertLess(CUSTOMER_CART.index('item.itemType === "device_config"'), CUSTOMER_CART.index('item.catalogType === "tools"'))
        self.assertLess(CUSTOMER_CART.index('item.catalogType === "tools"'), CUSTOMER_CART.index('item.catalogType === "accessories"'))
        self.assertIn("renderCatalogCartGroup(type, items)", CUSTOMER_CART)
        self.assertNotIn("data-select-cart-group=", CUSTOMER_CART)
        self.assertIn("data-edit-catalog-group=", CUSTOMER_CART)
        self.assertNotIn("data-detail-catalog-group=", CUSTOMER_CART)
        self.assertIn("COALESCE(o.sort_order, 2147483647)", catalog_repository)
        self.assertIn("ORDER BY created_at ASC, id ASC", config_repository)
        self.assertIn('ITEM_TYPE_ORDER = {"device_config": 0, "tool": 1, "accessory": 2}', commerce_repository)
        self.assertIn("key=_canonical_cart_order", commerce_repository)

    def test_catalog_cart_groups_have_editable_quantity_dialogs(self) -> None:
        self.assertIn("function showCatalogGroupDialog(type)", CUSTOMER_CART)
        self.assertIn("data-catalog-quantity-step", CUSTOMER_CART)
        self.assertIn("data-mark-catalog-delete", CUSTOMER_CART)
        self.assertIn("marked-for-delete", CUSTOMER_CART)
        self.assertIn('/cart/batch-archive', CUSTOMER_CART)
        self.assertIn('method: "PATCH"', CUSTOMER_CART)
        self.assertIn('cartTitle: "我的购物车"', CUSTOMER_LANGUAGE)
        self.assertIn('cartTitle: "My Cart"', CUSTOMER_LANGUAGE)
        self.assertIn('.catalog-group-dialog.is-editing', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('.share-dialog.catalog-group-dialog {', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('width: min(94vw, 1120px);', CUSTOMER_COMPONENTS_CSS)
        self.assertLess(CUSTOMER_COMPONENTS_CSS.index('.share-dialog {'), CUSTOMER_COMPONENTS_CSS.index('.share-dialog.catalog-group-dialog {'))
        self.assertIn('.catalog-dialog-stepper {', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('renderDeviceCartCard(unit.item, ++deviceIndex)', CUSTOMER_CART)
        self.assertIn('class="cart-item-kind-title"', CUSTOMER_CART)
        self.assertIn('class="cart-catalog-group-total"', CUSTOMER_CART)
        self.assertIn('items.reduce((total, item) => total + Number(item.quantity || 1), 0)', CUSTOMER_CART)

    def test_cart_footer_keeps_share_and_pdf_on_the_first_row(self) -> None:
        self.assertIn('exportCombinedPdf: "导出 PDF"', CUSTOMER_LANGUAGE)
        self.assertIn('exportCombinedPdf: "Export PDF"', CUSTOMER_LANGUAGE)
        self.assertIn('.cart-batch-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('.cart-batch-actions .danger { grid-column: 1 / -1;', CUSTOMER_COMPONENTS_CSS)

    def test_cart_actions_operate_on_all_saved_items(self) -> None:
        self.assertIn("function allCartItems()", CUSTOMER_CART)
        self.assertIn("async function shareCart()", CUSTOMER_CART)
        self.assertIn("async function exportCartPdf()", CUSTOMER_CART)
        self.assertIn("function requestCartInquiry()", CUSTOMER_CART)
        self.assertIn('document.getElementById("cart-share")', CUSTOMER_CART)
        self.assertIn('document.getElementById("cart-inquiry")', CUSTOMER_CART)
        self.assertIn('inquiryTitle: "联系销售获取报价"', CUSTOMER_LANGUAGE)
        self.assertIn('inquiryTitle: "Contact Sales for a Quote"', CUSTOMER_LANGUAGE)

    def test_quote_lifecycle_management_exposes_archive_restore_and_history(self) -> None:
        self.assertIn('data-view-panel="quotes"', ADMIN_HTML)
        self.assertIn('报价草稿、已发送版本和归档记录', ADMIN_HTML)
        self.assertIn('function quoteLifecycleLabel(status)', ADMIN_JS)
        self.assertIn('data-archive-quote=', ADMIN_JS)
        self.assertIn('data-restore-quote=', ADMIN_JS)
        self.assertIn('data-quote-history=', ADMIN_JS)
        self.assertIn('/staff/quotes/${encodeURIComponent(quote.id)}/archive', ADMIN_JS)
        self.assertIn('/staff/quotes/${encodeURIComponent(quote.id)}/restore', ADMIN_JS)
        self.assertIn('/staff/quotes/${encodeURIComponent(quoteId)}/history', ADMIN_JS)
        self.assertIn('dialog.quote-history-dialog', ADMIN_CSS)

    def test_admin_api_status_lives_in_sidebar_without_a_desktop_topbar(self) -> None:
        self.assertIn('id="sidebar-api-status"', ADMIN_HTML)
        overview = ADMIN_HTML.index('data-view="dashboard"')
        self.assertLess(overview, ADMIN_HTML.index('id="sidebar-api-status"'))
        self.assertLess(ADMIN_HTML.index('id="sidebar-api-status"'), ADMIN_HTML.index('data-view="products"'))
        self.assertNotIn('<header class="topbar">', ADMIN_HTML)
        self.assertIn('sidebarStatus.querySelector("span").textContent = "API 正常"', ADMIN_JS)
        self.assertIn('.nav-api-status', ADMIN_CSS)

    def test_tool_and_accessory_navigation_use_semantic_svg_icons(self) -> None:
        self.assertIn('data-view="tool-catalog" type="button"><span class="nav-icon nav-icon-svg"', ADMIN_HTML)
        self.assertIn('data-view="accessory-catalog" type="button"><span class="nav-icon nav-icon-svg"', ADMIN_HTML)
        self.assertIn('.nav-icon-svg svg', ADMIN_CSS)

    def test_catalog_pages_add_directly_to_cart_without_pending_summary(self) -> None:
        for marker in (
            'id="catalog-summary-panel"',
            'id="catalog-cart-summary-list"',
            'id="catalog-summary-toggle"',
            'id="catalog-summary-close"',
        ):
            self.assertIn(marker, CUSTOMER_HTML)
        self.assertNotIn('id="catalog-draft-summary-list"', CUSTOMER_HTML)
        self.assertNotIn("drafts: new Map()", CUSTOMER_MARKETPLACE)
        self.assertIn("window.getCatalogCartSnapshot", CUSTOMER_CART)
        self.assertIn("function renderMarketplaceSummary", CUSTOMER_MARKETPLACE)
        self.assertIn("const selected = inCartQuantity > 0", CUSTOMER_MARKETPLACE)
        self.assertIn('body: JSON.stringify({ quantity: submittedQuantity, lang: marketplaceLanguage() })', CUSTOMER_MARKETPLACE)
        self.assertIn('class="catalog-product-selected-mark"', CUSTOMER_MARKETPLACE)
        self.assertIn('window.addEventListener("boten:cart-updated"', CUSTOMER_MARKETPLACE)
        self.assertIn('catalogSummary.hidden = !showCatalog', CUSTOMER_RENDERER)
        self.assertIn('catalogSummaryToggle.hidden = !showCatalog', CUSTOMER_RENDERER)
        self.assertIn('function bindCatalogSummaryDrawer()', CUSTOMER_MARKETPLACE)
        self.assertIn('panel.setAttribute("aria-modal", "true")', CUSTOMER_MARKETPLACE)
        self.assertIn('.catalog-summary-panel.open {', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('.catalog-product-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-sm); }', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('aria-labelledby="catalog-cart-summary-title"', CUSTOMER_HTML)
        self.assertNotIn('id="catalog-summary-title"', CUSTOMER_HTML)
        self.assertNotIn('class="catalog-summary-section"', CUSTOMER_HTML)
        self.assertIn('.catalog-summary-heading {', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('.catalog-summary-list { display: grid;', CUSTOMER_COMPONENTS_CSS)
        self.assertNotIn('.catalog-summary-quantity {', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('.catalog-product-card.selected {', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('id="catalog-drawer-toggle"', CUSTOMER_HTML)
        self.assertNotIn('setMarketplaceStatus(marketplaceText("addedToCart"', CUSTOMER_MARKETPLACE)
        self.assertNotIn('.catalog-marketplace-status.success', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('async function changeMarketplaceCartQuantity(optionId, quantity, delta)', CUSTOMER_MARKETPLACE)
        self.assertIn('if (delta < 0 && quantity === 1)', CUSTOMER_MARKETPLACE)
        self.assertIn('await window.confirmCartRemoval?.(message, title)', CUSTOMER_MARKETPLACE)
        self.assertIn('scheduleMarketplaceQuantitySave(optionId, quantity + delta)', CUSTOMER_MARKETPLACE)
        self.assertIn('method: "PUT"', CUSTOMER_MARKETPLACE)
        self.assertIn('window.refreshCatalogCartOnly', CUSTOMER_MARKETPLACE)
        self.assertIn('window.refreshCatalogCartOnly = async function refreshCatalogCartOnly()', CUSTOMER_CART)
        self.assertIn('window.confirmCartRemoval = confirmCartRemoval', CUSTOMER_CART)

    def test_desktop_selection_sidebars_scroll_inside_the_viewport(self) -> None:
        self.assertIn('max-height: calc(100dvh - var(--header-height) - (2 * var(--space-lg)))', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('.summary-panel .summary-list,\n  .catalog-summary-panel .catalog-summary-list {', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('overscroll-behavior: contain;', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('scrollbar-gutter: stable;', CUSTOMER_COMPONENTS_CSS)

    def test_cart_actions_and_share_filters_are_exposed(self) -> None:
        customer_html = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
        customer_state = (PROJECT_ROOT / "js" / "state.js").read_text(encoding="utf-8")
        self.assertNotIn('id="share-current"', customer_html)
        self.assertNotIn('id="export-print"', customer_html)
        for element_id in ("cart-share", "cart-pdf", "cart-inquiry", "config-edit-status", "cart-operation-status"):
            self.assertIn('id="{}"'.format(element_id), customer_html)
        for removed_id in ("cart-select-all", "cart-share-selected", "cart-pdf-selected", "cart-remove-selected"):
            self.assertNotIn('id="{}"'.format(removed_id), customer_html)
        self.assertIn("missingCount", customer_state)
        for element_id in ("share-filter-form", "share-query", "share-status-filter", "share-page-summary"):
            self.assertIn('id="{}"'.format(element_id), ADMIN_HTML)
        for removed_filter in ("share-product-filter", "share-created-from", "share-created-to"):
            self.assertNotIn('id="{}"'.format(removed_filter), ADMIN_HTML)
        self.assertIn('/shares/${button.dataset.closeShare}/status', ADMIN_JS)

    def test_customer_price_boundary_and_unified_top_selector_are_explicit(self) -> None:
        backend_routes = (PROJECT_ROOT / "backend" / "config_routes.py").read_text(encoding="utf-8")
        pdf_service = (PROJECT_ROOT / "backend" / "pdf_service.py").read_text(encoding="utf-8")
        customer_renderer = (PROJECT_ROOT / "js" / "renderer.js").read_text(encoding="utf-8")
        self.assertIn('user=Depends(staff_user)', backend_routes)
        self.assertIn('without_prices({"items": list_public_catalog_items', backend_routes)
        self.assertIn('include_prices=True', backend_routes)
        self.assertIn('include_prices: bool = False', pdf_service)
        for value in ('device:${m.id}', 'catalog:tools', 'catalog:accessories'):
            self.assertIn(value, customer_renderer)
        self.assertIn('window.botenShowDeviceSelection', customer_renderer)

    def test_inquiry_workflow_is_separate_from_shares_and_exposed_to_staff(self) -> None:
        backend_routes = (PROJECT_ROOT / "backend" / "config_routes.py").read_text(encoding="utf-8")
        inquiry_repository = (PROJECT_ROOT / "backend" / "inquiry_repository.py").read_text(encoding="utf-8")
        self.assertIn('data-view="inquiries"', ADMIN_HTML)
        self.assertIn('data-view-panel="inquiries"', ADMIN_HTML)
        self.assertIn('/api/v1/staff/inquiries?', ADMIN_JS)
        self.assertIn('convert-to-quote', ADMIN_JS)
        self.assertIn('@router.get("/staff/inquiries")', backend_routes)
        self.assertIn('@router.post("/staff/inquiries/{inquiry_id}/convert-to-quote"', backend_routes)
        self.assertIn('def inquiry_quote_items(', inquiry_repository)

    def test_customer_page_restores_the_last_catalog_and_defaults_to_cr1016(self) -> None:
        customer_state = (PROJECT_ROOT / "js" / "state.js").read_text(encoding="utf-8")
        customer_renderer = (PROJECT_ROOT / "js" / "renderer.js").read_text(encoding="utf-8")
        self.assertIn('sessionStorage.getItem("boten-page-device-state")', customer_state)
        self.assertIn('model.id === "cr1016"', customer_state)
        self.assertIn('const selectionViewStorageKey = "boten-page-selection-view"', customer_renderer)
        self.assertIn('return "device"', customer_renderer)
        self.assertNotIn('applySelectionView("none")', customer_renderer)

    def test_cart_cards_and_destructive_confirmation_use_the_page_design_system(self) -> None:
        self.assertIn('class="cart-item-toolbar"', CUSTOMER_CART)
        self.assertIn('btn btn-secondary btn-sm cart-item-details', CUSTOMER_CART)
        self.assertIn('confirmCartRemoval(message, title)', CUSTOMER_CART)
        self.assertIn('dialog.className = "share-dialog cart-confirm-dialog"', CUSTOMER_CART)
        self.assertNotIn('window.confirm(message)', CUSTOMER_CART)
        self.assertIn('width: min(420px, 80vw)', CUSTOMER_COMPONENTS_CSS)
        self.assertIn('id="cancel-config-edit" class="btn btn-secondary btn-sm config-edit-cancel"', CUSTOMER_HTML)

    def test_cart_device_edit_uses_the_loaded_snapshot_model(self) -> None:
        self.assertIn("const loadedModelId = state.getSnapshot().currentModelId", CUSTOMER_CART)
        self.assertIn("window.botenShowDeviceSelection?.(loadedModelId)", CUSTOMER_CART)
        self.assertIn("if (!deviceShown)", CUSTOMER_CART)

    def test_product_mapping_v2_supports_device_specific_notes(self) -> None:
        self.assertIn('state.mappingEditor.selected', ADMIN_CATALOG_V2)
        self.assertIn('optionalCategories()', ADMIN_CATALOG_V2)
        self.assertIn('data-edit-mapping-note', ADMIN_CATALOG_V2)
        self.assertIn('optional_config_overrides', ADMIN_CATALOG_V2)
        self.assertIn('mapping-option-code', ADMIN_CATALOG_V2)
        self.assertIn('option-special-note', CUSTOMER_RENDERER)

    def test_catalog_v2_exposes_three_roots_and_manual_bilingual_crud(self) -> None:
        for root_id in ("catalog-optional", "catalog-tools", "catalog-accessories"):
            self.assertIn(root_id, ADMIN_CATALOG_V2)
        self.assertIn('/api/v1/admin/catalog/categories', ADMIN_CATALOG_V2)
        self.assertIn('/api/v1/admin/catalog/items', ADMIN_CATALOG_V2)
        self.assertIn('translation_status', ADMIN_CATALOG_V2)
        self.assertIn('/api/v1/admin/catalog/translation-draft', ADMIN_CATALOG_V2)
        self.assertIn('data-catalog-root', ADMIN_CATALOG_V2)
        self.assertNotIn('data-catalog-translation-filter', ADMIN_CATALOG_V2)
        self.assertNotIn('catalogReview', ADMIN_CATALOG_V2)
        self.assertNotIn('id="product-translation-draft"', ADMIN_HTML)
        self.assertNotIn('<span>翻译状态</span>', ADMIN_HTML)
        self.assertIn('字段标题保持中文，右上角切换当前编辑的内容语言。', ADMIN_CATALOG_V2)

    def test_catalog_item_editor_uses_shared_editor_card_layout(self) -> None:
        for marker in (
            'class="catalog-dialog-footer"',
            'class="catalog-dialog-footer-actions"',
            'class="catalog-field-list"',
            'class="catalog-field catalog-image-field"',
            'class="compact-check catalog-footer-enabled"',
        ):
            self.assertIn(marker, ADMIN_CATALOG_V2)
        self.assertIn('dialogClass: "catalog-item-editor-dialog"', ADMIN_CATALOG_V2)
        self.assertIn('catalogType === "optional"', ADMIN_CATALOG_V2)
        self.assertIn('type="hidden" value="${escapeHtml(selectedCategoryId)}"', ADMIN_CATALOG_V2)

    def test_catalog_editors_use_aligned_rows_and_footer_status_controls(self) -> None:
        self.assertIn('footerControl = ""', ADMIN_CATALOG_V2)
        self.assertIn('class="compact-check catalog-footer-enabled"', ADMIN_CATALOG_V2)
        self.assertIn('<span>启用分类</span>', ADMIN_CATALOG_V2)
        self.assertIn('<span>启用${labels.singular}</span>', ADMIN_CATALOG_V2)
        self.assertIn('catalog-field catalog-image-field', ADMIN_CATALOG_V2)
        self.assertIn('<span>人民币参考价格</span><input name="price_cny"', ADMIN_CATALOG_V2)
        self.assertIn('<span>美元参考价格</span><input name="price_usd"', ADMIN_CATALOG_V2)
        self.assertLess(
            ADMIN_CATALOG_V2.index('catalog-field catalog-image-field'),
            ADMIN_CATALOG_V2.index('${translationFields(item || {}'),
        )
        self.assertIn('.catalog-image-field { align-items: center;', ADMIN_CSS)
        self.assertIn('.catalog-footer-enabled {', ADMIN_CSS)
        self.assertIn('.language-value-field > [data-content-lang] { grid-column: 2;', ADMIN_CSS)

    def test_catalog_image_preview_follows_complete_image_design_rule(self) -> None:
        self.assertIn('.catalog-image-preview { position: relative;', ADMIN_CSS)
        self.assertIn('padding: 8px;', ADMIN_CSS)
        self.assertIn('.catalog-image-preview img { position: absolute; inset: 8px;', ADMIN_CSS)
        self.assertIn('object-fit: contain;', ADMIN_CSS)
        self.assertIn('object-position: center;', ADMIN_CSS)

    def test_device_editor_v2_has_base_options_and_price_variants(self) -> None:
        for panel_id in ("editor-panel-base-options", "editor-panel-pricing", "editor-panel-options"):
            self.assertIn('id="{}"'.format(panel_id), ADMIN_HTML)
        self.assertIn('motor', ADMIN_CATALOG_V2)
        self.assertIn('power', ADMIN_CATALOG_V2)
        self.assertIn('channel', ADMIN_CATALOG_V2)
        self.assertIn('price_cny_minor', ADMIN_CATALOG_V2)
        self.assertIn('price_usd_minor', ADMIN_CATALOG_V2)
        self.assertIn('base-option-row-simple', ADMIN_CATALOG_V2)
        self.assertIn('base-option-row-power', ADMIN_CATALOG_V2)
        self.assertNotIn('data-base-price-confirmed', ADMIN_CATALOG_V2)
        self.assertNotIn('data-variant-confirmed', ADMIN_CATALOG_V2)
        self.assertNotIn('<span>价格已确认</span>', ADMIN_CATALOG_V2)

    def test_device_enabled_control_is_in_the_dialog_footer(self) -> None:
        footer = ADMIN_HTML.index('<footer class="product-dialog-footer">')
        enabled = ADMIN_HTML.index('name="enabled"', footer)
        actions = ADMIN_HTML.index('class="product-dialog-footer-actions"', enabled)
        self.assertLess(footer, enabled)
        self.assertLess(enabled, actions)

    def test_product_editor_warns_for_every_unsaved_module(self) -> None:
        self.assertIn('function productEditorSnapshot()', ADMIN_CATALOG_V2)
        self.assertIn('selected: Array.from(editor.selected || []).sort()', ADMIN_CATALOG_V2)
        self.assertIn('window.hasUnsavedProductChanges', ADMIN_CATALOG_V2)
        self.assertIn('window.addEventListener("beforeunload"', ADMIN_CATALOG_V2)
        self.assertIn('className = "confirm-dialog"', ADMIN_JS)
        self.assertIn('dialog.classList.contains("confirm-dialog")', ADMIN_JS)
        self.assertIn('aria-describedby', ADMIN_JS)
        self.assertIn('继续编辑', ADMIN_JS)

    def test_color_editor_uses_aligned_controls_without_exposing_color_code(self) -> None:
        self.assertIn('class="color-state-controls"', ADMIN_CATALOG_V2)
        self.assertIn('aria-label="选择前端显示的文字颜色"', ADMIN_CATALOG_V2)
        self.assertNotIn('<code>${escapeHtml(color.display_color', ADMIN_CATALOG_V2)
        self.assertIn('const TEXT_COLOR_PRESETS', ADMIN_CATALOG_V2)
        for label in ("红色", "绿色", "蓝色", "黄色", "黑色", "灰色"):
            self.assertIn(label, ADMIN_CATALOG_V2)
        self.assertIn('<select data-color-field="display_color"', ADMIN_CATALOG_V2)
        self.assertIn('style="color:${escapeOptionHtml(displayColor)}"', CUSTOMER_RENDERER)
        self.assertIn('.product-dialog .color-image-preview img', ADMIN_CSS)
        self.assertIn('aspect-ratio: 2 / 1;', ADMIN_CSS)
        self.assertIn('position: absolute; inset: 8px;', ADMIN_CSS)
        self.assertIn('width: calc(100% - 16px); height: calc(100% - 16px);', ADMIN_CSS)
        self.assertIn('object-fit: contain;', ADMIN_CSS)

    def test_pages_expose_skip_links_and_complete_tab_semantics(self) -> None:
        self.assertIn('class="skip-link" href="#admin-content"', ADMIN_HTML)
        self.assertIn('class="skip-link" href="#main-content"', CUSTOMER_HTML)
        self.assertIn('role="tab" aria-selected="true" aria-controls="editor-panel-basic"', ADMIN_HTML)
        self.assertIn('role="tablist" aria-label="配置分类"', CUSTOMER_HTML)
        self.assertIn('aria-controls="options-panel"', CUSTOMER_RENDERER)

    def test_customer_accessible_names_follow_the_selected_language(self) -> None:
        for key in (
            "skipToContent", "languageSwitcher", "cartCount", "configurationArea",
            "gallery", "previousImage", "nextImage", "appearanceSelection",
            "motorSelection", "powerSelection", "channelSelection",
            "deviceConfiguration", "categoryTabs", "catalogTabs", "catalogCategories",
            "jumpTo", "colorSwatch",
        ):
            self.assertIn(f'{key}:', CUSTOMER_LANGUAGE)
        self.assertIn('skipLink.textContent = text.skipToContent', CUSTOMER_LANGUAGE)
        self.assertIn('gallery.setAttribute("aria-label", text.gallery)', CUSTOMER_LANGUAGE)
        self.assertIn('categoryTabs.setAttribute("aria-label", text.categoryTabs)', CUSTOMER_LANGUAGE)
        self.assertIn('catalogCategories.setAttribute("aria-label", text.catalogCategories)', CUSTOMER_LANGUAGE)
        self.assertIn('window.botenI18n?.t("slide")', CUSTOMER_RENDERER)
        self.assertIn('window.botenI18n?.t("jumpTo")', CUSTOMER_RENDERER)
        self.assertIn('prefersReducedMotion() ? "auto" : "smooth"', CUSTOMER_RENDERER)

    def test_catalog_filtering_and_hash_navigation_are_restorable(self) -> None:
        self.assertIn('id="mapping-search"', ADMIN_HTML)
        self.assertIn('data-mapping-filter="selected"', ADMIN_HTML)
        self.assertIn('window.location.hash = view', ADMIN_JS)
        self.assertIn('window.addEventListener("hashchange"', ADMIN_JS)

    def test_customer_drawers_manage_focus_and_background_inertness(self) -> None:
        self.assertIn('region.inert = true', CUSTOMER_RENDERER)
        self.assertIn('previousFocus?.focus()', CUSTOMER_RENDERER)
        self.assertIn('trapCartFocus(event)', CUSTOMER_CART)
        self.assertIn('panel._returnFocus?.focus()', CUSTOMER_CART)

    def test_account_management_uses_separate_safe_workflows(self) -> None:
        for dialog_id in ("user-dialog", "user-role-dialog", "user-password-dialog", "user-archive-dialog"):
            self.assertIn('id="{}"'.format(dialog_id), ADMIN_HTML)
        self.assertIn('id="user-search"', ADMIN_HTML)
        self.assertIn('id="user-archived-filter"', ADMIN_HTML)
        self.assertIn('data-field-error="email"', ADMIN_HTML)
        self.assertIn('class ApiError extends Error', ADMIN_JS)
        self.assertIn('ACCOUNT_ERROR_TEXT_ZH', ADMIN_JS)
        self.assertIn('ACCOUNT_ERROR_TEXT_EN', ADMIN_JS)
        self.assertIn('applyUserMutation(result', ADMIN_JS)
        self.assertIn('操作已保存，但列表同步失败', ADMIN_JS)
        self.assertIn('button.setAttribute("aria-busy", "true")', ADMIN_JS)
        self.assertIn('/archive`, { method: "POST"', ADMIN_JS)
        self.assertIn('/restore`, { method: "POST"', ADMIN_JS)


if __name__ == "__main__":
    unittest.main()
