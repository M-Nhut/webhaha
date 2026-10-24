"""Local question illustrations: decode raster files and strip metadata."""
import hashlib
import io
from pathlib import Path
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

DIRECTORY = Path(__file__).resolve().parents[1] / 'static/uploads/questions'


def save_question_image(upload):
    raw = upload.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError('Ảnh tối đa 5 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as original:
                if original.format not in ('PNG', 'JPEG', 'WEBP'):
                    raise ValueError('Chỉ nhận ảnh PNG, JPG hoặc WebP.')
                if original.width * original.height > 16_000_000:
                    raise ValueError('Ảnh tối đa 16 triệu điểm ảnh.')
                original.load()
                picture = ImageOps.exif_transpose(original).convert('RGBA')
                stream = io.BytesIO()
                picture.save(stream, format='PNG')
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('Không đọc được ảnh. Hãy chọn ảnh PNG, JPG hoặc WebP hợp lệ.') from exc
    data = stream.getvalue()
    name = 'manual_' + hashlib.sha256(data).hexdigest() + '.png'
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    target = DIRECTORY / name
    if not target.exists(): target.write_bytes(data)
    return '/static/uploads/questions/' + name
