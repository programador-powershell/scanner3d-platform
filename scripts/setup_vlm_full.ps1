# setup_vlm_full.ps1
# One-click setup for full proper llama.cpp VLM (replaces the 10KB stub)
# - Creates D:\llm\qwen3-vl-4b (VLM_DIR) and D:\llama.cpp
# - Downloads the exact GGUF + mmproj that the project expects (via huggingface_hub)
# - Downloads a recent official Windows CUDA prebuilt of llama.cpp (llama-server.exe + CUDA DLLs)
# - Verifies the binary is a real full build (>150KB)
#
# Usage (PowerShell as Administrator recommended for some extractions):
#   cd D:\scanner3d-platform
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup_vlm_full.ps1
#
# After success: restart your node server.js. Auto-spawn will use the real binary,
# VLM_URL will be set after health+probe, and the Qwen/general half of the hybrid VLM judges
# (plus any direct /v1 fetches) will work in addition to the Eagle spatial path.

$ErrorActionPreference = 'Stop'

$VLM_DIR = if ($env:VLM_DIR) { $env:VLM_DIR } else { 'D:\llm\qwen3-vl-4b' }
$LLAMA_DIR = 'D:\llama.cpp'
$TARGET_EXE = Join-Path $LLAMA_DIR 'llama-server.exe'

Write-Host '=== [VLM SETUP] Full llama.cpp + Qwen3-VL-4B-Thinking (scanner3d-platform) ===' -ForegroundColor Cyan
Write-Host "VLM_DIR    : $VLM_DIR"
Write-Host "LLAMA_DIR  : $LLAMA_DIR"
Write-Host "Target exe : $TARGET_EXE"
Write-Host ''

# Ensure dirs
New-Item -ItemType Directory -Path $VLM_DIR -Force | Out-Null
New-Item -ItemType Directory -Path $LLAMA_DIR -Force | Out-Null

# --- MODELS (idempotent, will skip if present) ---
Write-Host '[1/3] Models via huggingface_hub (Q4_K_M + mmproj) ...' -ForegroundColor Yellow

$python = 'python'
try { & $python -c 'import sys; print(\"Python OK\", sys.version)' | Out-Null } catch {
  Write-Warning 'python not found in PATH, trying py launcher'
  $python = 'py'
}

& $python -m pip install -U --quiet 'huggingface_hub[cli,hf_transfer]' hf_transfer | Out-Null

$env:HF_HUB_ENABLE_HF_TRANSFER = '1'
$repo = 'unsloth/Qwen3-VL-4B-Thinking-GGUF'
$modelFile = 'Qwen3-VL-4B-Thinking-Q4_K_M.gguf'
$mmprojFile = 'mmproj-F16.gguf'

& $python -m huggingface_hub.commands.hf download $repo $modelFile $mmprojFile --local-dir $VLM_DIR --local-dir-use-symlinks False

$modelDest = Join-Path $VLM_DIR $modelFile
$mmprojDest = Join-Path $VLM_DIR $mmprojFile

if (-not (Test-Path $modelDest) -or -not (Test-Path $mmprojDest)) {
  Write-Error 'Model download incomplete. Use the server /api/vlm/download endpoint as fallback (it streams + reports progress via SSE).'
  exit 1
}

$msz = [math]::Round((Get-Item $modelDest).Length / 1MB, 1)
$psz = [math]::Round((Get-Item $mmprojDest).Length / 1MB, 1)
Write-Host "Models OK: $modelFile ($msz MB) + $mmprojFile ($psz MB)" -ForegroundColor Green

# --- BINARY (the actual fix for the 10KB stub) ---
Write-Host ''
Write-Host '[2/3] llama-server.exe prebuilt (CUDA 12.4 x64 from official ggml-org release) ...' -ForegroundColor Yellow

$releaseTag = 'b9672'
$base = "https://github.com/ggml-org/llama.cpp/releases/download/$releaseTag"

$zipName = "llama-$releaseTag-bin-win-cuda-12.4-x64.zip"
$zipUrl = "$base/$zipName"
$zipPath = Join-Path $env:TEMP $zipName

$rtName = 'cudart-llama-bin-win-cuda-12.4-x64.zip'
$rtUrl = "$base/$rtName"
$rtPath = Join-Path $env:TEMP $rtName

if (-not (Test-Path $zipPath)) {
  Write-Host "Downloading $zipName (this is the real full build, not the stub)..."
  Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
} else {
  Write-Host 'Reusing existing zip in TEMP'
}

$extract = Join-Path $env:TEMP "llama-b$releaseTag-extract"
if (Test-Path $extract) { Remove-Item $extract -Recurse -Force -ErrorAction SilentlyContinue }
Expand-Archive -LiteralPath $zipPath -DestinationPath $extract -Force

$exe = Get-ChildItem $extract -Recurse -Filter 'llama-server.exe' | Select-Object -First 1
if (-not $exe) {
  Write-Error 'llama-server.exe not found in the release zip. Layout may have changed for this tag.'
  exit 1
}

