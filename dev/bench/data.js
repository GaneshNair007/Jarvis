window.BENCHMARK_DATA = {
  "lastUpdate": 1794292628893,
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
          "id": "a75aede7f15dafd7db10174850cae9396822829e",
          "message": "fix(ci): resolve Linux runner platform disparities, missing PDF dependencies, and audio/powershell hardware guards",
          "timestamp": "2026-11-10T12:05:39+05:30",
          "tree_id": "8a12735fe6ebb0fc5a88a791cc3272cf402b4716",
          "url": "https://github.com/GaneshNair007/Jarvis/commit/a75aede7f15dafd7db10174850cae9396822829e"
        },
        "date": 1794292627959,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::test_benchmark_policy_gate_read",
            "value": 740523.4746023791,
            "unit": "iter/sec",
            "range": "stddev: 4.2446091522875026e-7",
            "extra": "mean: 1.350396083712195 usec\nrounds: 62661"
          },
          {
            "name": "tests/test_benchmarks.py::test_benchmark_policy_gate_destructive_action",
            "value": 199500.33454297224,
            "unit": "iter/sec",
            "range": "stddev: 8.391381860055031e-7",
            "extra": "mean: 5.0125229227853785 usec\nrounds: 30450"
          },
          {
            "name": "tests/test_benchmarks.py::test_benchmark_desktop_screen_size",
            "value": 11425431.489289084,
            "unit": "iter/sec",
            "range": "stddev: 7.896875177382135e-9",
            "extra": "mean: 87.52404676688644 nsec\nrounds: 115381"
          },
          {
            "name": "tests/test_benchmarks.py::test_benchmark_audit_hash",
            "value": 12630.145871031784,
            "unit": "iter/sec",
            "range": "stddev: 0.000006635826038219563",
            "extra": "mean: 79.17564929266393 usec\nrounds: 5372"
          }
        ]
      }
    ]
  }
}