"""Seed dummy enrichment data for GUI preview.

Adds fake AI enrichment records, sector/derivative linkages, and OA status
to existing findings so the GUI tabs have something meaningful to display.
"""

import random
import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "soyscope.db"

SECTORS = [
    "Construction & Building Materials",
    "Automotive & Transportation",
    "Packaging & Containers",
    "Textiles & Fibers",
    "Coatings, Paints & Inks",
    "Adhesives & Sealants",
    "Plastics & Bioplastics",
    "Lubricants & Metalworking Fluids",
    "Energy & Biofuels",
    "Chemicals & Solvents",
    "Personal Care & Cosmetics",
    "Cleaning Products & Surfactants",
    "Agriculture",
    "Electronics",
    "Firefighting Foam",
    "Rubber & Elastomers",
]

DERIVATIVES = [
    "Soy Oil",
    "Soy Protein",
    "Soy Meal",
    "Soy Lecithin",
    "Soy Fiber",
    "Soy Wax",
    "Soy Hulls",
    "Soybean Hulls",
    "Soy-based Polyols",
    "Soy Isoflavones",
    "Soy Fatty Acids",
    "Glycerol soy-derived",
    "Soy-based Resins",
    "Whole Soybean",
]

COMMERCIALIZATION_STATUSES = [
    "research", "pilot", "early_commercial", "commercial", "declining",
]

DUMMY_SUMMARIES = [
    "This study demonstrates a novel soy-based polyurethane foam formulation achieving 85% bio-content for automotive seating applications. The material shows comparable mechanical properties to petroleum-based alternatives while reducing VOC emissions by 40%.",
    "Researchers developed a soy protein isolate adhesive for wood composites that exceeds formaldehyde-based adhesive bond strength by 15%. The formulation uses enzymatic cross-linking to achieve water resistance suitable for exterior-grade plywood.",
    "A breakthrough in soy wax coating technology enables fully compostable food packaging with 12-month shelf life. The coating maintains grease resistance at temperatures up to 100C, making it suitable for hot-fill applications.",
    "This patent covers a soy lecithin-based emulsifier system for metalworking fluids that replaces petroleum sulfonates. Field trials show 30% longer tool life and elimination of skin irritation complaints.",
    "Investigation of soy-based polyols in rigid insulation foam shows R-value improvements of 8% over conventional MDI systems. The bio-content reaches 35% while maintaining Class A fire rating.",
    "A new soy fiber reinforced bioplastic composite achieves tensile strength of 45 MPa, suitable for non-structural automotive interior panels. The material is fully recyclable through mechanical grinding.",
    "Development of soy oil-derived alkyd resins for architectural coatings with 70% bio-content. VOC levels meet California AQMD standards while maintaining durability comparable to traditional alkyd paints.",
    "This research presents a soy-based asphalt rejuvenator that extends pavement life by 40%. The bio-oil restores aged asphalt binder properties at 60% lower cost than petroleum-based alternatives.",
    "A soy protein-based fire suppressant foam demonstrates Class B fire knockdown performance equal to PFAS-based AFFF. The formulation is fully biodegradable and shows no bioaccumulation in aquatic testing.",
    "Novel soy isoflavone extraction process yields pharmaceutical-grade genistein at 98% purity for nutraceutical and cosmetic applications. The process uses supercritical CO2, eliminating toxic solvent residues.",
    "Soy meal-derived activated carbon shows heavy metal adsorption capacity 2x higher than coconut shell carbon. The material is cost-effective for industrial wastewater treatment at scale.",
    "Bio-based hydraulic fluid from soy fatty acid esters demonstrates superior performance in cold-weather applications down to -40C. Biodegradability reaches 95% within 28 days under OECD 301B testing.",
    "Research on soy-based printing inks for flexographic packaging shows improved color density and reduced set-off compared to mineral oil inks. The inks enable easier deinking for paper recycling.",
    "A soy glycerol-derived plasticizer for PVC shows migration resistance 3x better than DEHP while maintaining flexibility at low temperatures. The material meets EU REACH and FDA food contact requirements.",
    "Development of soy hull nanocellulose as reinforcing filler in natural rubber compounds. Tear strength improves 25% while maintaining elongation, targeting tire sidewall applications.",
    "Soy-based surfactants for enhanced oil recovery demonstrate 15% improvement in displacement efficiency compared to petroleum sulfonates in sandstone reservoir simulations.",
    "A novel soy protein film with antimicrobial properties extends fresh produce shelf life by 5 days. The edible coating incorporates thyme essential oil encapsulated in soy lecithin liposomes.",
    "Research demonstrates soy-based polyester resin for fiberglass composites achieving 60% bio-content. Mechanical properties meet ASTM standards for wind turbine blade manufacturing.",
    "Soy wax-based phase change materials for thermal energy storage show latent heat capacity of 180 J/g, suitable for building temperature regulation and reducing HVAC energy consumption by 20%.",
    "This study validates soy oil epoxidation for reactive diluents in epoxy flooring systems. The product reduces viscosity 40% while maintaining chemical resistance to industrial solvents.",
]

