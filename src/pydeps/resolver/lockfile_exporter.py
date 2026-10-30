"""Exporter for resolved lockfiles, pinned requirements.txt, and structured resolution JSON."""

from __future__ import annotations

from pathlib import Path

from pydeps.models.dependencies import ResolutionMode, ResolutionResult


class LockfileExporter:
    """Exports resolution outputs (uv.lock, requirements.txt, structured JSON) safely to disk."""

    @staticmethod
    def export(
        result: ResolutionResult,
        output_dir: Path | str,
        overwrite: bool = False,
    ) -> list[str]:
        """Write resolution outputs to the target directory.

        Returns the list of created file paths.
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        created_files: list[str] = []

        if result.mode == ResolutionMode.UNIVERSAL:
            # 1. Export native uv.lock if available
            if result.lockfile_content:
                lock_file = out_path / "uv.lock"
                if not lock_file.exists() or overwrite:
                    lock_file.write_text(result.lockfile_content, encoding="utf-8")
                    created_files.append(str(lock_file))

            # 2. Export requirements.txt
            if result.requirements_txt:
                req_file = out_path / "requirements.txt"
                if not req_file.exists() or overwrite:
                    req_file.write_text(result.requirements_txt, encoding="utf-8")
                    created_files.append(str(req_file))

            # 3. Export resolution.json
            res_json = out_path / "resolution.json"
            if not res_json.exists() or overwrite:
                res_json.write_text(result.model_dump_json(indent=2), encoding="utf-8")
                created_files.append(str(res_json))

        else:
            # Per-target mode
            # Root resolution summary JSON
            res_json = out_path / "resolution_summary.json"
            if not res_json.exists() or overwrite:
                res_json.write_text(result.model_dump_json(indent=2), encoding="utf-8")
                created_files.append(str(res_json))

            # Per-target subdirectories
            for target_tag, sub_result in result.per_target_results.items():
                target_sub = out_path / target_tag
                target_sub.mkdir(parents=True, exist_ok=True)

                if hasattr(sub_result, "requirements_txt") and sub_result.requirements_txt:
                    t_req = target_sub / "requirements.txt"
                    if not t_req.exists() or overwrite:
                        t_req.write_text(sub_result.requirements_txt, encoding="utf-8")
                        created_files.append(str(t_req))

                t_json = target_sub / "resolution.json"
                if not t_json.exists() or overwrite:
                    dump = (
                        sub_result.model_dump_json(indent=2)
                        if hasattr(sub_result, "model_dump_json")
                        else str(sub_result)
                    )
                    t_json.write_text(dump, encoding="utf-8")
                    created_files.append(str(t_json))

        return created_files
