import json
from pathlib import Path
from collections import defaultdict, Counter

def audit():
    catalog_path = Path("data/powers_catalog.json")
    if not catalog_path.exists():
        print("Catalog missing")
        return

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    print(f"Total powers in catalog: {len(catalog)}")

    names = defaultdict(list)
    ids = defaultdict(list)
    repo_counter = Counter()

    for item in catalog:
        pid = item.get("power_id")
        pname = item.get("power_name")
        cat = item.get("category")
        repos = item.get("contributing_repos", [])

        ids[pid].append(pname)
        names[pname].append((pid, cat, repos))

        for r in repos:
            repo_counter[r] += 1

    print("\n--- Duplicate IDs ---")
    dup_ids = {k: v for k, v in ids.items() if len(v) > 1}
    print(f"Found {len(dup_ids)} duplicate IDs: {dup_ids}")

    print("\n--- Duplicate Names ---")
    dup_names = {k: v for k, v in names.items() if len(v) > 1}
    for name, items in dup_names.items():
        print(f"Name '{name}':")
        for it in items:
            print(f"   ID: {it[0]}, Category: {it[1]}, Repos: {it[2]}")

    print("\n--- Repo Contributions ---")
    total_associations = sum(repo_counter.values())
    for r, c in repo_counter.most_common():
        print(f"   {r}: {c}")
    print(f"Total repository associations: {total_associations}")

if __name__ == "__main__":
    audit()
