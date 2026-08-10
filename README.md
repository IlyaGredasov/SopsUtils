# Gist
Reusable CLI utilities for encrypting dotenv files with SOPS and, optionally,
generating Kubernetes ConfigMap and encrypted Secret manifests.

After installation, run the commands from the consuming project's root directory:

```powershell
sops-encrypt --root-dir .
sops-encrypt --root-dir . --with-k8s --namespace my-app
sops-decrypt --root-dir . --age-key-file age-key.txt
```

Encryption recursively finds every `*.env` file under `--root-dir` and creates a
sibling `<name>.env.enc` file. Decryption finds every `*.env.enc` file and
restores the sibling `.env` file.

With `--with-k8s`, each env file uses the `env-schema.yaml` in the same
directory. Both `env/service.env` and `service/.env` generate manifests in
`infra/k8s/base/service`; the root `.env` still uses `infra/k8s/base`.
ConfigMap and Secret manifests are created only when the respective env values
are present. Encrypted Secrets use the `secret.yaml.enc` filename.

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
