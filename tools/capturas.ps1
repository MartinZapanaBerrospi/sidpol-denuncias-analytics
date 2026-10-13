# Captura cada página del informe abierto en Power BI Desktop, sin mover el mouse ni robar el foco.
# Cambia de página con UI Automation y captura la ventana con PrintWindow (funciona aunque esté tapada).
#
# Uso:  powershell -ExecutionPolicy Bypass -File tools\capturas.ps1 -Salida <carpeta> [-Recorte]
param(
    [Parameter(Mandatory = $true)][string]$Salida,
    [switch]$Recorte
)

Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, System.Drawing
Add-Type @'
using System; using System.Runtime.InteropServices;
public static class Win {
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
'@

$paginas = @("1. Resumen", "2. Modalidades", "3. Territorio", "4. Distritos", "5. Alertas", "6. Calendario", "7. Notas")
$proc = Get-Process PBIDesktop | Where-Object MainWindowTitle | Select-Object -First 1
if (-not $proc) { throw "Power BI Desktop no está abierto" }
$hwnd = $proc.MainWindowHandle
$raiz = [System.Windows.Automation.AutomationElement]::FromHandle($hwnd)
New-Item -ItemType Directory -Force $Salida | Out-Null

# Si la ventana está minimizada, se restaura sin activarla y se manda al fondo: no roba el foco ni tapa
# otras ventanas. El árbol de accesibilidad y PrintWindow necesitan la ventana restaurada.
$estabaMinimizada = [Win]::IsIconic($hwnd)
if ($estabaMinimizada) { [Win]::ShowWindow($hwnd, 4) | Out-Null }           # SW_SHOWNOACTIVATE
# Tamaño fijo para que el lienzo entre completo; al fondo y sin activar
[Win]::SetWindowPos($hwnd, [IntPtr]1, 0, 0, 1920, 1040, 0x0010) | Out-Null   # HWND_BOTTOM; NOACTIVATE
Start-Sleep -Seconds 5

function Capturar([string]$archivo) {
    $r = New-Object Win+RECT; [Win]::GetWindowRect($hwnd, [ref]$r) | Out-Null
    $w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp); $hdc = $g.GetHdc()
    [Win]::PrintWindow($hwnd, $hdc, 2) | Out-Null          # 2 = PW_RENDERFULLCONTENT
    $g.ReleaseHdc($hdc); $g.Dispose()
    $bmp.Save($archivo, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
}

for ($i = 0; $i -lt $paginas.Count; $i++) {
    $nombre = $paginas[$i]
    # Busca la pestaña por el número de página ("3. "), que no depende de tildes ni del estado de la pestaña
    $prefijo = $nombre.Substring(0, 3)
    $pestana = $null
    # El árbol de accesibilidad tarda en cargarse tras restaurar la ventana: hasta 5 intentos
    for ($intento = 0; $intento -lt 5 -and -not $pestana; $intento++) {
        if ($intento) { Start-Sleep -Seconds 3 }
        foreach ($e in $raiz.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)) {
            if ($e.Current.Name -and $e.Current.Name.StartsWith($prefijo) -and $e.Current.Name.Length -lt 40) {
                $p0 = $null
                if ($e.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern, [ref]$p0) -or
                    $e.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$p0)) { $pestana = $e; break }
            }
        }
    }
    if (-not $pestana) { Write-Warning "No se encontró la pestaña '$nombre'"; continue }
    $patron = $null
    if ($pestana.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern, [ref]$patron)) { $patron.Select() }
    elseif ($pestana.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$patron)) { $patron.Invoke() }
    else { Write-Warning "La pestaña '$nombre' no se puede seleccionar"; continue }
    Start-Sleep -Seconds 6
    $archivo = Join-Path $Salida ("{0:D2}_pagina.png" -f ($i + 1))
    Capturar $archivo
    Write-Output "$nombre -> $archivo"
}

if ($estabaMinimizada) { [Win]::ShowWindow($hwnd, 7) | Out-Null }           # SW_SHOWMINNOACTIVE: la deja como estaba
