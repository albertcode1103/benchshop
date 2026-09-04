"""Migrate legacy motor and power mappings into the new catalog model."""

from alembic import op


revision = "20260903_0011"
down_revision = "20260903_0010"
branch_labels = None
depends_on = None


def _whole_to_minor(value) -> int:
    if value in (None, ""):
        return 0
    return max(0, int(round(float(value) * 100)))


def _insert_group(bind, product_id: str, option_type: str, sort_order: int) -> str:
    group_id = "base-{}-{}".format(product_id, option_type)
    bind.exec_driver_sql(
        """
        INSERT OR IGNORE INTO product_base_option_groups
            (id, product_id, option_type, required, single_select, sort_order, enabled)
        VALUES (?, ?, ?, 1, 1, ?, 1)
        """,
        (group_id, product_id, option_type, sort_order),
    )
    return group_id


def _insert_base_option(bind, group_id: str, product_id: str, option_type: str, row, sort_order: int) -> str:
    option_id = "base-{}-{}-{}".format(product_id, option_type, row["id"])
    cny_minor = 0
    usd_minor = 0
    is_free = 0
    price_confirmed = 0
    if option_type == "power":
        cny_minor = _whole_to_minor(row["price"])
        usd_minor = _whole_to_minor(row["price_usd"])
        is_free = int(cny_minor == 0 and usd_minor == 0 and "default" in row["id"])
        price_confirmed = is_free

    bind.exec_driver_sql(
        """
        INSERT OR IGNORE INTO product_base_options
            (id, group_id, name_zh, name_en, price_cny_minor, price_usd_minor,
             price_confirmed, is_free, sort_order, enabled, translation_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            option_id,
            group_id,
            row["name"],
            row["name_en"] or "",
            cny_minor,
            usd_minor,
            price_confirmed,
            is_free,
            sort_order,
            int(bool(row["enabled"])),
            "reviewed" if (row["name_en"] or "").strip() else "machine_draft",
        ),
    )
    return option_id


def upgrade() -> None:
    bind = op.get_bind()

    roots = (
        ("catalog-optional", "可选配置", "Optional Configurations", "optional", 0),
        ("catalog-tools", "维修工具", "Service Tools", "tools", 1),
        ("catalog-accessories", "设备附件", "Accessories", "accessories", 2),
    )
    for category_id, name, name_en, catalog_type, sort_order in roots:
        bind.exec_driver_sql(
            """
            INSERT OR IGNORE INTO categories
                (id, name, name_en, description, description_en, multiple, sort_order,
                 parent_id, catalog_type, enabled, version, translation_status)
            VALUES (?, ?, ?, '', '', 1, ?, NULL, ?, 1, 1, 'reviewed')
            """,
            (category_id, name, name_en, sort_order, catalog_type),
        )

    bind.exec_driver_sql(
        """
        UPDATE categories
        SET parent_id = 'catalog-optional'
        WHERE catalog_type = 'optional'
          AND id NOT IN ('catalog-optional', 'catalog-tools', 'catalog-accessories')
        """
    )
    bind.exec_driver_sql(
        """
        UPDATE categories
        SET parent_id = 'catalog-accessories'
        WHERE catalog_type = 'accessories'
          AND id NOT IN ('catalog-optional', 'catalog-tools', 'catalog-accessories')
        """
    )

    # These legacy descriptions already contain English technical text. Copying
    # them avoids a Chinese fallback while preserving the original for review.
    bind.exec_driver_sql(
        """
        UPDATE options
        SET description_en = description,
            translation_status = 'machine_draft'
        WHERE trim(COALESCE(description, '')) <> ''
          AND trim(COALESCE(description_en, '')) = ''
        """
    )

    products = bind.exec_driver_sql(
        "SELECT id FROM products ORDER BY sort_order, id"
    ).mappings().all()

    for product in products:
        product_id = product["id"]
        legacy_rows = bind.exec_driver_sql(
            """
            SELECT o.id, o.category_id, o.name, o.name_en, o.price, o.price_usd,
                   o.enabled, o.sort_order
            FROM product_options po
            JOIN options o ON o.id = po.option_id
            WHERE po.product_id = ?
              AND po.enabled = 1
              AND o.category_id IN ('motor', 'voltage')
            ORDER BY o.category_id, o.sort_order, o.id
            """,
            (product_id,),
        ).mappings().all()

        new_motor_ids = {}
        for option_type, legacy_category, group_sort in (
            ("motor", "motor", 0),
            ("power", "voltage", 1),
        ):
            matching = [row for row in legacy_rows if row["category_id"] == legacy_category]
            if not matching:
                continue
            group_id = _insert_group(bind, product_id, option_type, group_sort)
            for index, row in enumerate(matching):
                new_id = _insert_base_option(bind, group_id, product_id, option_type, row, index)
                if option_type == "motor":
                    new_motor_ids[row["id"]] = new_id

        motor_prices = bind.exec_driver_sql(
            """
            SELECT motor_option_id, base_price_cny, base_price_usd
            FROM product_motor_prices
            WHERE product_id = ?
            ORDER BY motor_option_id
            """,
            (product_id,),
        ).mappings().all()
        for row in motor_prices:
            motor_option_id = new_motor_ids.get(row["motor_option_id"])
            if not motor_option_id:
                continue
            variant_id = "price-{}-{}".format(product_id, row["motor_option_id"])
            bind.exec_driver_sql(
                """
                INSERT OR IGNORE INTO product_price_variants
                    (id, product_id, motor_option_id, channel_option_id,
                     price_cny_minor, price_usd_minor, price_confirmed, enabled)
                VALUES (?, ?, ?, NULL, ?, ?, 0, 1)
                """,
                (
                    variant_id,
                    product_id,
                    motor_option_id,
                    _whole_to_minor(row["base_price_cny"]),
                    _whole_to_minor(row["base_price_usd"]),
                ),
            )

    # CR318 PRO is the first channel-priced device requested by the business.
    product_exists = bind.exec_driver_sql(
        "SELECT 1 FROM products WHERE id = 'cr318pro'"
    ).first()
    if product_exists:
        channel_group = _insert_group(bind, "cr318pro", "channel", 2)
        motor_option = bind.exec_driver_sql(
            """
            SELECT id FROM product_base_options
            WHERE group_id = 'base-cr318pro-motor'
            ORDER BY sort_order, id LIMIT 1
            """
        ).first()
        for index, (channel_id, name_zh, name_en) in enumerate(
            (
                ("base-cr318pro-channel-2", "2 通道", "2 Channels"),
                ("base-cr318pro-channel-4", "4 通道", "4 Channels"),
            )
        ):
            bind.exec_driver_sql(
                """
                INSERT OR IGNORE INTO product_base_options
                    (id, group_id, name_zh, name_en, price_cny_minor, price_usd_minor,
                     price_confirmed, is_free, sort_order, enabled, translation_status)
                VALUES (?, ?, ?, ?, 0, 0, 0, 0, ?, 1, 'machine_draft')
                """,
                (channel_id, channel_group, name_zh, name_en, index),
            )
            if motor_option:
                bind.exec_driver_sql(
                    """
                    INSERT OR IGNORE INTO product_price_variants
                        (id, product_id, motor_option_id, channel_option_id,
                         price_cny_minor, price_usd_minor, price_confirmed, enabled)
                    VALUES (?, 'cr318pro', ?, ?, 0, 0, 0, 1)
                    """,
                    (
                        "price-cr318pro-{}".format(index + 2),
                        motor_option[0],
                        channel_id,
                    ),
                )

        # Once channels exist, CR318 PRO must use the exact motor+channel
        # variants rather than the legacy motor-only fallback.
        if motor_option:
            bind.exec_driver_sql(
                """
                UPDATE product_price_variants
                SET enabled = 0
                WHERE product_id = 'cr318pro'
                  AND motor_option_id = ?
                  AND channel_option_id IS NULL
                """,
                (motor_option[0],),
            )


def downgrade() -> None:
    # Preserve copied and subsequently edited data. Roll back the application
    # with the verified database snapshot rather than destructive row deletes.
    pass
