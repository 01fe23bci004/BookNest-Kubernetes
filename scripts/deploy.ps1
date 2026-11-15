$ErrorActionPreference = 'Stop'

function Run-Command([string]$Name, [scriptblock]$Command) {
    Write-Host "`n>>> $Name" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Name failed (exit code $LASTEXITCODE)." }
}

Write-Host 'BookNest Kubernetes deployment' -ForegroundColor Green
Run-Command 'Check Kubernetes context' { kubectl config current-context }
Run-Command 'Check cluster node' { kubectl get nodes }
Run-Command 'Build local Docker image' { docker build -t booknest:2.0 . }
Run-Command 'Create namespace' { kubectl apply -f .\k8s\00-namespace.yaml }
Run-Command 'Create persistent volume' { kubectl apply -f .\k8s\03-pv.yaml }
Run-Command 'Create persistent volume claim' { kubectl apply -f .\k8s\04-pvc.yaml }
Run-Command 'Apply ConfigMap' { kubectl apply -f .\k8s\01-configmap.yaml }
Run-Command 'Apply Secret' { kubectl apply -f .\k8s\02-secret.yaml }
Run-Command 'Apply Deployment' { kubectl apply -f .\k8s\05-deployment.yaml }
Run-Command 'Apply Service' { kubectl apply -f .\k8s\06-service.yaml }

Write-Host "`nWaiting for BookNest pods to become ready..." -ForegroundColor Yellow
kubectl rollout status deployment/booknest -n booknest --timeout=240s
if ($LASTEXITCODE -ne 0) { throw 'Deployment did not become ready. Run kubectl describe pods -n booknest and inspect the events.' }

Write-Host "`nDeployment complete. Current resources:" -ForegroundColor Green
kubectl get pods,svc,pvc -n booknest
Write-Host "`nNext: run .\scripts\port-forward.ps1 and open http://localhost:8080" -ForegroundColor Green
