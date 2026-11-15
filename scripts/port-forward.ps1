$ErrorActionPreference = 'Stop'
Write-Host 'Forwarding BookNest to http://localhost:8080' -ForegroundColor Green
Write-Host 'Keep this window open. Press Ctrl+C to stop port forwarding.' -ForegroundColor Yellow
kubectl port-forward -n booknest svc/booknest-service 8080:80
