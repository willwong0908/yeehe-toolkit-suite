"""Run with sudo on yh-srv-01 to mount the gateway on the existing HTTPS site."""

import os
import shutil
import subprocess
import time
from pathlib import Path

site = Path("/etc/nginx/conf.d/yeehe-dashboard.conf")
src = Path(__file__).with_name("nginx.location.conf")
marker = "    include /etc/nginx/snippets/adaptive-memory-dashboard-locations.conf;"
include = "    include /etc/nginx/snippets/yeehe-feishu-transfer.conf;"
target = Path("/etc/nginx/snippets/yeehe-feishu-transfer.conf")
if os.geteuid() != 0:
    raise SystemExit("Run with sudo")
original = site.read_text()
if marker not in original:
    raise SystemExit("Unexpected site layout, inspect configuration first")
backup = site.with_suffix(".conf.pre-transfer-" + str(int(time.time())))
shutil.copy2(site, backup)
previous = target.read_bytes() if target.exists() else None
try:
    target.write_bytes(src.read_bytes())
    if include not in original:
        site.write_text(original.replace(marker, include + "\n" + marker, 1))
    subprocess.run(["nginx", "-t"], check=True)
    subprocess.run(["systemctl", "reload", "nginx"], check=True)
except BaseException:
    shutil.copy2(backup, site)
    if previous is not None:
        target.write_bytes(previous)
    else:
        target.unlink(missing_ok=True)
    raise
