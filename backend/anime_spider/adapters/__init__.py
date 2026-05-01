"""站点适配器导出。"""

from anime_spider.adapters.base import BaseSiteAdapter
from anime_spider.adapters.generic import GenericSiteAdapter
from anime_spider.adapters.maccms import MacCMSAdapter
from anime_spider.adapters.module_theme import ModuleThemeAdapter
from anime_spider.adapters.registry import SiteAdapterRegistry
from anime_spider.adapters.video_info import VideoInfoThemeAdapter

__all__ = [
    'BaseSiteAdapter',
    'GenericSiteAdapter',
    'MacCMSAdapter',
    'ModuleThemeAdapter',
    'SiteAdapterRegistry',
    'VideoInfoThemeAdapter',
]
