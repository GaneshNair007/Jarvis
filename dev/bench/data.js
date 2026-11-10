window.BENCHMARK_DATA = {
  "lastUpdate": 1794292968829,
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
          "id": "8ef33b68e510d7a09d416cf425a27902a7c6c350",
          "message": "fix(ci): install libportaudio2 on Ubuntu, add sounddevice dependency and PortAudio test guards",
          "timestamp": "2026-11-10T12:11:28+05:30",
          "tree_id": "46e64d62e637c79edd7bd646d8c22aa2a3e72ad4",
          "url": "https://github.com/GaneshNair007/Jarvis/commit/8ef33b68e510d7a09d416cf425a27902a7c6c350"
        },
        "date": 1794292967643,
        "tool": "pytest",
        "benches": [
          {
            "name": "tests/test_benchmarks.py::test_benchmark_policy_gate_read",
            "value": 748991.9031181191,
            "unit": "iter/sec",
            "range": "stddev: 3.780515493206491e-7",
            "extra": "mean: 1.335127917721022 usec\nrounds: 61993"
          },
          {
            "name": "tests/test_benchmarks.py::test_benchmark_policy_gate_destructive_action",
            "value": 201233.4659941309,
            "unit": "iter/sec",
            "range": "stddev: 8.716765109551191e-7",
            "extra": "mean: 4.969352364229346 usec\nrounds: 31300"
          },
          {
            "name": "tests/test_benchmarks.py::test_benchmark_desktop_screen_size",
            "value": 11551034.527921468,
            "unit": "iter/sec",
            "range": "stddev: 7.996186662806086e-9",
            "extra": "mean: 86.57233233808641 nsec\nrounds: 113174"
          },
          {
            "name": "tests/test_benchmarks.py::test_benchmark_audit_hash",
            "value": 12440.346156980388,
            "unit": "iter/sec",
            "range": "stddev: 0.000006230720146338378",
            "extra": "mean: 80.38361532559857 usec\nrounds: 5220"
          }
        ]
      }
    ]
  }
}