from __future__ import annotations

import database


def get_organization_sort_order_map():
    with database.get_connection() as connection:
        rows = connection.execute(
            "SELECT id, sort_order FROM organization_units"
        ).fetchall()

    return {
        int(row["id"]): int(row["sort_order"] or 0)
        for row in rows
    }


def get_canal_sort_order_map():
    with database.get_connection() as connection:
        rows = connection.execute(
            "SELECT id, sort_order FROM canal_units"
        ).fetchall()

    return {
        int(row["id"]): int(row["sort_order"] or 0)
        for row in rows
    }
