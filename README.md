# Gist
Reusable CLI utilities for encrypting dotenv files with SOPS and, optionally,
generating Kubernetes ConfigMap and encrypted Secret manifests.

Run them from a consuming project by passing its root directory:

```powershell
uv run --directory path/to/sops_utils scripts/encrypt_sops.py --root-dir .
uv run --directory path/to/sops_utils scripts/encrypt_sops.py --root-dir . --with-k8s --namespace my-app
uv run --directory path/to/sops_utils scripts/decrypt_sops.py --root-dir .
```

Use `--namespace` to set both the Kubernetes namespace and the generated resource names (`<namespace>-config` and `<namespace>-secrets`).

When Kubernetes generation is enabled, the project must provide `env-schema.yaml`:

```yaml
variables:
  APP_ENV: global
  POSTGRES_DB: config
  POSTGRES_PASSWORD: secret
```
