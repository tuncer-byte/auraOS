"""In-process metrics: counter / gauge / histogram + Prometheus exposition.

Kütüphane bağımlılığı eklemek istemediğimiz için kendi minimal metrics registry'mizi
yazıyoruz. Prometheus scrape eden ortamda `render_prometheus()` çıktısı
text/plain `0.0.4` formatına uyumludur.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable


def _labels_key(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    if not labels:
        return ()
    return tuple(sorted(labels.items()))


def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{v}"' for k, v in labels)
    return "{" + inner + "}"


@dataclass
class Counter:
    name: str
    help: str = ""
    _values: dict[tuple, float] = field(default_factory=lambda: defaultdict(float))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def inc(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            self._values[_labels_key(labels)] += amount

    def value(self, labels: dict[str, str] | None = None) -> float:
        return self._values.get(_labels_key(labels), 0.0)


@dataclass
class Gauge:
    name: str
    help: str = ""
    _values: dict[tuple, float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            self._values[_labels_key(labels)] = value


@dataclass
class Histogram:
    name: str
    help: str = ""
    buckets: tuple[float, ...] = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    _data: dict[tuple, dict] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        key = _labels_key(labels)
        with self._lock:
            d = self._data.setdefault(key, {"count": 0, "sum": 0.0, "buckets": [0] * len(self.buckets)})
            d["count"] += 1
            d["sum"] += value
            for i, b in enumerate(self.buckets):
                if value <= b:
                    d["buckets"][i] += 1


class MetricsRegistry:
    def __init__(self) -> None:
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._lock = threading.Lock()

    def counter(self, name: str, help: str = "") -> Counter:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name=name, help=help)
            return self._counters[name]

    def gauge(self, name: str, help: str = "") -> Gauge:
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name=name, help=help)
            return self._gauges[name]

    def histogram(self, name: str, help: str = "", buckets: Iterable[float] | None = None) -> Histogram:
        with self._lock:
            if name not in self._histograms:
                kwargs = {"name": name, "help": help}
                if buckets is not None:
                    kwargs["buckets"] = tuple(buckets)
                self._histograms[name] = Histogram(**kwargs)
            return self._histograms[name]

    def render_prometheus(self) -> str:
        out: list[str] = []
        for c in self._counters.values():
            if c.help:
                out.append(f"# HELP {c.name} {c.help}")
            out.append(f"# TYPE {c.name} counter")
            for labels, val in c._values.items():
                out.append(f"{c.name}{_format_labels(labels)} {val}")
        for g in self._gauges.values():
            if g.help:
                out.append(f"# HELP {g.name} {g.help}")
            out.append(f"# TYPE {g.name} gauge")
            for labels, val in g._values.items():
                out.append(f"{g.name}{_format_labels(labels)} {val}")
        for h in self._histograms.values():
            if h.help:
                out.append(f"# HELP {h.name} {h.help}")
            out.append(f"# TYPE {h.name} histogram")
            for labels, d in h._data.items():
                cum = 0
                for i, b in enumerate(h.buckets):
                    cum += d["buckets"][i] - (d["buckets"][i - 1] if i > 0 else 0)
                    lk = labels + (("le", str(b)),)
                    out.append(f"{h.name}_bucket{_format_labels(lk)} {d['buckets'][i]}")
                lk_inf = labels + (("le", "+Inf"),)
                out.append(f"{h.name}_bucket{_format_labels(lk_inf)} {d['count']}")
                out.append(f"{h.name}_sum{_format_labels(labels)} {d['sum']}")
                out.append(f"{h.name}_count{_format_labels(labels)} {d['count']}")
        return "\n".join(out) + "\n"


METRICS = MetricsRegistry()


class Timer:
    """`with Timer(hist, labels=...): ...` — süreyi histogram'a yazar."""

    def __init__(self, hist: Histogram, labels: dict[str, str] | None = None) -> None:
        self.hist = hist
        self.labels = labels
        self.start = 0.0

    def __enter__(self) -> "Timer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *exc) -> None:
        self.hist.observe(time.perf_counter() - self.start, self.labels)
