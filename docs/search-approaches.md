# SoyScope: blueprint for the definitive industrial soybean research database

**SoyScope can become the most comprehensive industrial-soy research database ever built, but it currently misses approximately 40–60% of relevant global literature.** The biggest gaps are patent literature (hundreds of thousands of soy-related patents worldwide, completely disconnected from academic records), Chinese-language research (CNKI alone holds millions of relevant records that OpenAlex systematically misclassifies), and gray literature from government agencies and trade organizations. Below is a complete, actionable technical blueprint covering 27+ additional databases with API endpoints, a full-text acquisition pipeline, PRISMA-compliant methodology, gap remediation strategies, and a directory of 40+ soy industry organizations — all with specific URLs, Python code patterns, and integration priorities.

---

## 1. Twenty-seven databases SoyScope is missing and how to connect them

### Tier 1 — Free, API-ready, implement immediately

**OSTI.gov** (Office of Scientific and Technical Information) is the single highest-value addition for DOE-funded bioenergy and bio-based materials research. It offers a **free REST API requiring no authentication**:
```python
import requests
url = "https://www.osti.gov/api/v1/records"
params = {"q": "soybean industrial", "rows": 50}
response = requests.get(url, params=params, headers={"Accept": "application/json"})
```
Endpoints span DOE PAGES (journal articles), DOE Patents, DOE Data Explorer, and ETDEWEB (international energy), all at `https://www.osti.gov/api/v1/records`. Returns JSON, XML, or BibTeX. Documentation lives at `https://www.osti.gov/api/v1/docs`.

**USPTO PatentsView API** provides the entire U.S. patent corpus. Register for a free API key at `https://patentsview.org/`, then query `https://search.patentsview.org/api/v1/patent/` with soy-related terms in abstracts. Rate limit is **45 requests/minute**. Bulk download of all U.S. patents as TSV is available at `https://patentsview.org/download/`. The `patent_client` Python library (`pip install patent_client`) wraps this cleanly. License is CC BY 4.0.

**SBIR/STTR Awards Database** tracks every federally funded small business innovation award. The API at `https://api.www.sbir.gov/public/api/awards` is free and keyless. Query `?keyword=soybean&agency=USDA` to find soy innovation projects. Bulk download of all award data (65–290 MB) is available at `https://www.sbir.gov/data-resources` in JSON, XML, or XLS.

**AGRIS (FAO)** at `https://agris.fao.org/` indexes **7+ million multilingual bibliographic records** with particularly strong Global South coverage — critical for Brazilian and Indian soy research invisible to English-language databases. Supports OAI-PMH harvesting and Linked Open Data (RDF/SPARQL). Uses the AGROVOC multilingual thesaurus. Completely free.

**Lens.org** uniquely bridges patent and scholarly literature, linking **200M+ scholarly records** with the global patent dataset. API at `POST https://api.lens.org/patent/search` and `POST https://api.lens.org/scholarly/search` uses Elasticsearch Query DSL. Request a Bearer token through your Lens user profile. Trial access is free for academic/non-commercial use. Lens.org's bidirectional patent-paper citation linking makes it **the single most important tool** for connecting SoyScope's academic records to patent literature.

**USDA ERS** offers formal REST APIs at `https://api.ers.usda.gov/data/arms/` for the Agricultural Resource Management Survey. Register for a free API key at `https://api.data.gov`. The Oil Crops Yearbook and Soybeans & Oil Crops data products are available as CSV downloads from `https://www.ers.usda.gov/data-products/oil-crops-yearbook/`.

### Tier 2 — Free with registration or light scraping required

**EPO Open Patent Services** provides access to **100+ million patent documents** from global offices. Register at `https://developers.epo.org/user/register` (free tier: 4 GB/month). The Python client `python-epo-ops-client` (`pip install python-epo-ops-client`) handles OAuth2 authentication and rate throttling automatically. Query syntax is CQL (e.g., `ti=soybean AND ta=industrial`). Base URL: `https://ops.epo.org/3.2/rest-services/`.

