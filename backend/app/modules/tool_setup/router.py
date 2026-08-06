from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/tools", tags=["Tool setup"])


POWERSHELL_SETUP = r'''$ErrorActionPreference = "Stop"
$tool = if ($env:NEXORA_TOOL) { $env:NEXORA_TOOL } else { "claude" }
$model = if ($env:NEXORA_MODEL) { $env:NEXORA_MODEL } else { "gpt-5.5" }
$base = if ($env:NEXORA_BASE) { $env:NEXORA_BASE.TrimEnd("/") } else { "https://meridian.nexoratech.com.vn" }
$key = $env:NEXORA_KEY
if (-not $key) { throw "NEXORA_KEY is missing." }
if ($tool -notin @("claude", "codex")) { throw "NEXORA_TOOL must be claude or codex." }
if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) { throw "Windows App Installer (winget) is required." }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
  winget install --id OpenJS.NodeJS.LTS --exact --silent --accept-package-agreements --accept-source-agreements
}
if ($tool -eq "claude" -and -not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
  winget install --id Git.Git --exact --silent --accept-package-agreements --accept-source-agreements
}
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw "Node.js was installed. Reopen PowerShell and run the setup command again." }
$package = if ($tool -eq "claude") { "@anthropic-ai/claude-code" } else { "@openai/codex" }
$launcher = "$tool.cmd"
if (-not (Get-Command $launcher -ErrorAction SilentlyContinue)) { & npm.cmd install --global $package }
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
if (Test-Path "C:\Program Files\Git\bin\bash.exe") {
  [Environment]::SetEnvironmentVariable("CLAUDE_CODE_GIT_BASH_PATH", "C:\Program Files\Git\bin\bash.exe", "User")
  $env:CLAUDE_CODE_GIT_BASH_PATH = "C:\Program Files\Git\bin\bash.exe"
}
[Environment]::SetEnvironmentVariable("ANTHROPIC_BASE_URL", $base, "User")
[Environment]::SetEnvironmentVariable("ANTHROPIC_AUTH_TOKEN", $key, "User")
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $null, "User")
[Environment]::SetEnvironmentVariable("ANTHROPIC_MODEL", $model, "User")
[Environment]::SetEnvironmentVariable("OPENAI_BASE_URL", "$base/v1", "User")
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", $key, "User")
$env:ANTHROPIC_BASE_URL = $base
$env:ANTHROPIC_AUTH_TOKEN = $key
$env:ANTHROPIC_MODEL = $model
$env:OPENAI_BASE_URL = "$base/v1"
$env:OPENAI_API_KEY = $key
Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
if ($tool -eq "claude") {
  $config = Join-Path $env:USERPROFILE ".claude.json"
  $state = if (Test-Path $config) { Get-Content $config -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
  $state | Add-Member -NotePropertyName hasCompletedOnboarding -NotePropertyValue $true -Force
  $state | ConvertTo-Json -Depth 20 | Set-Content $config -Encoding UTF8
  $claudeDir = Join-Path $env:USERPROFILE ".claude"
  New-Item -ItemType Directory -Force $claudeDir | Out-Null
  $settingsPath = Join-Path $claudeDir "settings.json"
  $settings = if (Test-Path $settingsPath) { Get-Content $settingsPath -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
  if (-not $settings.env) { $settings | Add-Member -NotePropertyName env -NotePropertyValue ([pscustomobject]@{}) -Force }
  $settings.env | Add-Member -NotePropertyName ANTHROPIC_BASE_URL -NotePropertyValue $base -Force
  $settings.env | Add-Member -NotePropertyName ANTHROPIC_AUTH_TOKEN -NotePropertyValue $key -Force
  $settings.env | Add-Member -NotePropertyName ANTHROPIC_MODEL -NotePropertyValue $model -Force
  $settings.env.PSObject.Properties.Remove("ANTHROPIC_API_KEY")
  $settings | ConvertTo-Json -Depth 20 | Set-Content $settingsPath -Encoding UTF8
}
Write-Host "Nexora setup completed. Starting $tool..." -ForegroundColor Green
& $launcher
'''


BASH_SETUP = r'''#!/usr/bin/env bash
set -e
tool="${NEXORA_TOOL:-claude}"
model="${NEXORA_MODEL:-gpt-5.5}"
base="${NEXORA_BASE:-https://meridian.nexoratech.com.vn}"
base="${base%/}"
: "${NEXORA_KEY:?NEXORA_KEY is missing}"
if [ "$tool" != "claude" ] && [ "$tool" != "codex" ]; then echo "NEXORA_TOOL must be claude or codex" >&2; exit 1; fi
if ! command -v npm >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then brew install node
  elif command -v apt-get >/dev/null 2>&1; then sudo apt-get update && sudo apt-get install -y nodejs npm
  elif command -v dnf >/dev/null 2>&1; then sudo dnf install -y nodejs npm
  else echo "Install Node.js LTS, then run this command again." >&2; exit 1; fi
fi
package="@openai/codex"; [ "$tool" = "claude" ] && package="@anthropic-ai/claude-code"
command -v "$tool" >/dev/null 2>&1 || npm install --global "$package"
profile="$HOME/.profile"
touch "$profile"
sed -i.bak '/# Nexora Gateway$/,/^# End Nexora Gateway$/d' "$profile" 2>/dev/null || true
cat >> "$profile" <<EOF
# Nexora Gateway
export ANTHROPIC_BASE_URL='$base'
export ANTHROPIC_AUTH_TOKEN='$NEXORA_KEY'
export ANTHROPIC_MODEL='$model'
export OPENAI_BASE_URL='$base/v1'
export OPENAI_API_KEY='$NEXORA_KEY'
# End Nexora Gateway
EOF
unset ANTHROPIC_API_KEY
export ANTHROPIC_BASE_URL="$base" ANTHROPIC_AUTH_TOKEN="$NEXORA_KEY" ANTHROPIC_MODEL="$model"
export OPENAI_BASE_URL="$base/v1" OPENAI_API_KEY="$NEXORA_KEY"
if [ "$tool" = "claude" ]; then
  mkdir -p "$HOME/.claude"
  node <<'NODE'
const fs = require('fs');
const path = require('path');
const file = path.join(process.env.HOME, '.claude', 'settings.json');
let settings = {};
try { settings = JSON.parse(fs.readFileSync(file, 'utf8')); } catch {}
settings.env = {
  ...(settings.env || {}),
  ANTHROPIC_BASE_URL: process.env.ANTHROPIC_BASE_URL,
  ANTHROPIC_AUTH_TOKEN: process.env.NEXORA_KEY,
  ANTHROPIC_MODEL: process.env.ANTHROPIC_MODEL
};
delete settings.env.ANTHROPIC_API_KEY;
fs.writeFileSync(file, JSON.stringify(settings, null, 2));
NODE
fi
echo "Nexora setup completed. Starting $tool..."
exec "$tool"
'''


@router.get("/setup.ps1", response_class=PlainTextResponse)
def powershell_setup() -> PlainTextResponse:
    return PlainTextResponse(POWERSHELL_SETUP, media_type="text/plain; charset=utf-8")


@router.get("/setup.sh", response_class=PlainTextResponse)
def bash_setup() -> PlainTextResponse:
    return PlainTextResponse(BASH_SETUP, media_type="text/plain; charset=utf-8")
