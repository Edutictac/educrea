"""Read a root-owned Docker secret, then run the API without root privileges."""

import os
from pathlib import Path

secret_file = os.environ.pop("EDUSTUDIO_DATABASE_URL_FILE")
os.environ["EDUSTUDIO_DATABASE_URL"] = Path(secret_file).read_text().strip()
keys_file = os.environ.pop("EDUSTUDIO_CREDENTIAL_KEYS_FILE")
os.environ["EDUSTUDIO_CREDENTIAL_KEYS"] = Path(keys_file).read_text().strip()
os.setgroups([])
os.setgid(10001)
os.setuid(10001)
os.execvp("uvicorn", ["uvicorn", "edustudio_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"])
