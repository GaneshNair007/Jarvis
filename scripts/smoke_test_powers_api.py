"""
End-to-End Smoke Test for JARVIS Powers API & Multi-Repo Ecosystem
Performs full ASGI verification across all 11 repositories.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from jarvis.api.server import app

def run_smoke_test():
    client = TestClient(app)
    print("=== JARVIS Powers API End-to-End Smoke Test ===")

    # 1. Call /api/v1/powers/ecosystem
    print("\n[Step 1] Calling GET /api/v1/powers/ecosystem...")
    res = client.get("/api/v1/powers/ecosystem")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    eco_data = res.json()
    print(f"Formula: {eco_data['formula']}")
    print(f"Total Powers: {eco_data['total_powers']}")
    print(f"Total Repositories: {eco_data['total_repositories']}")
    assert eco_data["total_powers"] == 355
    assert eco_data["total_repositories"] == 11

    # 2. Call /api/v1/powers
    print("\n[Step 2] Calling GET /api/v1/powers...")
    res = client.get("/api/v1/powers")
    assert res.status_code == 200
    powers_data = res.json()
    total = powers_data["total_powers"]
    count = len(powers_data["powers"])
    print(f"Total Powers reported: {total}, Items returned: {count}")
    assert total == 355
    assert count == 355

    # 3. Select at least one power from each of the 11 repositories
    print("\n[Step 3 & 4] Verifying at least one power from each of the 11 repositories:")
    repos = list(eco_data["repositories"].keys())
    assert len(repos) == 11

    for r in sorted(repos):
        sample_pids = eco_data["repositories"][r]["sample_powers"]
        assert len(sample_pids) > 0, f"No sample powers for {r}"
        sample_pid = sample_pids[0]

        # Call /api/v1/powers/{id}
        res_power = client.get(f"/api/v1/powers/{sample_pid}")
        assert res_power.status_code == 200, f"Failed lookup for {sample_pid} ({r})"
        p_detail = res_power.json()

        # Validate attribution and metadata
        assert p_detail["power_id"] == sample_pid
        assert p_detail["power_name"]
        assert p_detail["category"]
        assert p_detail["slug"]
        assert r in p_detail["contributing_repos"]
        assert p_detail["status"] in ["executable", "requires_configuration", "reference_only"]
        assert p_detail["execution_handler"]
        
        print(f"  [OK] [{r:16s}] -> {sample_pid}: {p_detail['power_name'][:30]:30s} | Status: {p_detail['status']:22s} | Handler: {p_detail['execution_handler']}")

    # 4. Verify invalid power lookup
    print("\n[Step 5] Verifying 404 behavior for invalid power ID...")
    res_404 = client.get("/api/v1/powers/PWR-INVALID-999")
    assert res_404.status_code == 404
    print("  [OK] Nonexistent ID correctly returns 404")

    # 5. Verify case-insensitivity and slug lookup
    print("\n[Step 6] Verifying slug and case-insensitivity...")
    res_lower = client.get("/api/v1/powers/pwr-001")
    assert res_lower.status_code == 200
    assert res_lower.json()["power_id"] == "PWR-001"
    res_slug = client.get("/api/v1/powers/wake-word-activation")
    assert res_slug.status_code == 200
    assert res_slug.json()["power_id"] == "PWR-001"
    print("  [OK] Lowercase ID and slug lookups resolve accurately")

    print("\n=== SMOKE TEST RESULT: 100% PASS ===")
    return 0

if __name__ == "__main__":
    sys.exit(run_smoke_test())
