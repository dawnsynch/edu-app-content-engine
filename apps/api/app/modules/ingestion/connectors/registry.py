import httpx

from app.core.settings import Settings
from app.modules.ingestion.connectors.base import Connector
from app.modules.ingestion.connectors.cms import OwnedCmsConnector
from app.modules.ingestion.connectors.errors import PermanentConnectorError
from app.modules.ingestion.connectors.manual import ManualCourseConnector
from app.modules.ingestion.connectors.rss import RssAtomConnector
from app.modules.ingestion.connectors.youtube import YouTubeConnector
from app.modules.sources.enums import SourceType


class ConnectorRegistry:
    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._connectors: dict[SourceType, Connector] = {
            SourceType.RSS: RssAtomConnector(client),
            SourceType.OWNED_CMS: OwnedCmsConnector(client),
            SourceType.YOUTUBE: YouTubeConnector(client, settings.youtube_api_key),
            SourceType.COURSE_PROVIDER: ManualCourseConnector(),
        }

    def get(self, source_type: str) -> Connector:
        try:
            kind = SourceType(source_type)
        except ValueError as exc:
            raise PermanentConnectorError(f"unsupported source type: {source_type}") from exc
        connector = self._connectors.get(kind)
        if connector is None:
            raise PermanentConnectorError(f"no approved connector for source type: {source_type}")
        return connector
