"""One-time backfill: seed finding_sources from existing findings.source_api."""

from pathlib import Path

from soyscope.config import get_settings
from soyscope.db import Database


def main():
    settings = get_settings()
    db = Database(settings.db_path)
    db.init_schema()

    count = db.backfill_finding_sources()
    print(f"Backfilled {count} finding-source records.")

    stats = db.get_stats()
    print(f"Findings with multiple sources: {stats.get('findings_with_multiple_sources', 0)}")


if __name__ == "__main__":
    main()