**Google Patents via BigQuery** contains **90+ million publications** from 17 countries with U.S. full text. Query `patents-public-data.patents.publications` table with standard SQL. Free tier provides 1 TB/month of processing. Use `pip install google-cloud-bigquery`. ML embeddings and similarity vectors live in `google_patents_research.publications`.

**NIFA/CRIS Data Gateway** at `https://cris.nifa.usda.gov/` tracks all USDA-funded research projects from FY2002 onward, searchable by Knowledge Area and Subject of Investigation. No formal API exists, but CSV export is available from the search interface. The **NIFA Reporting Portal** at `https://portal.nifa.usda.gov/` provides additional project data.

**USDA BioPreferred Catalog** at `https://www.biopreferred.gov/` contains **2,500+ USDA-certified biobased products** across 109 designated categories — many soy-based (lubricants, solvents, paints, adhesives, cleaners). No API exists; web scraping required. Extremely relevant for mapping the commercial landscape of industrial soy products.

**WIPO PATENTSCOPE** at `https://patentscope.wipo.int/` offers free web search with CSV export of up to **10,000 records per query**. The paid SOAP API costs 2,000 CHF/year; weekly XML bibliographic data costs 400 CHF/year. For cost-effective access, use free web search combined with EPO OPS for detailed patent retrieval.

### Tier 3 — Institutional or paid access

**Scopus API** (Elsevier) at `https://api.elsevier.com/content/` indexes **78+ million items** including conference proceedings. Requires institutional subscription plus API key from `https://dev.elsevier.com/`. The `pybliometrics` Python library (`pip install pybliometrics`) provides clean access. Filter conference proceedings with `DOCTYPE(cp)` in queries. This is the single best source for conference proceeding metadata.

**CAB Abstracts** (CABI) at `https://www.cabidigitallibrary.org/` contains **12+ million records** from 120+ countries in 50 languages, covering agriculture, environment, and food science. Requires institutional subscription via EBSCO or Ovid. Unique value: extensive gray literature and non-English agricultural research unavailable elsewhere.

**IEEE Xplore API** at `https://developer.ieee.org/` provides metadata and abstracts for **6+ million documents** including conference proceedings on bio-based materials and biodiesel processing. Free API key for metadata; full text requires subscription. Python SDK available at `https://developer.ieee.org/Python3_Software_Development_Kit`.

**ProQuest Dissertations & Theses** contains **5+ million dissertations** globally. Institutional subscription required. Alternative free sources: **OATD** (Open Access Theses and Dissertations) at `https://oatd.org/` indexes **6.5+ million ETDs**, and individual university repositories are harvestable via OAI-PMH.

Additional databases worth noting: **DTIC** (Defense Technical Information Center) at `https://discover.dtic.mil/` holds 4.7M+ S&T assets; **NTIS** (National Technical Reports Library) at `https://ntrl.ntis.gov/` holds 3M+ government-funded publications; **FSTA** (Food Science and Technology Abstracts) via EBSCO/Ovid subscription covers food technology applications of soy.

Two soy-specific databases already exist and should be systematically integrated: **soybeanresearchdata.com** (National Soybean Checkoff Research Database, funded by USB, containing checkoff-funded projects from 2008 to present with an "Industrial" category filter) and **soybeanresearchinfo.com** (Soybean Research & Information Network/SRIN, delivering practical summaries of checkoff-funded research).

---

## 2. A pipeline for acquiring full text at scale

### Open access sources provide the foundation

**Unpaywall** remains the starting point for OA discovery. The REST API at `https://api.unpaywall.org/v2/{doi}?email={your_email}` requires only a valid email address and handles ~100,000 calls/day. It indexes **20M+ free scholarly articles** from 50,000+ publishers. Each response includes `best_oa_location.url_for_pdf` and OA status (gold/green/hybrid/bronze/closed). The bulk data snapshot is available to institutions at `https://unpaywall.org/products/snapshot` in JSONL format. As of 2025, Unpaywall runs as a subroutine of the OpenAlex codebase. Python wrapper: `pip install unpywall`.