SOY_ADVANTAGES = [
    "Renewable feedstock with established agricultural supply chain; 35% lower carbon footprint than petroleum alternative.",
    "Abundant domestic supply reduces import dependency; price stability from soybean commodity market hedging.",
    "Biodegradable end product eliminates disposal concerns; compostable within 90 days under industrial conditions.",
    "Non-toxic formulation enables food-contact applications; eliminates worker exposure to hazardous chemicals.",
    "Lower processing temperatures reduce energy costs by 25%; compatible with existing manufacturing equipment.",
    "Soy-based material achieves equivalent performance at 20% lower material cost due to agricultural subsidies and scale.",
    "Regulatory advantage: meets emerging bio-based content requirements in government procurement (USDA BioPreferred).",
    "Multi-functional properties reduce additive package complexity; single material replaces 3 petroleum-derived components.",
    "Consumer preference for bio-based products commands 10-15% price premium in retail markets.",
    "Waste valorization: uses soy processing byproducts that would otherwise require disposal, creating new revenue streams.",
]

BARRIERS = [
    "Scale-up challenges: batch-to-continuous process transition requires $2-5M capital investment.",
    "Supply chain variability: soy crop quality fluctuates with weather, affecting product consistency.",
    "Regulatory timeline: FDA food contact approval process takes 18-24 months for novel formulations.",
    "Performance gap in extreme conditions: bio-based material degrades above 150C vs 200C for petroleum alternative.",
    "Price competitiveness depends on petroleum prices; at <$50/bbl oil, soy alternative loses cost advantage.",
    "Limited awareness among end-users; requires significant marketing investment to shift purchasing decisions.",
    "Allergen labeling requirements restrict use in some consumer product categories.",
    "Shelf life limitations: bio-based formulation requires cold chain storage, increasing logistics costs.",
    "Competition from other bio-based feedstocks (palm, castor) with lower costs in tropical regions.",
    "Intellectual property landscape is crowded; freedom to operate analysis needed before commercialization.",
]


