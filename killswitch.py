import pathlib, sys

FLAG = pathlib.Path("PAUSE") / "STOP"


def engaged():
    return FLAG.is_file()


def trip(reason=""):
    FLAG.parent.mkdir(parents=True, exist_ok=True)
    FLAG.write_text(reason)

def release():
    FLAG.unlink(missing_ok=True)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "trip":
        trip(" ".join(sys.argv[2:]))
        print("paused")
    elif cmd == "release":
        release()
        print("resumed")
    else:
        print("paused" if engaged() else "running")