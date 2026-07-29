"""Serve the compiled Vite shell; assets are handled by WhiteNoise."""
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404


def frontend_index(request):  # pyrefly: ignore[unused-parameter]
    path = Path(settings.FRONTEND_DIST) / "index.html"
    if not path.is_file():
        raise Http404(
            "Frontend bundle not present. Run the Vite dev server locally or "
            "build the production container."
        )
    return FileResponse(path.open("rb"), content_type="text/html")
