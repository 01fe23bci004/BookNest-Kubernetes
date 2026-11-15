$ErrorActionPreference = 'Stop'
Write-Host 'This removes the BookNest namespace and Kubernetes resources in it.' -ForegroundColor Yellow
Write-Host 'The hostPath data directory on the Docker Desktop node is not deleted.' -ForegroundColor Yellow
$answer = Read-Host 'Type DELETE-BOOKNEST to continue'
if ($answer -ne 'DELETE-BOOKNEST') { Write-Host 'Cleanup cancelled.'; exit 0 }
kubectl delete namespace booknest
if ($LASTEXITCODE -ne 0) { throw 'Namespace deletion failed.' }
kubectl delete persistentvolume booknest-data-pv --ignore-not-found=true
Write-Host 'BookNest Kubernetes resources deleted.' -ForegroundColor Green
