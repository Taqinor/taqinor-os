# Audit Lighthouse de toutes les pages (outil de session, hors git via shot-*/lh-*)
param([string]$BaseUrl = "http://127.0.0.1:8788")
$pages = [ordered]@{
  'home'          = '/'
  'residentiel'   = '/r%C3%A9sidentiel'
  'professionnel' = '/professionnel'
  'equipement'    = '/%C3%A9quipement'
  'contact'       = '/contact'
  'loi-82-21'     = '/loi-82-21'
  'regul'         = '/regularization-article-33'
}
$env:CHROME_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"
foreach ($k in $pages.Keys) {
  npx --yes lighthouse ($BaseUrl + $pages[$k]) --quiet --output=json --output-path=".curation/lh-$k.json" --chrome-flags="--headless=new --disable-gpu" --only-categories=performance,accessibility,best-practices,seo 2>$null | Out-Null
  $r = Get-Content ".curation/lh-$k.json" -Raw | ConvertFrom-Json
  $s = $r.categories
  "{0,-14} perf {1,3}  a11y {2,3}  bp {3,3}  seo {4,3}" -f $k, [math]::Round($s.performance.score*100), [math]::Round($s.accessibility.score*100), [math]::Round($s.'best-practices'.score*100), [math]::Round($s.seo.score*100)
}
