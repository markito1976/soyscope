import sqlite3
conn = sqlite3.connect('C:/EvalToolVersions/soy-industrial-tracker/data/soyscope.db')
print('=== CURRENT DATA STATE ===')
print('Total findings:', conn.execute('SELECT COUNT(*) FROM findings').fetchone()[0])
print('With DOI:', conn.execute("SELECT COUNT(*) FROM findings WHERE doi IS NOT NULL").fetchone()[0])
print('With pdf_url:', conn.execute("SELECT COUNT(*) FROM findings WHERE pdf_url IS NOT NULL AND pdf_url != ''").fetchone()[0])
print('With OA status:', conn.execute("SELECT COUNT(*) FROM findings WHERE open_access_status IS NOT NULL AND open_access_status != ''").fetchone()[0])
print()
print('Source breakdown:')
for r in conn.execute("""
    SELECT source_api, COUNT(*) as total,
           SUM(CASE WHEN doi IS NOT NULL THEN 1 ELSE 0 END) as with_doi,
           SUM(CASE WHEN pdf_url IS NOT NULL AND pdf_url != '' THEN 1 ELSE 0 END) as with_pdf,
           SUM(CASE WHEN open_access_status IS NOT NULL AND open_access_status != '' THEN 1 ELSE 0 END) as with_oa
    FROM findings GROUP BY source_api ORDER BY total DESC
""").fetchall():
    print(f'  {r[0]}: {r[1]} total | {r[2]} DOI | {r[3]} PDF | {r[4]} OA')

print()
print('=== FINDINGS WITH DOI BUT NO PDF ===')
row = conn.execute("SELECT COUNT(*) FROM findings WHERE doi IS NOT NULL AND (pdf_url IS NULL OR pdf_url = '')").fetchone()
print(f'  {row[0]} findings have DOI but no PDF URL (can be resolved via Unpaywall)')

print()
print('=== FINDINGS WITHOUT DOI ===')
row = conn.execute("SELECT COUNT(*) FROM findings WHERE doi IS NULL").fetchone()
print(f'  {row[0]} findings have no DOI (cannot resolve via Unpaywall)')

print()
print('=== UNIQUE DOI COUNT ===')
row = conn.execute("SELECT COUNT(DISTINCT doi) FROM findings WHERE doi IS NOT NULL").fetchone()
print(f'  {row[0]} unique DOIs')
conn.close()
