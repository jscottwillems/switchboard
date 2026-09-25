"""Postgres writes for attr.campaign and attr.campaign_attribution."""

from datetime import datetime
from uuid import UUID

from switchboard_schemas.attribution import Campaign, CampaignAttribution
from switchboard_schemas.enums import CampaignStatus

from switchboard_repositories.columns import ATTRIBUTION_COLUMNS, CAMPAIGN_COLUMNS
from switchboard_repositories.connection import DictConnection
from switchboard_repositories.cursors import decode_cursor, encode_cursor
from switchboard_repositories.errors import NotFound
from switchboard_repositories.mapping import attribution_from_row, campaign_from_row


class PostgresCampaigns:
    def __init__(self, conn: DictConnection) -> None:
        self._conn = conn

    def insert(self, campaign: Campaign) -> tuple[Campaign, bool]:
        row = self._conn.execute(
            f"""
            INSERT INTO attr.campaign (
                id,
                label,
                status,
                summary,
                created_at,
                updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            RETURNING {CAMPAIGN_COLUMNS}
            """,
            (
                campaign.id,
                campaign.label,
                campaign.status.value,
                campaign.summary,
                campaign.created_at,
                campaign.updated_at,
            ),
        ).fetchone()
        if row is not None:
            return campaign_from_row(row), True
        existing = self.get(campaign.id)
        if existing is None:
            raise RuntimeError("campaign conflicted but no row was stored")
        return existing, False

    def get(self, campaign_id: UUID) -> Campaign | None:
        row = self._conn.execute(
            f"""
            SELECT {CAMPAIGN_COLUMNS}
            FROM attr.campaign
            WHERE id = %s
            """,
            (campaign_id,),
        ).fetchone()
        if row is None:
            return None
        return campaign_from_row(row)

    def list_page(
        self,
        *,
        limit: int,
        cursor: str | None = None,
    ) -> tuple[list[Campaign], str | None]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        moment, row_id = _cursor_bounds(cursor)
        rows = self._conn.execute(
            f"""
            SELECT {CAMPAIGN_COLUMNS}
            FROM attr.campaign
            WHERE (
                %s::timestamptz IS NULL
                OR (created_at, id) < (%s::timestamptz, %s::uuid)
            )
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (moment, moment, row_id, limit + 1),
        ).fetchall()
        page = [campaign_from_row(row) for row in rows[:limit]]
        if len(rows) <= limit:
            return page, None
        last = page[-1]
        return page, encode_cursor(last.created_at, last.id)

    def set_status(self, campaign_id: UUID, status: CampaignStatus) -> Campaign:
        row = self._conn.execute(
            f"""
            UPDATE attr.campaign
            SET status = %s,
                updated_at = now()
            WHERE id = %s
            RETURNING {CAMPAIGN_COLUMNS}
            """,
            (status.value, campaign_id),
        ).fetchone()
        if row is None:
            raise NotFound(f"campaign {campaign_id} does not exist")
        return campaign_from_row(row)


class PostgresAttributions:
    def __init__(self, conn: DictConnection) -> None:
        self._conn = conn

    def insert(self, attribution: CampaignAttribution) -> tuple[CampaignAttribution, bool]:
        row = self._conn.execute(
            f"""
            INSERT INTO attr.campaign_attribution (
                id,
                campaign_id,
                call_session_id,
                supporting_finding_ids,
                method,
                method_version,
                confidence,
                rationale,
                created_at
            ) VALUES (%s, %s, %s, %s::uuid[], %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            RETURNING {ATTRIBUTION_COLUMNS}
            """,
            (
                attribution.id,
                attribution.campaign_id,
                attribution.call_session_id,
                attribution.supporting_finding_ids,
                attribution.method,
                attribution.method_version,
                attribution.confidence,
                attribution.rationale,
                attribution.created_at,
            ),
        ).fetchone()
        if row is not None:
            return attribution_from_row(row), True
        existing = self.get(attribution.id)
        if existing is None:
            raise RuntimeError("attribution conflicted but no row was stored")
        return existing, False

    def get(self, attribution_id: UUID) -> CampaignAttribution | None:
        row = self._conn.execute(
            f"""
            SELECT {ATTRIBUTION_COLUMNS}
            FROM attr.campaign_attribution
            WHERE id = %s
            """,
            (attribution_id,),
        ).fetchone()
        if row is None:
            return None
        return attribution_from_row(row)

    def list_for_session(self, call_session_id: UUID) -> list[CampaignAttribution]:
        rows = self._conn.execute(
            f"""
            SELECT {ATTRIBUTION_COLUMNS}
            FROM attr.campaign_attribution
            WHERE call_session_id = %s
            ORDER BY created_at ASC, id ASC
            """,
            (call_session_id,),
        ).fetchall()
        return [attribution_from_row(row) for row in rows]

    def list_for_campaign(self, campaign_id: UUID) -> list[CampaignAttribution]:
        rows = self._conn.execute(
            f"""
            SELECT {ATTRIBUTION_COLUMNS}
            FROM attr.campaign_attribution
            WHERE campaign_id = %s
            ORDER BY created_at ASC, id ASC
            """,
            (campaign_id,),
        ).fetchall()
        return [attribution_from_row(row) for row in rows]


def _cursor_bounds(cursor: str | None) -> tuple[datetime | None, UUID | None]:
    if cursor is None:
        return None, None
    return decode_cursor(cursor)
