import time 
from contextlib import contextmanager
from loguru import logger

class PerfTester:
    def __init__(self):
        self.metrics = {}

    @contextmanager
    def track(self, name : str):
        logger.info(f"[STARTING]: {name}")
        start = time.perf_counter()
        yield 
        elapesd = time.perf_counter() - start
        self.metrics[name] = elapesd

    def report(self):
        logger.info("[PERFORMANCE SUMMARY]")
        total = 0
        for name, duration in self.metrics.items():
            logger.info(f"{name:<20} | {duration:.4f}s")
            total += duration
        logger.info(f"{'Total Time':<20} | {total:.4f}s")

perftester = PerfTester()