# Open only Easy Studio's port on Private networks. Safe to run again.
# Does not open ComfyUI's port (8188). Does not turn the firewall off.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File setup\firewall_windows.ps1
#        powershell -NoProfile -ExecutionPolicy Bypass -File setup\firewall_windows.ps1 -Remove
param([switch]$Remove)
$ErrorActionPreference = "Stop"
$port = if ($env:EASY_STUDIO_PORT) { $env:EASY_STUDIO_PORT } else { "7860" }
$name = "Easy Studio LAN $port"
if ($Remove) {
  netsh advfirewall firewall delete rule name="$name" | Out-Host
  Write-Host "Removed $name if it existed. No rule was added for port 8188."
  exit 0
}
netsh advfirewall firewall delete rule name="$name" | Out-Null
netsh advfirewall firewall add rule name="$name" dir=in action=allow protocol=TCP localport=$port profile=private remoteip=localsubnet | Out-Host
Write-Host "PASS  $name allows TCP $port from the local subnet on Private networks."
netsh advfirewall firewall show rule name="$name"
Write-Host "Expected: one inbound allow rule. There must be no Easy Studio rule for port 8188."
