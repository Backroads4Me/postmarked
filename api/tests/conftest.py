import os
import tempfile

# app.tasks creates the media directories at import time, defaulting to the
# container path /media. Point them at a writable location so collection works
# on a developer machine and in CI.
os.environ.setdefault(
    "MEDIA_DIR", os.path.join(tempfile.gettempdir(), "postmarked-test-media")
)
