"""
Box Archiver for SpectreHUD.
Packs the entire project workspace (notes, state, loot, recon, exploit, reports, screenshots)
into a portable, compressed ZIP archive with sandbox traversal protections.
"""
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from core.logger import get_logger

logger = get_logger("box_archiver")

EXCLUDED_FILENAMES = {".DS_Store", "Thumbs.db"}
EXCLUDED_EXTENSIONS = {".tmp", ".lock"}


class BoxArchiver:
    """Creates compressed .zip archives of project workspaces."""

    @staticmethod
    def archive_project(
        project_dir: Path,
        output_zip: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Compresses all files in project_dir into output_zip.
        Returns dict with keys: 'success', 'zip_path', 'file_count', 'total_bytes', 'compressed_bytes', 'error'.
        """
        proj_path = Path(project_dir).resolve()
        if not proj_path.exists() or not proj_path.is_dir():
            return {
                "success": False,
                "zip_path": None,
                "file_count": 0,
                "total_bytes": 0,
                "compressed_bytes": 0,
                "error": f"Project directory does not exist: {project_dir}"
            }

        if output_zip is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_zip = proj_path.parent / f"{proj_path.name}_archive_{ts}.zip"
        else:
            output_zip = Path(output_zip).resolve()

        if output_zip.suffix.lower() != ".zip":
            output_zip = output_zip.with_suffix(".zip")

        try:
            output_zip.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return {
                "success": False,
                "zip_path": output_zip,
                "file_count": 0,
                "total_bytes": 0,
                "compressed_bytes": 0,
                "error": f"Failed to create output directory: {e}"
            }

        file_count = 0
        total_raw_bytes = 0
        tmp_zip = output_zip.with_name(f".{output_zip.name}.{os.getpid()}.{datetime.now().strftime('%f')}.tmp")

        try:
            with zipfile.ZipFile(tmp_zip, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                for root, dirs, files in os.walk(proj_path):
                    root_path = Path(root).resolve()
                    # Security: Disallow symlink escapes outside project_dir
                    if not root_path.is_relative_to(proj_path):
                        continue

                    # Filter out hidden or excluded files
                    for filename in files:
                        if filename.startswith(".") or filename in EXCLUDED_FILENAMES:
                            continue
                        if any(filename.endswith(ext) for ext in EXCLUDED_EXTENSIONS):
                            continue

                        file_path = root_path / filename
                        # Skip the output zip file itself or temp files
                        if file_path in (output_zip, tmp_zip):
                            continue

                        if file_path.is_file() and not file_path.is_symlink():
                            rel_path = file_path.relative_to(proj_path)
                            arcname = str(Path(proj_path.name) / rel_path)
                            zf.write(file_path, arcname=arcname)
                            file_count += 1
                            total_raw_bytes += file_path.stat().st_size

            # Atomically replace destination with completed tmp archive
            os.replace(tmp_zip, output_zip)
            compressed_size = output_zip.stat().st_size if output_zip.exists() else 0
            logger.info(f"Successfully archived project {proj_path.name} to {output_zip} ({file_count} files, {compressed_size} bytes)")
            return {
                "success": True,
                "zip_path": output_zip,
                "file_count": file_count,
                "total_bytes": total_raw_bytes,
                "compressed_bytes": compressed_size,
                "error": None
            }
        except Exception as e:
            logger.error(f"Failed to archive project {proj_path.name} to {output_zip}: {e}", exc_info=True)
            if tmp_zip.exists():
                try:
                    tmp_zip.unlink()
                except OSError:
                    pass
            return {
                "success": False,
                "zip_path": output_zip,
                "file_count": file_count,
                "total_bytes": total_raw_bytes,
                "compressed_bytes": 0,
                "error": str(e)
            }
