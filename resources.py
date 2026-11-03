import pathlib

def lanes(default=3, floor=1, cap=4):
    try:
        for line in pathlib.Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                gb = int(line.split()[1]) / 1048576
                return max(floor, min(cap, int(gb // 1.5)))
    except Exception:
        pass
    return default