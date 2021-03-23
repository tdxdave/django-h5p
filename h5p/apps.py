from pathlib import Path
from django.apps import AppConfig
from django.conf import settigs

class H5PConfig(AppConfig):
    name = 'h5p'

    CONTENT_DIR = settings.MEDIA_ROOT / "xapi"

    def ready(self):
        if not CONTENT_DIR.exists():
            CONTENT_DIR.mkdir(parents=True, exist_ok=True)