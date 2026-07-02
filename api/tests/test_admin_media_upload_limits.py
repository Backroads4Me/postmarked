from app.routers.admin import media


def test_default_media_upload_limit_is_500_mib():
    assert media.DEFAULT_MAX_UPLOAD_FILE_MIB == 500
    assert media.MAX_UPLOAD_FILE_BYTES == 500 * 1024 * 1024

