"""Read a root-owned Docker secret, then run the API without root privileges."""

import os
from pathlib import Path

secret_file = os.environ.pop("EDUCREA_DATABASE_URL_FILE")
os.environ["EDUCREA_DATABASE_URL"] = Path(secret_file).read_text().strip()
keys_file = os.environ.pop("EDUCREA_CREDENTIAL_KEYS_FILE")
os.environ["EDUCREA_CREDENTIAL_KEYS"] = Path(keys_file).read_text().strip()
oidc_file = os.environ.pop("EDUCREA_OIDC_CLIENT_SECRET_FILE", "")
if oidc_file:
    os.environ["EDUCREA_OIDC_CLIENT_SECRET"] = Path(oidc_file).read_text().strip()
for name in ("GEMINI", "QWEN", "DEEPSEEK"):
    secret_path = os.environ.pop(f"EDUCREA_{name}_API_KEY_FILE", "")
    if secret_path:
        os.environ[f"EDUCREA_{name}_API_KEY"] = Path(secret_path).read_text().strip()
smtp_path = os.environ.pop("EDUCREA_SMTP_PASSWORD_FILE", "")
if smtp_path:
    os.environ["EDUCREA_SMTP_PASSWORD"] = Path(smtp_path).read_text().strip()
for name in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"):
    secret_path = os.environ.pop(f"EDUCREA_{name}_FILE", "")
    if secret_path:
        os.environ[f"EDUCREA_{name}"] = Path(secret_path).read_text().strip()
os.setgroups([])
os.setgid(10001)
os.setuid(10001)
os.execvp("uvicorn", ["uvicorn", "educrea_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"])
