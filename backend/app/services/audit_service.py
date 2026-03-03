from datetime import datetime
from uuid import UUID

import structlog
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = structlog.get_logger(__name__)


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def log(
        self,
        org_id: UUID,
        user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        deal_id: UUID | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Create an audit log entry."""
        entry = AuditLog(
            org_id=org_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            deal_id=deal_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(entry)
        await self.db.flush()

        logger.debug(
            "audit_logged",
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            user_id=str(user_id),
        )
        return entry

    async def query_logs(
        self,
        org_id: UUID,
        user_id: UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        deal_id: UUID | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict:
        """Query audit logs with filters and cursor-based pagination.

        Returns {"items": [...], "cursor": str | None, "has_more": bool}
        """
        stmt = (
            select(AuditLog)
            .where(AuditLog.org_id == org_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        )

        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if deal_id:
            stmt = stmt.where(AuditLog.deal_id == deal_id)
        if start_date:
            stmt = stmt.where(AuditLog.created_at >= start_date)
        if end_date:
            stmt = stmt.where(AuditLog.created_at <= end_date)

        if cursor:
            try:
                parts = cursor.split("|", 1)
                cursor_dt = datetime.fromisoformat(parts[0])
                cursor_id = UUID(parts[1]) if len(parts) > 1 else None
                if cursor_id is not None:
                    stmt = stmt.where(
                        or_(
                            AuditLog.created_at < cursor_dt,
                            and_(
                                AuditLog.created_at == cursor_dt,
                                AuditLog.id < cursor_id,
                            ),
                        )
                    )
                else:
                    stmt = stmt.where(AuditLog.created_at < cursor_dt)
            except (ValueError, IndexError):
                pass

        stmt = stmt.limit(limit + 1)
        result = await self.db.execute(stmt)
        logs = list(result.scalars().all())

        has_more = len(logs) > limit
        if has_more:
            logs = logs[:limit]

        next_cursor = None
        if has_more and logs:
            last = logs[-1]
            next_cursor = f"{last.created_at.isoformat()}|{last.id}"

        return {
            "items": logs,
            "cursor": next_cursor,
            "has_more": has_more,
        }

    async def count_logs(
        self,
        org_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int:
        """Count audit log entries for an org in a time range."""
        stmt = select(func.count(AuditLog.id)).where(AuditLog.org_id == org_id)
        if start_date:
            stmt = stmt.where(AuditLog.created_at >= start_date)
        if end_date:
            stmt = stmt.where(AuditLog.created_at <= end_date)
        result = await self.db.execute(stmt)
        return result.scalar_one()
