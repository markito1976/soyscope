"""Quick data quality check for SoyScope DB."""
import sqlite3

conn = sqlite3.connect("data/soyscope.db")
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM findings")
total = c.fetchone()[0]

c.execute("SELECT status, COUNT(*) FROM search_checkpoints GROUP BY status")
checkpoints = c.fetchall()

c.execute("SELECT COUNT(*) FROM findings WHERE title IS NOT NULL AND title <> ''")
with_title = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM findings WHERE abstract IS NOT NULL AND abstract <> ''")
with_abstract = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM findings WHERE doi IS NOT NULL AND doi <> ''")
with_doi = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM findings WHERE year IS NOT NULL")
with_year = c.fetchone()[0]

c.execute("SELECT source_api, COUNT(*) FROM finding_sources GROUP BY source_api ORDER BY COUNT(*) DESC")
sources = c.fetchall()

c.execute("SELECT year, COUNT(*) FROM findings WHERE year IS NOT NULL GROUP BY year ORDER BY year")
years = c.fetchall()

c.execute("SELECT title, doi, year, length(abstract) as alen FROM findings ORDER BY rowid DESC LIMIT 10")
recent = c.fetchall()

print("=== OVERALL ===")
print(f"Total findings: {total}")
if total > 0:
    print(f"With title:    {with_title:>6} ({100*with_title/total:.1f}%)")
    print(f"With abstract: {with_abstract:>6} ({100*with_abstract/total:.1f}%)")
    print(f"With DOI:      {with_doi:>6} ({100*with_doi/total:.1f}%)")
    print(f"With year:     {with_year:>6} ({100*with_year/total:.1f}%)")
print()
print("=== CHECKPOINT PROGRESS ===")
for status, count in checkpoints:
    print(f"  {status}: {count}")
print()
print("=== SOURCE DISTRIBUTION ===")
for src, cnt in sources:
    print(f"  {src:>20}: {cnt}")
print()
print("=== YEAR DISTRIBUTION ===")
for yr, cnt in years:
    print(f"  {yr}: {cnt}")
print()
print("=== RECENT 10 FINDINGS (quality sample) ===")
for t, d, y, a in recent:
    title = (t or "NO TITLE")[:90]
    print(f"  [{y}] {title}")
    print(f"       DOI: {d or 'NONE'}  |  Abstract: {a or 0} chars")

conn.close()
