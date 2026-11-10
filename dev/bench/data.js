window.BENCHMARK_DATA = {
  "lastUpdate": 1794299097206,
  "repoUrl": "https://github.com/GaneshNair007/Jarvis",
  "entries": {
    "Benchmark": [
      {
        "commit": {
          "author": {
            "email": "nairganesh134@gmail.com",
            "name": "GaneshNair007",
            "username": "GaneshNair007"
          },
          "committer": {
            "email": "nairganesh134@gmail.com",
            "name": "GaneshNair007",
            "username": "GaneshNair007"
          },
          "distinct": true,
          "id": "c195c973528f35a908ce3392990478014f140961",
          "message": "docs(architecture): apply iteration 2 forensic audit remediations and FreeLLMAPI WAN classification",
          "timestamp": "2026-11-10T13:53:37+05:30",
          "tree_id": "2ae96529d1f516c5605abcd1fae3aff48214d273",
          "url": "https://github.com/GaneshNair007/Jarvis/commit/c195c973528f35a908ce3392990478014f140961"
        },
        "date": 1794299096523,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::test_benchmark_policy_gate_read",
            "value": 751905.7583119037,
            "unit": "iter/sec",
            "range": "stddev: 3.7305221920132737e-7",
            "extra": "mean: 1.3299539057196348 usec\nrounds: 50310"
          },
          {
            "name": "tests/test_benchmarks.py::test_benchmark_policy_gate_destructive_action",
            "value": 198217.32804684015,
            "unit": "iter/sec",
            "range": "stddev: 9.449650575565245e-7",
            "extra": "mean: 5.044967611326559 usec\nrounds: 24947"
          },
          {
            "name": "tests/test_benchmarks.py::test_benchmark_desktop_screen_size",
            "value": 11348864.52112212,
            "unit": "iter/sec",
            "range": "stddev: 9.04483338864135e-9",
            "extra": "mean: 88.11454204421548 nsec\nrounds: 113559"
          },
          {
            "name": "tests/test_benchmarks.py::test_benchmark_audit_hash",
            "value": 12231.10832862227,
            "unit": "iter/sec",
            "range": "stddev: 0.000007981272121829583",
            "extra": "mean: 81.75873952975131 usec\nrounds: 4465"
          }
        ]
      }
    ]
  }
}