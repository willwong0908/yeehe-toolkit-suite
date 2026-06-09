from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


SPREADSHEET_EXTENSIONS = {".xlsx", ".xlsm", ".xls", ".xlsb", ".csv"}


def _run_windows_powershell(script: str, env: dict[str, str] | None = None) -> None:
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-Command", script],
            check=True,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(detail or "Windows 打开操作失败。") from exc


def open_path(path_text: str | os.PathLike[str]) -> None:
    path = Path(path_text)
    if not path.exists():
        raise FileNotFoundError("文件不存在：{0}".format(path))
    if os.name == "nt":
        if path.is_file() and path.suffix.lower() in SPREADSHEET_EXTENSIONS:
            _open_spreadsheet_file_windows(path)
            return
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


def open_folder(path_text: str | os.PathLike[str]) -> None:
    path = Path(path_text)
    directory = path if path.is_dir() else path.parent
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        subprocess.Popen(["explorer.exe", str(directory)])
        return
    subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(directory)])


def open_spreadsheet_cell(path_text: str | os.PathLike[str], sheet_name: str, cell_address: str) -> None:
    path = Path(path_text)
    if not path.exists():
        raise FileNotFoundError("文件不存在：{0}".format(path))
    if os.name != "nt":
        raise RuntimeError("当前系统暂不支持直接定位 Excel 单元格。")
    if path.suffix.lower() not in SPREADSHEET_EXTENSIONS:
        raise RuntimeError("当前文件类型暂不支持直接定位。")
    _run_windows_powershell(_spreadsheet_activation_script(select_cell=True), env=_spreadsheet_env(path, sheet_name, cell_address))


def _open_spreadsheet_file_windows(path: Path) -> None:
    _run_windows_powershell(_spreadsheet_activation_script(select_cell=False), env=_spreadsheet_env(path, "", ""))


def _spreadsheet_env(path: Path, sheet_name: str, cell_address: str) -> dict[str, str]:
    env = os.environ.copy()
    env["YEEHE_SPREADSHEET_FILE"] = str(path.resolve())
    env["YEEHE_SPREADSHEET_SHEET"] = str(sheet_name or "")
    env["YEEHE_SPREADSHEET_CELL"] = str(cell_address or "")
    return env