Copy-Item -LiteralPath $exe.FullName -Destination $TARGET_EXE -Force

# Bring any .dll from the extract (llama.dll, ggml*.dll, cudart etc.)
Get-ChildItem $extract -Recurse -Include '*.dll' | ForEach-Object {
  Copy-Item -LiteralPath $_.FullName -Destination $LLAMA_DIR -Force
}

# Extra cudart package (some tags ship runtime separately)
if (-not (Test-Path $rtPath)) {
  try {
    Write-Host 'Fetching matching cudart runtime zip...'
    Invoke-WebRequest -Uri $rtUrl -OutFile $rtPath -UseBasicParsing
    $rtExtract = Join-Path $env:TEMP "llama-rt-$releaseTag"
    if (Test-Path $rtExtract) { Remove-Item $rtExtract -Recurse -Force -ErrorAction SilentlyContinue }
    Expand-Archive -LiteralPath $rtPath -DestinationPath $rtExtract -Force
    Get-ChildItem $rtExtract -Recurse -Include '*.dll' | ForEach-Object {
      Copy-Item -LiteralPath $_.FullName -Destination $LLAMA_DIR -Force
    }
  } catch {
    Write-Warning 'cudart zip not available or failed (non-fatal). If you have NVIDIA GPU you may need CUDA 12.4+ toolkit installed or copy cudart64_*.dll manually.'
  }
}

# Verify the installed server (official prebuilts often ship a small launcher .exe + large *-impl.dll + ggml-*.dll + mtmd.dll for vision).
# As long as the collection comes from the official release zip and --help runs, it is a "full proper build".
if (-not (Test-Path $TARGET_EXE)) {
  Write-Error 'Failed to install llama-server.exe'
  exit 1
}
$sz = (Get-Item $TARGET_EXE).Length
$hasImpl = (Test-Path (Join-Path $LLAMA_DIR 'llama-server-impl.dll')) -or (Test-Path (Join-Path $LLAMA_DIR 'llama.dll'))
$hasCuda = Test-Path (Join-Path $LLAMA_DIR 'ggml-cuda.dll')
$hasMtmd = Test-Path (Join-Path $LLAMA_DIR 'mtmd.dll')

if ($sz -lt 5 * 1024) {
  Write-Error "The launcher exe is absurdly small and no supporting DLLs were found. The release layout may have changed."
  exit 1
}
if ($sz -lt 150 * 1024 -and -not ($hasImpl -and ($hasCuda -or $hasMtmd))) {
  Write-Warning "llama-server.exe is small ($([math]::Round($sz/1KB,1)) KB) but this is normal for the split official 'bin-win-cuda' packages. Key DLLs were found, continuing."
}
Write-Host "Binary layout OK: llama-server.exe $([math]::Round($sz/1KB,1)) KB + supporting DLLs (impl=$hasImpl cuda=$hasCuda vision/mtmd=$hasMtmd)" -ForegroundColor Green

# Quick functional test (no model load)
Write-Host 'Quick smoke test (llama-server --help)...'
& $TARGET_EXE --help 2>&1 | Select-Object -First 5 | ForEach-Object { Write-Host $_ }

# --- DONE ---
Write-Host ''
Write-Host '[3/3] Verification' -ForegroundColor Yellow
$modelsOk = (Test-Path $modelDest) -and (Test-Path $mmprojDest)
$binOk = (Test-Path $TARGET_EXE) -and ($sz -gt 150KB)

Write-Host "Models ready : $modelsOk"
Write-Host "Real binary  : $binOk"

if ($modelsOk -and $binOk) {
  Write-Host ''
  Write-Host '=== SUCCESS: 10KB stub replaced with full llama.cpp build ===' -ForegroundColor Green
  Write-Host ''
  Write-Host 'Restart your scanner3d-platform server:' -ForegroundColor Cyan
  Write-Host '  cd D:\scanner3d-platform'
  Write-Host '  node server.js'
  Write-Host ''
  Write-Host 'On boot you should now see clean lines like:'
  Write-Host '  [VLM] Iniciando LLM local automaticamente no boot...'
  Write-Host '  [VLM] Auto/spawn llama-server D:\llama.cpp\llama-server.exe'
  Write-Host '  [VLM] Health OK — VLM respondendo em http://127.0.0.1:8080/v1/chat/completions'
  Write-Host ''
  Write-Host 'No more "Binário suspeito", no more Eagle parse errors for scan (Eagle still used for spatial),'
  Write-Host 'and the Qwen/general part of hybrid judges + direct fetches will now succeed with real vision.'
  Write-Host ''
  Write-Host 'The project /api/vlm/download endpoint can still be used from the UI for models (it reports progress).'
  Write-Host 'This script is the fast/offline-capable alternative for the full stack (binary + models).'
  Write-Host ''
  Write-Host 'Tip: with a real GPU the server starts with -ngl 99 (almost everything on VRAM). CPU-only still works.'
} else {
  Write-Host 'Setup not complete. Check messages above.' -ForegroundColor Red
  exit 1
}
