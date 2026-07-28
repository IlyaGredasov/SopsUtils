# Gist
Reusable CLI utilities for encrypting dotenv files with SOPS and, optionally,
generating Kubernetes ConfigMap and encrypted Secret manifests.

Run them from a consuming project by passing its root directory:

```powershell
uv run --directory path/to/sops_utils scripts/encrypt_sops.py --root-dir . --source-file .env
uv run --directory path/to/sops_utils scripts/encrypt_sops.py --root-dir . --source-file .env --with-k8s --namespace my-app
uv run --directory path/to/sops_utils scripts/decrypt_sops.py --root-dir . --source-file .env.enc --age-key-file age-key.txt
uv run --directory path/to/sops_utils scripts/encrypt_sops.py --root-dir . --project
```

Use `--source-file` (and optionally `--output-file`) to process one file. Use `--project` to recursively process every env file: encryption finds `*.env` and creates a sibling `<name>.env.enc`, while decryption finds `*.env.enc` and restores the sibling `.env`.

With `--project --with-k8s`, each env file uses the `env-schema.yaml` in the same directory. For `service/service.env`, manifests are generated in `infra/k8s/base/service`; the root `.env` still uses `infra/k8s/base`.

Use `--namespace` to set both the Kubernetes namespace and the generated resource names (`<namespace>-config` and `<namespace>-secrets`).

When Kubernetes generation is enabled, the project must provide `env-schema.yaml`:

```yaml
variables:
  APP_ENV: global
  POSTGRES_DB: config
  POSTGRES_PASSWORD: secret
  REDIS_ENDPOINT:
    type: config
    k8s_value: redis://redis-master:6379/0
```

`k8s_value` is used only in generated Kubernetes manifests; the value in `.env`
is retained when encrypting the dotenv file.
