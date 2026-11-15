$ErrorActionPreference = 'Stop'
Write-Host '=== BookNest Kubernetes resources ===' -ForegroundColor Cyan
kubectl get pods,deploy,svc,pvc -n booknest
if ($LASTEXITCODE -ne 0) { throw 'Could not list BookNest resources.' }

Write-Host "`n=== ConfigMap and Secret objects ===" -ForegroundColor Cyan
kubectl get configmap,secret -n booknest
if ($LASTEXITCODE -ne 0) { throw 'Could not list ConfigMap/Secret objects.' }

$pod = kubectl get pods -n booknest -l app=booknest -o jsonpath='{.items[0].metadata.name}'
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($pod)) { throw 'No BookNest pod found.' }

Write-Host "`n=== Non-sensitive ConfigMap environment value ===" -ForegroundColor Cyan
kubectl exec -n booknest $pod -- printenv LIBRARY_NAME
Write-Host "`n=== Secret wiring (secret values are not printed) ===" -ForegroundColor Cyan
$secretUser = kubectl exec -n booknest $pod -- printenv ADMIN_USERNAME
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($secretUser)) { throw 'ADMIN_USERNAME is not injected.' }
Write-Host 'ADMIN_USERNAME: injected' -ForegroundColor Green
$sessionKey = kubectl exec -n booknest $pod -- printenv SESSION_SECRET_KEY
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($sessionKey)) { throw 'SESSION_SECRET_KEY is not injected.' }
Write-Host 'SESSION_SECRET_KEY: injected (value hidden)' -ForegroundColor Green
Write-Host "`n=== Mounted configuration and Secret files ===" -ForegroundColor Cyan
kubectl exec -n booknest $pod -- sh -c 'test -f /etc/booknest/config/config.json && echo ConfigMap file: mounted'
kubectl exec -n booknest $pod -- sh -c 'test -f /etc/booknest/secrets/credentials.json && echo Secret file: mounted'
Write-Host "`nVerification commands completed. Open Library settings in BookNest to see runtime status." -ForegroundColor Green