**PubMed Central's Open Access Subset** is available via FTP at `https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/` in three license tiers: `oa_comm/` (commercial use), `oa_noncomm/` (non-commercial), and `oa_other/`. The file list at `https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_file_list.csv` maps articles to download paths. Coverage exceeds **7.6M research papers**. The BioC API at `https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json/{PMCID}/unicode` returns structured full text as JSON. Also available on AWS S3 for faster retrieval.

**OpenAlex** offers both an API and bulk snapshots. The S3 bucket at `s3://openalex` (free via AWS Open Data, no account needed) contains the entire dataset as gzipped JSON Lines. Download with `aws s3 sync "s3://openalex" "openalex-snapshot" --no-sign-request`. The content endpoint at `https://content.openalex.org/works/{id}.tei.xml` provides parsed TEI XML for open-access works. **240M+ works** indexed, ~50,000 added daily. API rate: 100,000 credits/day with key.

**Semantic Scholar's S2ORC** (Open Research Corpus) offers machine-readable full text parsed from PDFs. Access via the Datasets API at `https://api.semanticscholar.org/datasets/v1/release/latest`. The corpus includes structured full text for millions of OA papers. The bulk search endpoint at `/paper/search/bulk` returns up to **10M results** per query, 1,000 per page. Python package: `pip install semanticscholar`.

**CORE** at `https://api.core.ac.uk/v3/` aggregates **200M+ metadata records** from thousands of open repositories, with extracted full text for many. The API supports queries like `(title: soybean OR soy) AND year >= 2000 AND _exists_:fullText`. The bulk dataset (~300 GB) is available at `https://core.ac.uk/services/dataset`. CORE FastSync provides continuous updates.

### Legal pathways to paywalled content

Text mining is generally considered fair use under U.S. law based on the *Authors Guild v. Google* (2015) precedent establishing that indexing and analyzing text is transformative. The **EU DSM Directive Articles 3–4** provides a mandatory TDM exception for research organizations on lawfully accessed content that cannot be overridden by contract. The *Kneschke v. LAION* ruling (Hamburg, September 2024) confirmed that dataset creation qualifies as TDM under Article 3.

Publisher TDM APIs enable legal bulk access for institutional subscribers:

- **Elsevier** at `https://dev.elsevier.com/`: Register for API key; non-commercial TDM via Full Text API allows bulk XML download at 20,000 records/week
- **Springer Nature** at `https://api.springernature.com`: TDM API with 150 requests/min; subscribing institutions may include TDM rights at no extra cost
- **Wiley** at `https://onlinelibrary.wiley.com/library-info/resources/text-and-data-mining`: Obtain API token via ORCID ID; non-commercial research only
- **Crossref TDM Service**: Cross-publisher full-text link resolution via `https://api.crossref.org/works/{doi}` — free

### Processing downloaded PDFs

**GROBID** is the best-in-class tool for extracting structured metadata from PDFs. Deploy via Docker: `docker pull lfoppiano/grobid:0.8.0`. The Python client (`pip install grobid-client-python`) processes PDFs into TEI XML with 68 fine-grained labels (title, authors, affiliations, sections, references, figures, tables). Reference extraction F1 is approximately **0.87**. GROBID is used in production at Semantic Scholar, ResearchGate, and Internet Archive. LangChain integration is available via `GrobidParser`.

### OAI-PMH for institutional repositories

The **Sickle** Python library (`pip install sickle`) handles OAI-PMH harvesting with automatic resumption token management. Key agricultural repositories to harvest include USDA NAL/AGRICOLA, Iowa State Digital Repository (`https://dr.lib.iastate.edu/`), Purdue e-Pubs, IDEALS (Illinois), and CGIAR repositories. Use OpenDOAR at `https://v2.sherpa.ac.uk/opendoar/` to discover additional soy-relevant repositories worldwide.

---

## 3. Building a PRISMA-compliant database from eight-plus APIs

### Deduplication is the central engineering challenge

The recommended deduplication cascade processes records through five stages of decreasing confidence:

1. **Exact DOI match** after normalization (lowercase, strip URL prefixes, decode percent-encoding, strip trailing punctuation, validate `10.\d{4,}/` format) → confirmed duplicate
2. **Exact PMID/PubMed ID match** → confirmed duplicate
3. **Normalized title exact match** (lowercase, strip all punctuation and whitespace) → confirmed duplicate
4. **Fuzzy title match** (RapidFuzz `token_sort_ratio ≥ 92`) + same publication year + first author last name match → confirmed duplicate
5. **Fuzzy title match** (≥ 85) + same year + same journal → probable duplicate, flag for review

**BibDedupe** (`pip install bib-dedupe`, published in JOSS 2024) is purpose-built for bibliographic record deduplication with a zero-false-positives design goal. It handles author reformatting, journal abbreviation expansion, and title translations. **RapidFuzz** (`pip install rapidfuzz`) provides C++-backed fuzzy string matching that runs **16× faster** than FuzzyWuzzy — essential at the scale SoyScope operates. The **ASySD** tool (BMC Biology 2023) achieves sensitivity of 0.95–0.99 with specificity >0.99 across datasets of up to 79,880 citations.

DOI normalization must handle preprint-vs-published versioning (bioRxiv DOI `10.1101/...` differs from the published version's DOI; Crossref tracks this relationship via `hasPreprint`/`isPrereviewOf` metadata) and supplementary material DOIs (strip supplementary suffixes when matching to parent papers).

### Metadata enrichment fills gaps across sources

Build a cascading enrichment pipeline that queries multiple APIs per record:

| Missing field | Primary source | Fallback |
|---|---|---|
| Abstract | Semantic Scholar, OpenAlex | PubMed, CORE |
| Author ORCIDs | OpenAlex, Crossref | Semantic Scholar |
| Open access URL | Unpaywall | OpenAlex, CORE |
| Citation graph | OpenAlex, Crossref | Semantic Scholar |
| Funding data | OpenAlex, Crossref | — |
| Topics/keywords | OpenAlex (topics) | Semantic Scholar |

Implement a metadata completeness score weighting DOI (3), title (3), authors (2), year (2), abstract (2), journal (1), volume (1), pages (1), keywords (1), and OA URL (1) for a maximum of 17 points. Flag records scoring below 50% for manual review. Use **pyalex** (`pip install pyalex`) for batch DOI lookups (up to 50 DOIs per request) and **habanero** (`pip install habanero`) for Crossref enrichment with polite-pool rate limits.

### PRISMA 2020 and PRISMA-S compliance

PRISMA 2020 (Page et al., 2021, BMJ 372:n71) explicitly supports **"continually updated ('living') systematic reviews"** — directly applicable to SoyScope's living database model. The 27-item checklist requires documenting eligibility criteria, all information sources with access dates, full search strategies, and a flow diagram. Generate flow diagrams using the Shiny app at `https://estech.shinyapps.io/prisma_flowdiagram/`. The PRISMA website with all resources is at `https://www.prisma-statement.org/`.

**PRISMA-S** (Rethlefsen et al., 2021, Systematic Reviews 10(1):39) adds 16 items specifically for search reporting. For each of SoyScope's 8+ databases, document: full API endpoint and parameters, date range applied, language/document-type filters, number of records retrieved, date search was executed, and deduplication method with result counts. Store these as version-controlled YAML files alongside code.

For screening, **ASReview** (`pip install asreview`) provides open-source active learning that reduces screening workload by approximately **95%**. It offers a full Python API for programmatic integration, runs locally for data privacy, and supports flexible AI models including transformer-based classifiers via the `asreview-dory` extension. Published in Nature Machine Intelligence (2021).

### Living review automation

Implement weekly automated searches using OpenAlex's `from_created_date` filter to detect new works. Semantic Scholar's Datasets API supports incremental diffs between releases. PMC's FTP provides daily incrementals. Store SHA-256 hashes of key metadata fields for change detection. Maintain a cumulative PRISMA flow diagram showing records added per update cycle.

---

## 4. Ten gaps a reviewer would target — and how to close each one

### Geographic and language bias are the most damaging gaps

SoyScope's current sources systematically underrepresent the three largest soybean-producing nations after the U.S. **Brazil produces 35% of global soybeans** (163 MMT in 2023) and generates substantial Portuguese-language research on biodiesel and soy polymers visible only in SciELO (`https://scielo.org/`, free API) and BDTD (`https://bdtd.ibict.br/`). **China produces ~5% of global soybeans but files more patents annually than any other country** (1.64 million in 2023 per WIPO). A 2025 JASIST study (Zheng et al., DOI: 10.1002/asi.70013) documented that **OpenAlex suffers from "ingestion instability" for Chinese publications**, with many CNKI papers misidentified in language and affiliation. CNKI (`https://oversea.cnki.net`) indexes 7,200+ core journals and represents an entire parallel research ecosystem largely invisible to SoyScope.

Web of Science indexes **95% English-language publications** versus OpenAlex at approximately 75% (68% upon manual verification per Céspedes et al., 2024). Remediation requires adding CNKI, SciELO, Wanfang Data, J-STAGE (`https://www.jstage.jst.go.jp/`), and Shodhganga (`https://shodhganga.inflibnet.ac.in/`), combined with machine translation via DeepL API (`https://www.deepl.com/pro-api`) or Google Cloud Translation API for batch processing of non-English titles and abstracts.

### Patent-academic disconnect hides the majority of industrial soy innovation

Global patent filings reached **3.55 million in 2023** (WIPO), with Asia accounting for 68.7%. Industrial soy patents span polyols, polyurethanes, biodiesel catalysts, adhesives, lubricants, and polymers — most have no corresponding academic validation papers. **Lens.org is the critical bridge**: it uniquely links 200M+ scholarly records with patent data bidirectionally, allowing discovery of which academic papers are cited in patents and vice versa. PatSeq maps biological sequence patents onto the soybean genome. Integration via `POST https://api.lens.org/patent/search` should be an immediate priority.

### Gray literature represents a hidden knowledge base

Substantial technical information exists in USDA technical reports, EPA documents, DOE research outputs, and land-grant university extension publications that academic databases do not index. Key remediation sources include:

- **USDA PubAg** at `https://pubag.nal.usda.gov/` — full-text USDA articles
- **USDA Ag Data Commons** at `https://data.nal.usda.gov/`
- **NREL Publications** at `https://www.nrel.gov/publications.html` — critical for biofuel/bio-based product reports
- **Science.gov** — federated search across 60+ federal databases
- **eXtension.org** — land-grant university extension resources

### Publication bias inflates efficacy estimates

Statistically significant results are **3× more likely to be published** than null results (BMC Medical Research Methodology, 2009). The pooled odds ratio is 2.8 (95% CI 2.2–3.5) for publication of significant versus non-significant results across 23 cohort studies (Schmucker et al., 2014). For industrial soy, this means systematic overestimation of performance for soy-based lubricants, biodiesel yields, and polymer properties. Mitigation includes monitoring preprint servers (agriRxiv at `https://agrirxiv.org/`, ChemRxiv, bioRxiv), flagging study types in metadata, and tracking USB-funded project protocols alongside published deliverables.

### Temporal gaps erase pre-digital industrial soy history

Henry Ford invested heavily in soybean-based plastics, paints, and car bodies from 1931–1941, including the famous 1941 "Soybean Car." The WWII-era Chemurgy movement produced extensive industrial soy research. Most of this exists only in physical archives. The **SoyInfo Center** at `https://www.soyinfocenter.com/` maintains 80+ book-length bibliographies of historical soybean uses. **HathiTrust** (`https://www.hathitrust.org/`), **Biodiversity Heritage Library** (`https://www.biodiversitylibrary.org/`), and **The Henry Ford Digital Collections** (`https://www.thehenryford.org/collections-and-research/digital-collections/`) contain relevant digitized historical materials.

### Market data and LCA data are entirely absent

The global soy chemicals market reached **$27.9 billion in 2023** (projected $40.1 billion by 2030). The soy-based biodegradable polymer market alone was $132.8 million in 2024. Yet SoyScope contains no market data. Key free sources include: USDA ERS Oil Crops Yearbook, USDA ERS U.S. Bioenergy Statistics, SoyStats at `https://soystats.com/`, and USDA FAS PSD Online at `https://apps.fas.usda.gov/psdonline/` (API available). For LCA data, the **GREET Model** at `https://greet.anl.gov/` (free, from Argonne National Lab) and **U.S. LCI Database** at `https://www.lcacommons.gov/` (free, NREL-managed) provide soybean production and processing lifecycle data. The 2024 USB/NOPA LCA study found a **19% decrease in U.S. soybean carbon footprint** between 2015 and 2021.

---

## 5. Forty-plus soy organizations and their data access points

### Core U.S. organizations with research data

**United Soybean Board** at `https://unitedsoybean.org/` funds checkoff research accessible through the searchable database at `https://www.soybeanresearchdata.com/` (projects from 2008+, filterable by "Industrial" category). The companion site **SoyBiobased.org** at `https://www.soybiobased.org/` specifically tracks industrial soy products in commercial use — tires, foam, paints, lubricants, turf — with a success stories archive. This is arguably the most directly relevant existing resource for SoyScope's mission.

**American Soybean Association** publishes the annual **SoyStats** report at `https://soystats.com/` (2025 PDF: `https://soystats.com/wp-content/uploads/2025Soystats1.pdf`) covering U.S. crush data, biomass-based diesel production, soybean oil production, and world trade statistics. All data sourced from USDA; free PDF and web table access.

**NOPA** (National Oilseed Processors Association) at `https://www.nopa.org/` publishes the monthly crush report covering **95%+ of U.S. soybean crush** with regional breakdowns. Data distributed exclusively via LSEG/Refinitiv ($1,200/year subscription) at `https://www.refinitiv.com/`. Released ~15th of each month at 12:00 PM EST.

**Clean Fuels Alliance America** at `https://cleanfuels.org/` (formerly National Biodiesel Board) publishes economic impact studies ($42.4 billion in 2024 economic activity), health benefits research, and BQ-9000 quality program data. No API; PDF reports and the monthly Clean Fuels Bulletin newsletter.

**AOCS** at `https://www.aocs.org/` publishes JAOCS (ISSN 1558-9331), Lipids, and Journal of Surfactants and Detergents through Wiley at `https://aocs.onlinelibrary.wiley.com/`. The **AOCS Methods database** at `https://library.aocs.org/` contains 400+ analytical methods for oilseeds, oils, fats, soaps, and detergents (subscription required). For SoyScope integration, query JAOCS articles by ISSN through Crossref, Scopus, or OpenAlex APIs; set up Wiley RSS/Atom feeds for new-issue alerts.

### State boards and regional programs

All major state soybean boards' checkoff-funded research is centralized at `https://www.soybeanresearchdata.com/`. The **North Central Soybean Research Program** at `https://ncsrp.com/` coordinates research across 13 states (Illinois, Indiana, Iowa, Kansas, Michigan, Minnesota, Missouri, Nebraska, North Dakota, Ohio, South Dakota, Wisconsin, Pennsylvania) and administers SRIN at `https://soybeanresearchinfo.com/`. Each state board (Illinois Soybean Association at `ilsoy.org`, Iowa Soybean Association at `iasoybeans.com`, Indiana Soybean Alliance at `indianasoybean.com`, Ohio Soybean Council at `soyohio.org`, etc.) feeds into the central database with a consistent searchable interface.

### International organizations with structured data

**ABIOVE** (Brazil) at `https://abiove.org.br/statistics/` publishes monthly supply/demand balance data for the soybean complex, exports data, processing/refining capacity by region, and biodiesel statistics — all publicly downloadable. **SOPA** (India) at `https://sopa.org/statistics/` provides monthly price trends, soybean meal export data by port, and India oilseed production statistics. **FEDIOL** (EU) at `https://www.fediol.eu/` reports monthly EU crush volumes covering ~80% of EU-28 crush capacity. **CIARA-CEC** (Argentina) at `https://www.ciaracec.com.ar/` publishes crush and export estimates (primarily Spanish-language).

For Brazil-specific supply chain traceability, **Trase** at `https://trase.earth/` provides open data with an API mapping soy flows from Brazilian municipalities to export destinations.

### University research centers

**Iowa State's Center for Crops Utilization Research** at `https://ccur.iastate.edu/` (established 1984) and **Iowa Soybean Research Center** at `https://iowasoybeancenter.iastate.edu/` focus specifically on new processes and products from soybeans, including the Biopolymers and Biocomposites Research Team developing biorenewable polymers and plastics. The institutional repository at `https://dr.lib.iastate.edu/` is searchable and OAI-PMH harvestable.

Other key university repositories: Purdue e-Pubs at `https://docs.lib.purdue.edu/`, Missouri MOspace at `https://mospace.umsystem.edu/`, Kansas State KREX at `https://krex.k-state.edu/`, Ohio State Knowledge Bank at `https://kb.osu.edu/`, Illinois IDEALS at `https://www.ideals.illinois.edu/`. The University of Louisville's Conn Center runs a student **Soy Innovation Challenge** at `https://www.conncenter.org/soy-innovation-challenge` for novel industrial soy applications.

### Additional organizations worth monitoring

The **Soy Aquaculture Alliance** at `https://soyaquaculture.com/` funds research on soybean use in aquaculture feed. The **USSEC** at `https://ussec.org/` maintains a resource library of 62+ downloadable guides on soy applications and the International Aquaculture Feed Formulation Database. **Advanced BioFuels USA** at `https://advancedbiofuelsusa.info/` maintains an indexed database of ~50,000 articles on biofuels including soy-based biodiesel. **USDA FAS PSD Online** at `https://apps.fas.usda.gov/psdonline/` provides global production/supply/distribution data with an API.

---

## Recommended technology stack and implementation sequence

The complete Python pipeline should use: `pyalex` + `habanero` + `semanticscholar` for metadata collection; `bib-dedupe` + `rapidfuzz` for deduplication; `unpywall` for OA discovery; `grobid-client-python` for PDF processing; `asreview` for screening; `sickle` for OAI-PMH harvesting; `python-epo-ops-client` for EPO patents; `google-cloud-bigquery` for Google Patents; PostgreSQL for relational storage; and Elasticsearch for full-text search.

```
pip install pyalex habanero semanticscholar rapidfuzz bib-dedupe asreview 
pip install unpywall sickle python-epo-ops-client grobid-client-python
pip install patent-client google-cloud-bigquery recordlinkage nameparser
```

**Implement in this order for maximum impact:**

1. **Week 1–2**: Integrate Lens.org (bridges patent-academic gap), OSTI.gov (free API, DOE research), and SBIR/STTR (free API, innovation tracking)
2. **Week 3–4**: Add PatentsView API + EPO OPS + Google Patents BigQuery for comprehensive patent coverage
3. **Week 5–6**: Integrate AGRIS + SciELO + CNKI access for international/non-English research
4. **Week 7–8**: Build the deduplication pipeline (BibDedupe + RapidFuzz cascade) and metadata enrichment workflow
5. **Week 9–10**: Set up PMC FTP bulk download, Unpaywall-driven OA PDF acquisition, and GROBID processing
6. **Week 11–12**: Deploy publisher TDM APIs (Elsevier, Springer Nature, Wiley), implement PRISMA-S logging, and build the living-review automation with weekly OpenAlex polling

## Conclusion

SoyScope's current eight-source architecture captures perhaps half of the world's industrial soy research. The most consequential additions are **Lens.org** (uniquely bridging patents and papers, free), **CNKI** (unlocking Chinese research invisible to Western databases), **OSTI.gov** (free API covering DOE-funded bioenergy research), and **SciELO** (free access to Brazilian soy research from the world's largest producer). The patent gap alone likely represents hundreds of thousands of relevant documents that describe industrial soy innovations never published in academic journals. A PRISMA-compliant living database methodology — using BibDedupe for deduplication, ASReview for screening, and version-controlled search logs — will satisfy reviewers while enabling the continuous update cycles that a comprehensive industrial soy database demands. The combination of SoyBiobased.org's commercial product tracking, USDA BioPreferred's certified product catalog, GREET's lifecycle data, and the patent corpus would give SoyScope a breadth no existing database approaches.