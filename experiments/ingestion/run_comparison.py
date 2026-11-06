"""Run already-built local parser images sequentially and preserve evidence."""

import argparse
import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


PARSERS = {
    "liteparse": ("folio-liteparse:2.18.0", "/app/run.py --fixtures /fixtures --results /results/liteparse --warm-repeats 2"),
    "docling": ("folio-docling:2.148.0", "/opt/experiment/run.py --fixtures /fixtures --results /results --repeats 3"),
}
IMAGE_FORMAT = '{"id":{{json .Id}},"repo_digests":{{json .RepoDigests}},"architecture":{{json .Architecture}},"os":{{json .Os}}}'


def docker(*arguments, timeout=30):
    return subprocess.run(["docker", *arguments], capture_output=True, text=True, timeout=timeout, check=True)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def run_one(name, image, fixtures, results):
    evidence = results / "coordinator" / name
    evidence.mkdir(parents=True, exist_ok=False)
    container = f"folio-ingestion-{name}-{uuid.uuid4().hex[:10]}"
    shell = f"""mkdir -p /results/{name}
python {PARSERS[name][1]}
parser_code=$?
printf '%s\\n' '{{"peak_bytes":null,"source":null,"reason":"cgroup peak unavailable"}}' > /results/{name}/container-memory.json
for path in /sys/fs/cgroup/memory/memory.max_usage_in_bytes /sys/fs/cgroup/memory.peak; do
  if [ -r "$path" ]; then
    peak=$(cat "$path")
    case "$peak" in ''|*[!0-9]*) continue ;; esac
    printf '{{"peak_bytes":%s,"source":"%s"}}\\n' "$peak" "$path" > /results/{name}/container-memory.json
    break
  fi
done
exit "$parser_code"
"""
    metadata = {"parser": name, "container_name": container, "image_tag": image,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "limits": {"cpus": 4, "memory": "6g", "memory_swap": "6g", "timeout_seconds": 600},
                "network": "none", "timed_out": False}
    created = False
    interrupted = False
    container_started = None
    started = time.perf_counter()
    try:
        metadata["image"] = json.loads(docker("image", "inspect", image, "--format", IMAGE_FORMAT).stdout)
        metadata["container_id"] = docker(
            "create", "--name", container, "--network", "none", "--cpus", "4",
            "--memory", "6g", "--memory-swap", "6g",
            "--mount", f"type=bind,source={fixtures},target=/fixtures,readonly",
            "--mount", f"type=bind,source={results},target=/results",
            "--entrypoint", "/bin/sh", image, "-c", shell,
        ).stdout.strip()
        created = True
        container_started = time.perf_counter()
        docker("start", container)
        try:
            metadata["wait_exit_code"] = int(docker("wait", container, timeout=600).stdout.strip())
        except subprocess.TimeoutExpired:
            metadata["timed_out"] = True
            docker("stop", "--time", "10", container)
    except (Exception, KeyboardInterrupt) as error:
        metadata["coordinator_error"] = {"type": type(error).__name__, "message": str(error)}
        interrupted = isinstance(error, KeyboardInterrupt)
        if created:
            try:
                docker("stop", "--time", "10", container)
            except Exception as stop_error:
                metadata["stop_error"] = str(stop_error)
    finally:
        if created:
            try:
                logs = docker("logs", container)
                (evidence / "stdout.log").write_text(logs.stdout, encoding="utf-8")
                (evidence / "stderr.log").write_text(logs.stderr, encoding="utf-8")
                metadata["state"] = json.loads(docker("inspect", container, "--format", "{{json .State}}").stdout)
            except Exception as capture_error:
                metadata["capture_error"] = str(capture_error)
        metadata["coordinator_wall_seconds"] = time.perf_counter() - started
        metadata["container_lifecycle_wall_seconds"] = time.perf_counter() - container_started if container_started else None
        peak_file = results / name / "container-memory.json"
        try:
            metadata["container_memory_peak"] = json.loads(peak_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as peak_error:
            metadata["container_memory_peak"] = {"peak_bytes": None, "reason": "Missing or invalid peak artifact; inspect timeout/OOM/exit state. Missing is not zero.", "error_type": type(peak_error).__name__}
        write_json(evidence / "container.json", metadata)
    print(json.dumps({"parser": name, "container": container, "state": metadata.get("state"), "timed_out": metadata["timed_out"]}), flush=True)
    if interrupted:
        raise KeyboardInterrupt
    return not (metadata.get("coordinator_error") or metadata.get("capture_error") or metadata["timed_out"] or metadata.get("state", {}).get("ExitCode", 1))


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--fixtures", type=Path, required=True)
    cli.add_argument("--results", type=Path, required=True)
    cli.add_argument("--parsers", nargs="+", choices=PARSERS, default=list(PARSERS))
    for name, (image, _) in PARSERS.items():
        cli.add_argument(f"--{name}-image", default=image)
    args = cli.parse_args()
    fixtures, results = args.fixtures.resolve(strict=True), args.results.resolve()
    if not fixtures.is_dir() or not any(p.suffix.lower() in {".pdf", ".docx"} for p in fixtures.iterdir()):
        cli.error("fixtures must contain PDF or DOCX files")
    if len(set(args.parsers)) != len(args.parsers):
        cli.error("select each parser only once")
    if any((results / name).exists() or (results / "coordinator" / name).exists() for name in args.parsers):
        cli.error("Selected parser outputs already exist; choose a fresh results directory")
    results.mkdir(parents=True, exist_ok=True)
    succeeded = []
    for name in args.parsers:
        succeeded.append(run_one(name, getattr(args, f"{name}_image"), fixtures, results))
    return 0 if all(succeeded) else 1


if __name__ == "__main__":
    raise SystemExit(main())