def seed_data():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Get sector IDs
    sector_rows = conn.execute("SELECT id, name FROM sectors").fetchall()
    sector_map = {r["name"]: r["id"] for r in sector_rows}
    print(f"Found {len(sector_map)} sectors")

    # Get derivative IDs
    deriv_rows = conn.execute("SELECT id, name FROM derivatives").fetchall()
    deriv_map = {r["name"]: r["id"] for r in deriv_rows}
    print(f"Found {len(deriv_map)} derivatives")

    # Get all finding IDs
    finding_rows = conn.execute(
        "SELECT id, title, source_api, year FROM findings ORDER BY id"
    ).fetchall()
    finding_ids = [r["id"] for r in finding_rows]
    print(f"Found {len(finding_ids)} findings")

    # Check existing enrichments
    existing_enriched = conn.execute("SELECT COUNT(*) FROM enrichments").fetchone()[0]
    print(f"Existing enrichments: {existing_enriched}")

    if existing_enriched > 0:
        print("Enrichments already exist, skipping enrichment seeding.")
    else:
        # Seed enrichments for ~300 findings (mix of USB deliverables and checkoff)
        random.seed(42)  # Reproducible
        sample_size = min(300, len(finding_ids))
        enrichment_ids = random.sample(finding_ids, sample_size)

        enrichments_inserted = 0
        for fid in enrichment_ids:
            tier = random.choices(
                ["catalog", "summary", "deep"],
                weights=[0.5, 0.35, 0.15],
            )[0]
            trl = random.randint(1, 9)
            novelty = round(random.betavariate(2, 5) * 0.6 + 0.3, 3)  # 0.3-0.9 range
            status = random.choice(COMMERCIALIZATION_STATUSES)
            summary = random.choice(DUMMY_SUMMARIES)
            advantage = random.choice(SOY_ADVANTAGES)
            barrier = random.choice(BARRIERS)

            key_metrics = {
                "bio_content_pct": random.randint(20, 95),
                "cost_reduction_pct": random.randint(5, 40),
                "performance_vs_baseline": round(random.uniform(0.8, 1.3), 2),
            }
            key_players = random.sample(
                ["Cargill", "ADM", "Bunge", "DuPont", "BASF", "Dow",
                 "Solvay", "Evonik", "Covestro", "Huntsman",
                 "Missouri Soybean Board", "Iowa State University",
                 "Purdue University", "USDA ARS", "Battelle"],
                k=random.randint(2, 4),
            )

            conn.execute(
                """INSERT OR IGNORE INTO enrichments
                   (finding_id, tier, trl_estimate, commercialization_status,
                    novelty_score, ai_summary, key_metrics, key_players,
                    soy_advantage, barriers, model_used)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (fid, tier, trl, status, novelty,
                 summary, json.dumps(key_metrics), json.dumps(key_players),
                 advantage, barrier, "dummy-seed-v1"),
            )
            enrichments_inserted += 1

        conn.commit()
        print(f"Inserted {enrichments_inserted} enrichment records")

    # Seed sector-derivative linkages for ~2000 findings
    existing_fs = conn.execute("SELECT COUNT(*) FROM finding_sectors").fetchone()[0]
    print(f"Existing finding_sectors: {existing_fs}")

    if existing_fs > 0:
        print("Sector linkages exist, skipping.")
    else:
        random.seed(123)
        link_sample = min(2000, len(finding_ids))
        link_ids = random.sample(finding_ids, link_sample)

        sector_names = list(sector_map.keys())
        deriv_names = list(deriv_map.keys())

        fs_count = 0
        fd_count = 0
        for fid in link_ids:
            # 1-3 sectors per finding
            n_sectors = random.choices([1, 2, 3], weights=[0.5, 0.35, 0.15])[0]
            chosen_sectors = random.sample(sector_names, min(n_sectors, len(sector_names)))
            for sname in chosen_sectors:
                sid = sector_map[sname]
                conf = round(random.uniform(0.6, 1.0), 2)
                conn.execute(
                    "INSERT OR IGNORE INTO finding_sectors (finding_id, sector_id, confidence) VALUES (?, ?, ?)",
                    (fid, sid, conf),
                )
                fs_count += 1

            # 1-2 derivatives per finding
            n_derivs = random.choices([1, 2], weights=[0.6, 0.4])[0]
            chosen_derivs = random.sample(deriv_names, min(n_derivs, len(deriv_names)))
            for dname in chosen_derivs:
                did = deriv_map[dname]
                conf = round(random.uniform(0.6, 1.0), 2)
                conn.execute(
                    "INSERT OR IGNORE INTO finding_derivatives (finding_id, derivative_id, confidence) VALUES (?, ?, ?)",
                    (fid, did, conf),
                )
                fd_count += 1

        conn.commit()
        print(f"Inserted {fs_count} finding-sector links, {fd_count} finding-derivative links")

    # Update some findings with OA status
    existing_oa = conn.execute(
        "SELECT COUNT(*) FROM findings WHERE open_access_status IS NOT NULL AND open_access_status != ''"
    ).fetchone()[0]
    print(f"Existing findings with OA status: {existing_oa}")

    if existing_oa < 100:
        random.seed(456)
        oa_sample = random.sample(finding_ids, min(1500, len(finding_ids)))
        oa_statuses = ["gold", "green", "bronze", "hybrid", "closed"]
        oa_weights = [0.15, 0.2, 0.1, 0.1, 0.45]

        for fid in oa_sample:
            oa = random.choices(oa_statuses, weights=oa_weights)[0]
            conn.execute(
                "UPDATE findings SET open_access_status = ? WHERE id = ?",
                (oa, fid),
            )
        conn.commit()
        print(f"Updated {len(oa_sample)} findings with OA status")

    # Final stats check
    stats = {}
    stats["enrichments"] = conn.execute("SELECT COUNT(*) FROM enrichments").fetchone()[0]
    stats["finding_sectors"] = conn.execute("SELECT COUNT(*) FROM finding_sectors").fetchone()[0]
    stats["finding_derivatives"] = conn.execute("SELECT COUNT(*) FROM finding_derivatives").fetchone()[0]
    stats["oa_findings"] = conn.execute(
        "SELECT COUNT(*) FROM findings WHERE open_access_status IS NOT NULL AND open_access_status != ''"
    ).fetchone()[0]
    stats["matrix_cells"] = conn.execute(
        """SELECT COUNT(DISTINCT s.name || '|' || d.name)
           FROM finding_sectors fs
           JOIN sectors s ON fs.sector_id = s.id
           JOIN finding_derivatives fd ON fs.finding_id = fd.finding_id
           JOIN derivatives d ON fd.derivative_id = d.id"""
    ).fetchone()[0]

    conn.close()

    print("\n=== SEED COMPLETE ===")
    for k, v in stats.items():
        print(f"  {k}: {v:,}")


if __name__ == "__main__":
    seed_data()
