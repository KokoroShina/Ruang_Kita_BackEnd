"""Endpoint upload gambar untuk konten & topik (admin, hybrid URL/upload).

Admin bisa memakai URL eksternal (mis. thumbnail YouTube) LANGSUNG di field
image_url — upload ini opsi lanjutan bila gambar cuma ada di perangkat.
File disimpan ke <MEDIA_DIR>/uploads dan dikembalikan path publiknya
(/media/uploads/<file>) untuk diisi ke image_url.
"""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.dependencies import AdminUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["uploads"])


@router.post(
    "/admin/uploads/image",
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Upload gambar thumbnail/cover",
)
async def admin_upload_image(
    admin: AdminUser,
    file: UploadFile,
) -> dict[str, str]:
    allowed = settings.UPLOAD_ALLOWED_TYPES
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Tipe file tidak didukung. Gunakan: "
                + ", ".join(sorted(allowed.keys()))
            ),
        )

    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Berkas kosong.",
        )
    if len(data) > settings.UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Ukuran gambar maksimal 5 MB.",
        )

    ext = allowed[file.content_type]
    # Nama acak — tidak mempercayai nama file dari klien (path traversal safe)
    filename = f"{uuid.uuid4().hex}{ext}"
    upload_dir = Path(settings.MEDIA_DIR) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / filename).write_bytes(data)

    public_path = f"/media/uploads/{filename}"
    logger.info("Admin %s mengunggah gambar -> %s", admin.email, public_path)
    return {"image_url": public_path}
