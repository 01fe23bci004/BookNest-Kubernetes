# BookNest — Smart Library Management System

A polished, small library portal deployed to Kubernetes. Readers can browse and search the catalogue; librarians can issue and return books and add titles. Public library settings are supplied by a Kubernetes **ConfigMap** and librarian credentials/session-signing key are supplied by a Kubernetes **Secret**.

This project supports the Cloud Computing Lab Evaluation 2 problem: **“ConfigMaps and Secrets for Application Configuration.”** It demonstrates environment-variable injection, mounted files, application updates and Secret handling.

## Features

- Dedicated, responsive librarian sign-in page.
- Session-only sign-in: each new browser tab must authenticate; refreshes in the same tab keep the session. There is also an explicit Sign out button.
- Server-validated, HttpOnly session cookie; app APIs require a valid session.
- Book catalogue, search, dashboard statistics, issue/return workflow, and add-book form.
- ConfigMap values injected as environment variables and mounted at `/etc/booknest/config/config.json`.
- Secret credentials and session-signing key injected as environment variables; credentials file mounted at `/etc/booknest/secrets/credentials.json`.
- Two Deployment replicas, Kubernetes Service, health probes, and persistent SQLite data.

## Requirements

- Windows 10/11 with Docker Desktop installed and running.
- Kubernetes enabled in Docker Desktop.
- `docker` and `kubectl` available in PowerShell.
- `kubectl config current-context` points to Docker Desktop and `kubectl get nodes` shows `Ready`.

> The included PersistentVolume uses a local `hostPath` at `/mnt/data/booknest`, intended for a single-node Docker Desktop Kubernetes cluster. For multi-node or production use, choose a suitable storage class and managed database.

## Deploy on Windows

1. Extract the ZIP.
2. Open the extracted `booknest-kubernetes` folder in File Explorer.
3. Click the address bar, type `powershell`, and press Enter.
4. Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\scripts\deploy.ps1
```

Before deployment, create a local Secret manifest from the example and replace every `REPLACE_WITH_...` value with your own credentials and a long random session key. Keep `k8s/02-secret.yaml` private; it is excluded by `.gitignore`.

```powershell
Copy-Item .\k8s\02-secret.example.yaml .\k8s\02-secret.yaml
notepad .\k8s\02-secret.yaml
```

Then run the deployment script. It builds `booknest:2.0`, creates the namespace, PV/PVC, ConfigMap, Secret, Deployment and Service, then waits for both pods to become ready.

## Open the website

In a **second** PowerShell window opened in the same project folder, run:

```powershell
.\scripts\port-forward.ps1
```

Keep that window open and visit **http://localhost:8080**. The first visit redirects to the dedicated sign-in page.

## Configure librarian credentials

Set your own username and strong password in the local `k8s/02-secret.yaml` file created from `k8s/02-secret.example.yaml`. Use a unique, randomly generated `SESSION_SECRET_KEY`. The local Secret file is ignored by Git and is not included in this repository.

## Session behaviour

- Successful sign-in creates an HttpOnly, browser-session cookie signed by the key supplied through the Kubernetes Secret.
- The frontend stores a per-tab proof in `sessionStorage`; a fresh tab must sign in again. Refreshing the same tab retains its proof. API calls must present both the HttpOnly session cookie and the per-tab proof, so a cookie shared by the browser is not enough to authenticate a new tab.
- All library data and write APIs validate the signed session and per-tab proof on the server. The health endpoint remains unauthenticated so Kubernetes readiness/liveness probes can reach it.
- Use **Sign out** to revoke the browser cookie and clear the tab marker.

This is appropriate for a local lab demonstration. For production, use HTTPS, CSRF protections, rate limiting, password hashing/identity provider integration, and managed secret storage. Browsers that restore previous sessions may restore tab state; use Sign out for a guaranteed end to the current session.

## Verify Kubernetes resources

```powershell
.\scripts\verify.ps1
```

Useful commands:

```powershell
kubectl get pods -n booknest
kubectl get configmap,secret,deploy,svc,pvc -n booknest
kubectl describe deployment booknest -n booknest
kubectl logs deployment/booknest -n booknest
```

The verification script does not print the Secret password or session-signing key.

## Demonstrate a ConfigMap update

Run:

```powershell
.\scripts\update-config-demo.ps1
```

The script changes library hours, borrowing limit, late fee, announcement and theme, then restarts the Deployment. Refresh BookNest and open **Library settings**. The new values should appear.

Technical point for your viva:

- A ConfigMap mounted as a directory is projected into the pod and can refresh after Kubernetes' projection delay.
- Values imported as environment variables are a startup snapshot. Existing containers do not see changed environment variables. Recreating pods loads the updated values.
- The app reads the mounted `config.json` on each request, so its effective values can reflect the updated mounted file.

## Demonstrate a Secret update

Edit your local, Git-ignored `k8s/02-secret.yaml` and change `ADMIN_PASSWORD` and the matching password inside `credentials.json`. Apply the Secret and restart the Deployment:

```powershell
kubectl apply -f .\k8s\02-secret.yaml
kubectl rollout restart deployment/booknest -n booknest
kubectl rollout status deployment/booknest -n booknest
```

Sign in using the updated password. The settings page confirms whether the Secret environment and mounted-file sources match without exposing credential values. If you also rotate `SESSION_SECRET_KEY`, existing sessions become invalid and users must sign in again.

## Cleanup

```powershell
.\scripts\cleanup.ps1
```

The script asks for confirmation. It removes Kubernetes resources in the namespace and PV object, but does not erase the Docker Desktop node's `/mnt/data/booknest` directory.

## Kubernetes concepts to explain

A **ConfigMap** stores non-confidential settings such as library hours and borrowing limits. A **Secret** stores sensitive values such as administrator credentials and the session-signing key. Kubernetes makes these values available to containers as environment variables and mounted files. Keeping configuration outside the image lets the same application image run with different settings in different environments.

The example Kubernetes Secret manifest uses `stringData` for readability in a lab. Copy it to the ignored local filename and replace all placeholders before deployment. Never commit real credentials or keys. Kubernetes Secret manifests use `stringData` here for readability in a lab. Kubernetes Secret values are not automatically encrypted at rest merely because they are Secret objects; configure encryption at rest and strict RBAC for real deployments.