def _spreadsheet_activation_script(*, select_cell: bool) -> str:
    select_mode = "$true" if select_cell else "$false"
    return rf"""
$ErrorActionPreference = 'Stop'
$targetFile = [System.IO.Path]::GetFullPath($env:YEEHE_SPREADSHEET_FILE)
$targetSheet = $env:YEEHE_SPREADSHEET_SHEET
$targetCell = $env:YEEHE_SPREADSHEET_CELL
$selectCell = {select_mode}
$app = $null
$progIds = New-Object System.Collections.Generic.List[string]

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class YeeheWin32 {{
  [DllImport("user32.dll")]
  public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")]
  public static extern bool SetForegroundWindow(IntPtr hWnd);
}}
"@

function Add-AppCandidate {{
  param([string]$progId)
  if ([string]::IsNullOrWhiteSpace($progId)) {{ return }}
  if (-not $progIds.Contains($progId)) {{
    [void]$progIds.Add($progId)
  }}
}}

function Add-CandidatesFromText {{
  param([string]$text)
  if ([string]::IsNullOrWhiteSpace($text)) {{ return }}
  $value = $text.ToLowerInvariant()
  if ($value.Contains('ket') -or $value.Contains('wps') -or $value.Contains('\et.exe') -or $value.Contains('/et ')) {{
    Add-AppCandidate 'ket.Application'
  }}
  if ($value.Contains('excel') -or $value.Contains('\excel.exe') -or $value.Contains('microsoft office')) {{
    Add-AppCandidate 'Excel.Application'
  }}
}}

function Get-RegistryDefaultValue {{
  param([string]$path)
  try {{
    $item = Get-Item -LiteralPath $path -ErrorAction Stop
    return [string]$item.GetValue('')
  }} catch {{
    return ''
  }}
}}

try {{
  $extension = [System.IO.Path]::GetExtension($targetFile).ToLowerInvariant()
  $resolvedProgId = ''
  if (-not [string]::IsNullOrWhiteSpace($extension)) {{
    $userChoicePath = "Registry::HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\$extension\UserChoice"
    try {{
      $userChoice = Get-ItemProperty -LiteralPath $userChoicePath -ErrorAction Stop
      $defaultProgId = [string]$userChoice.ProgId
      $resolvedProgId = $defaultProgId
      Add-CandidatesFromText $defaultProgId
      if (-not [string]::IsNullOrWhiteSpace($defaultProgId)) {{
        Add-CandidatesFromText (Get-RegistryDefaultValue ("Registry::HKEY_CLASSES_ROOT\" + $defaultProgId + "\shell\open\command"))
      }}
    }} catch {{}}
    $extensionProgId = Get-RegistryDefaultValue ("Registry::HKEY_CLASSES_ROOT\" + $extension)
    Add-CandidatesFromText $extensionProgId
    if ([string]::IsNullOrWhiteSpace($resolvedProgId) -and -not [string]::IsNullOrWhiteSpace($extensionProgId)) {{
      $resolvedProgId = $extensionProgId
    }}
    if (-not [string]::IsNullOrWhiteSpace($resolvedProgId)) {{
      Add-CandidatesFromText (Get-RegistryDefaultValue ("Registry::HKEY_CLASSES_ROOT\" + $resolvedProgId + "\shell\open\command"))
    }}
  }}
}} catch {{}}

Add-AppCandidate 'Excel.Application'
Add-AppCandidate 'ket.Application'

try {{
  foreach ($progId in $progIds) {{
    if ($null -ne $app) {{ break }}
    try {{
      $app = [Runtime.InteropServices.Marshal]::GetActiveObject($progId)
    }} catch {{}}
  }}
  if ($null -eq $app) {{
    foreach ($progId in $progIds) {{
      if ($null -ne $app) {{ break }}
      try {{
        $app = New-Object -ComObject $progId
      }} catch {{}}
    }}
  }}
  if ($null -eq $app) {{
    throw '未能启动 Excel 或 WPS。'
  }}
  $app.Visible = $true
  $app.DisplayAlerts = $false
  $app.UserControl = $true
  $workbook = $null
  foreach ($wb in @($app.Workbooks)) {{
    if ([string]::Equals([System.IO.Path]::GetFullPath($wb.FullName), $targetFile, [System.StringComparison]::OrdinalIgnoreCase)) {{
      $workbook = $wb
      break
    }}
  }}
  if ($null -eq $workbook) {{
    $workbook = $app.Workbooks.Open($targetFile)
  }}
  $workbook.Activate() | Out-Null
  if ($selectCell) {{
    $worksheet = $null
    foreach ($ws in @($workbook.Worksheets)) {{
      if ([string]::Equals([string]$ws.Name, $targetSheet, [System.StringComparison]::OrdinalIgnoreCase)) {{
        $worksheet = $ws
        break
      }}
    }}
    if ($null -eq $worksheet) {{
      throw ('未找到工作表: ' + $targetSheet)
    }}
    $worksheet.Activate() | Out-Null
    $range = $worksheet.Range($targetCell)
    $range.Select() | Out-Null
    if ($app.ActiveWindow -ne $null) {{
      $app.ActiveWindow.ScrollRow = [Math]::Max(1, $range.Row - 3)
      $app.ActiveWindow.ScrollColumn = [Math]::Max(1, $range.Column - 1)
    }}
  }}
  try {{
    if ($app.WindowState -ne $null) {{
      $app.WindowState = -4143
    }}
  }} catch {{}}
  try {{
    $hwnd = [IntPtr]::new([int64]$app.Hwnd)
    [YeeheWin32]::ShowWindowAsync($hwnd, 9) | Out-Null
    Start-Sleep -Milliseconds 120
    [YeeheWin32]::SetForegroundWindow($hwnd) | Out-Null
  }} catch {{}}
}} catch {{
  throw $_
}}
"""
