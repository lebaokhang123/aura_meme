param([string]$BaseUrl = 'http://localhost:5080')
$ErrorActionPreference = 'Stop'

function Assert-Equal($Actual, $Expected, [string]$Name) {
    if ($Actual -ne $Expected) { throw "FAIL ${Name}: expected $Expected, got $Actual" }
    Write-Host "PASS $Name"
}

function Send-Request([string]$Method, [string]$Path, $Body = $null, $Headers = @{}) {
    $options = @{ Method = $Method; Uri = "$BaseUrl$Path"; Headers = $Headers; SkipHttpErrorCheck = $true }
    if ($null -ne $Body) {
        $options.ContentType = 'application/json'
        $options.Body = $Body | ConvertTo-Json -Compress
    }
    return Invoke-WebRequest @options
}

$postId = $null
try {
    $response = Send-Request GET '/api/posts'
    Assert-Equal ([int]$response.StatusCode) 200 'GET all'

    $data = @{ title = 'Smoke test post'; content = 'Only this test record is removed.'; author = 'API test'; id = 999999; createdAt = '2000-01-01T00:00:00Z' }
    $response = Send-Request POST '/api/posts' $data
    Assert-Equal ([int]$response.StatusCode) 201 'POST returns Created'
    $created = $response.Content | ConvertFrom-Json
    $postId = $created.id
    Assert-Equal ($postId -gt 0 -and $postId -ne 999999) $true 'Server owns Id'
    Assert-Equal ([datetime]$created.createdAt -gt [datetime]'2026-01-01') $true 'Server owns CreatedAt'
    Assert-Equal ([string]$response.Headers.Location -like "*/api/posts/$postId") $true 'Location header'

    $response = Send-Request GET "/api/posts/$postId"
    Assert-Equal ([int]$response.StatusCode) 200 'GET by id'
    Assert-Equal (($response.Content | ConvertFrom-Json).title) $data.title 'Read persisted title'

    $data.title = 'Updated smoke test'
    $response = Send-Request PUT "/api/posts/$postId" $data
    Assert-Equal ([int]$response.StatusCode) 204 'PUT'
    $response = Send-Request GET "/api/posts/$postId"
    $updated = $response.Content | ConvertFrom-Json
    Assert-Equal $updated.title $data.title 'PUT persisted'
    Assert-Equal ([string]$updated.createdAt) ([string]$created.createdAt) 'PUT preserves CreatedAt'

    foreach ($field in @('title', 'content', 'author')) {
        $invalid = @{ title = 'Valid'; content = 'Valid'; author = 'Valid' }
        $invalid[$field] = '   '
        Assert-Equal ([int](Send-Request POST '/api/posts' $invalid).StatusCode) 400 "Reject blank $field"
    }
    $invalid = @{ title = ('x' * 201); content = 'Valid'; author = 'Test' }
    Assert-Equal ([int](Send-Request PUT "/api/posts/$postId" $invalid).StatusCode) 400 'Reject long title on PUT'

    Assert-Equal ([int](Send-Request DELETE "/api/posts/$postId").StatusCode) 204 'DELETE'
    foreach ($method in @('GET', 'PUT', 'DELETE')) {
        $body = if ($method -eq 'PUT') { $data } else { $null }
        Assert-Equal ([int](Send-Request $method "/api/posts/$postId" $body).StatusCode) 404 "$method missing id"
    }

    $headers = @{ Origin = 'http://localhost:5173'; 'Access-Control-Request-Method' = 'PUT'; 'Access-Control-Request-Headers' = 'content-type' }
    $response = Send-Request OPTIONS '/api/posts/1' $null $headers
    Assert-Equal ([string]$response.Headers['Access-Control-Allow-Origin']) $headers.Origin 'Allow frontend CORS'
    $headers.Origin = 'http://example.com'
    $response = Send-Request OPTIONS '/api/posts/1' $null $headers
    Assert-Equal ($null -eq $response.Headers['Access-Control-Allow-Origin']) $true 'Reject unrelated origin'
    Assert-Equal ([int](Send-Request GET '/openapi/v1.json').StatusCode) 200 'OpenAPI available'
}
finally {
    if ($null -ne $postId) { $null = Send-Request DELETE "/api/posts/$postId" }
}
