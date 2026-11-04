# Reproducible local proof that the corrected "Build frontend" step fails
# closed: a failing native command must abort before a later succeeding native
# command can turn the outer exit code into 0.
# Mirrors the workflow pattern ($LASTEXITCODE checked after every native call).
$ErrorActionPreference = 'Stop'
cmd /c exit 7
if ($LASTEXITCODE -ne 0) { throw "first native command failed with exit code $LASTEXITCODE" }
cmd /c exit 0
if ($LASTEXITCODE -ne 0) { throw "second native command failed with exit code $LASTEXITCODE" }
