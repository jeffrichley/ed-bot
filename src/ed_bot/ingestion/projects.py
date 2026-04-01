"""Project ingestion: PDFs and code -> markdown."""

import pathlib
import re
from datetime import datetime, timezone


class ProjectIngester:
    """Converts project files (PDFs, Python code) to indexed markdown."""

    def __init__(self, config):
        self.config = config

    def ingest_pdf(self, pdf_path: pathlib.Path, project_name: str | None = None) -> int:
        """Convert a PDF to markdown and save. Returns 1 on success."""
        try:
            from markitdown import MarkItDown
            md_converter = MarkItDown()
            result = md_converter.convert(str(pdf_path))
            md_content = result.text_content
        except Exception:
            # Fallback: read raw text if markitdown fails or has different API
            try:
                md_content = pdf_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                md_content = f"(Could not extract content from {pdf_path.name})"

        name = project_name or pdf_path.stem
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        filename = f"{slug}-requirements.md"

        frontmatter = f"""---
project: "{name}"
type: requirements
source: "{pdf_path.name}"
ingested: {datetime.now(timezone.utc).isoformat()}
---

"""
        output = self.config.projects_dir
        output.mkdir(parents=True, exist_ok=True)
        (output / filename).write_text(frontmatter + md_content, encoding="utf-8")
        return 1

    def ingest_code(self, path: pathlib.Path, project_name: str) -> int:
        """Ingest Python files. Path can be a file or directory."""
        if path.is_file():
            return self._ingest_single_file(path, project_name)

        count = 0
        for py_file in sorted(path.glob("**/*.py")):
            count += self._ingest_single_file(py_file, project_name)
        return count

    def _ingest_single_file(self, py_file: pathlib.Path, project_name: str) -> int:
        code = py_file.read_text(encoding="utf-8")
        slug = re.sub(r"[^a-z0-9]+", "-", project_name.lower()).strip("-")
        filename = f"{slug}-{py_file.stem}.md"

        frontmatter = f"""---
project: "{project_name}"
type: starter-code
file: {py_file.name}
ingested: {datetime.now(timezone.utc).isoformat()}
---

# {py_file.name} (Starter Code)

```python
{code}
```
"""
        output = self.config.projects_dir
        output.mkdir(parents=True, exist_ok=True)
        (output / filename).write_text(frontmatter, encoding="utf-8")
        return 1
