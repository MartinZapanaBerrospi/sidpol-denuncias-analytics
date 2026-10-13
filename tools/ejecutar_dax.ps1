# Ejecuta una consulta DAX contra el modelo abierto en Power BI Desktop y guarda el resultado como CSV.
# Sirve para tools/validate_measures.py cuando no se usa el MCP de modelado.
#
# Uso:  powershell -ExecutionPolicy Bypass -File tools\ejecutar_dax.ps1 -Puerto 53583 -Consulta tools\validacion_medidas.dax -Salida reports\medidas_dax.csv
param(
    [Parameter(Mandatory = $true)][int]$Puerto,
    [Parameter(Mandatory = $true)][string]$Consulta,
    [Parameter(Mandatory = $true)][string]$Salida
)

# La biblioteca ADOMD.NET viene con SQL Server o con las herramientas de Analysis Services.
$dll = Get-ChildItem "C:\Program Files", "C:\Program Files (x86)" -Recurse -Filter "Microsoft.AnalysisServices.AdomdClient.dll" -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $dll) { throw "No se encontró Microsoft.AnalysisServices.AdomdClient.dll" }
try { Add-Type -Path $dll } catch { }          # avisa de tipos opcionales que no se cargan; los necesarios sí quedan

$conexion = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$Puerto")
$conexion.Open()
$comando = $conexion.CreateCommand()
$comando.CommandText = Get-Content -Raw -Encoding UTF8 $Consulta
$comando.CommandTimeout = 300
$lector = $comando.ExecuteReader()
$filas = New-Object System.Collections.Generic.List[string]
$cabecera = 0..($lector.FieldCount - 1) | ForEach-Object { '"' + $lector.GetName($_) + '"' }
$filas.Add(($cabecera -join ","))
while ($lector.Read()) {
    $celdas = 0..($lector.FieldCount - 1) | ForEach-Object {
        $v = $lector.GetValue($_)
        if ($v -eq $null) { '' } else { '"' + ([string]$v).Replace('"', '""') + '"' }
    }
    $filas.Add(($celdas -join ","))
}
$lector.Close(); $conexion.Close()
[System.IO.File]::WriteAllLines((Join-Path (Get-Location) $Salida), $filas, (New-Object System.Text.UTF8Encoding($false)))
Write-Output "$($filas.Count - 1) filas -> $Salida"
