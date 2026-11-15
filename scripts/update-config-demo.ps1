$ErrorActionPreference = 'Stop'
Write-Host 'Updating BookNest ConfigMap demo values...' -ForegroundColor Cyan
$config = @{
    LIBRARY_NAME = 'BookNest Library'
    LIBRARY_HOURS = '10:00 AM - 06:00 PM'
    MAX_BOOKS_PER_STUDENT = '4'
    LATE_RETURN_FEE = '7 INR per day'
    ANNOUNCEMENT = 'Updated notice: the reading room is open until 6 PM.'
    LIBRARY_THEME = 'ocean'
}
$configJson = $config | ConvertTo-Json -Compress
$data = @{}
foreach ($key in $config.Keys) { $data[$key] = [string]$config[$key] }
$data['config.json'] = $configJson
$patch = @{ data = $data } | ConvertTo-Json -Depth 5 -Compress

kubectl patch configmap booknest-config -n booknest --type merge -p $patch
if ($LASTEXITCODE -ne 0) { throw 'ConfigMap update failed.' }

Write-Host "`nConfigMap updated. Kubernetes refreshes mounted files after its projection delay." -ForegroundColor Yellow
Write-Host 'The environment-variable snapshot remains unchanged until pods are recreated.' -ForegroundColor Yellow
Write-Host "`nRestarting the Deployment so both environment variables and mounted files use the new settings..." -ForegroundColor Cyan
kubectl rollout restart deployment/booknest -n booknest
if ($LASTEXITCODE -ne 0) { throw 'Could not restart Deployment.' }
kubectl rollout status deployment/booknest -n booknest --timeout=180s
if ($LASTEXITCODE -ne 0) { throw 'Deployment restart did not complete.' }
Write-Host "`nDone. Refresh the BookNest page and visit Library settings." -ForegroundColor Green
