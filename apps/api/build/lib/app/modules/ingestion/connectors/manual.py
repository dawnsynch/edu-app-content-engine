from app.modules.ingestion.connectors.base import ConnectorContext, ConnectorResult


class ManualCourseConnector:
    async def fetch(self, context: ConnectorContext) -> ConnectorResult:
        return ConnectorResult(checkpoint=context.checkpoint, not_modified=True)
