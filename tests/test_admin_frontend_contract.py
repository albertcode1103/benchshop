import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADMIN_JS = (PROJECT_ROOT / "admin" / "admin.js").read_text(encoding="utf-8")
ADMIN_HTML = (PROJECT_ROOT / "admin" / "index.html").read_text(encoding="utf-8")
CUSTOMER_HTML = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
CUSTOMER_RENDERER = (PROJECT_ROOT / "js" / "renderer.js").read_text(encoding="utf-8")
CUSTOMER_CART = (PROJECT_ROOT / "js" / "cart.js").read_text(encoding="utf-8")


class AdminFrontendContractTests(unittest.TestCase):
    def test_sales_can_open_catalog_navigation(self) -> None:
        self.assertIn('data-view="products" type="button"', ADMIN_HTML)
        self.assertIn('data-view="config-catalog" type="button"', ADMIN_HTML)
        self.assertNotIn('data-view="products" data-admin-only', ADMIN_HTML)
        self.assertNotIn('data-view="config-catalog" data-admin-only', ADMIN_HTML)

    def test_product_editor_uses_atomic_save_endpoint(self) -> None:
        self.assertIn('/api/v1/admin/products/${productId}/configuration', ADMIN_JS)
        self.assertIn('option_overrides: optionOverrides', ADMIN_JS)

    def test_quote_and_share_pdf_downloads_use_dom_links(self) -> None:
        self.assertIn('await exportQuote(savedQuote)', ADMIN_JS)
        self.assertIn('document.body.appendChild(link);', ADMIN_JS)
        self.assertNotIn('printWindow.document.write', ADMIN_JS)

    def test_quote_prefill_uses_selected_motor_snapshot_price(self) -> None:
        self.assertIn('price_cny: Number(share.snapshot.product.base_price || 0)', ADMIN_JS)
        self.assertIn('price_usd: Number(share.snapshot.product.price_usd || 0)', ADMIN_JS)
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
        self.assertIn('data-color-name-lang="zh"', ADMIN_JS)
        self.assertIn('data-color-field="label_en"', ADMIN_JS)
        self.assertIn('data-color-image-preview', ADMIN_JS)
        self.assertIn('每台设备至少保留一种外观颜色', ADMIN_JS)
        self.assertIn('colorNames[color.code] = color.label || color.code', customer_api)

    def test_saved_cart_requests_current_catalog_language(self) -> None:
        customer_cart = (PROJECT_ROOT / "js" / "cart.js").read_text(encoding="utf-8")
        customer_price = (PROJECT_ROOT / "js" / "price.js").read_text(encoding="utf-8")
        self.assertIn('/configs?lang=${language}', customer_cart)
        self.assertIn('getColorLabel(snapshot.currentColor, model)', customer_price)
        self.assertNotIn('Green 绿色', customer_price)

    def test_product_mapping_notes_use_dedicated_bilingual_editor(self) -> None:
        customer_api = (PROJECT_ROOT / "js" / "catalog-api.js").read_text(encoding="utf-8")
        customer_renderer = (PROJECT_ROOT / "js" / "renderer.js").read_text(encoding="utf-8")
        self.assertIn('data-edit-mapping-note', ADMIN_JS)
        self.assertIn('data-note-lang="zh"', ADMIN_JS)
        self.assertIn('data-note-lang="en"', ADMIN_JS)
        self.assertIn('state.mappingEditor.selected', ADMIN_JS)
        self.assertNotIn('data-override-lang', ADMIN_JS)
        self.assertIn('specialNote: option.special_note || ""', customer_api)
        self.assertIn('option-special-note', customer_renderer)

    def test_pages_expose_skip_links_and_complete_tab_semantics(self) -> None:
        self.assertIn('class="skip-link" href="#admin-content"', ADMIN_HTML)
        self.assertIn('class="skip-link" href="#main-content"', CUSTOMER_HTML)
        self.assertIn('role="tab" aria-selected="true" aria-controls="editor-panel-basic"', ADMIN_HTML)
        self.assertIn('role="tablist" aria-label="配置分类"', CUSTOMER_HTML)
        self.assertIn('aria-controls="options-panel"', CUSTOMER_RENDERER)

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


if __name__ == "__main__":
    unittest.main()
