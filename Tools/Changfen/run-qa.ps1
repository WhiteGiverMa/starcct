param(
    [string]$BaselineQa = 'C:\Users\A1337\AppData\Local\Temp\opencode\starcct-holosignboard-20261111\qa',
    [string]$WorkDir = 'C:\Users\A1337\AppData\Local\Temp\opencode\starcct-changfen-20261113\qa'
)
$ErrorActionPreference = 'Stop'
py -3.15 (Join-Path $PSScriptRoot '..\HoloSignboard\test_wall_rotation.py')
if ($LASTEXITCODE -ne 0) { throw 'Wall texture rotation QA failed' }
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
if (!(Test-Path (Join-Path $BaselineQa 'QA.csproj'))) {
    throw "Baseline 939-check QA project not found: $BaselineQa"
}
dotnet build (Join-Path $root 'Source\AyameICCT\AyameICCT.csproj') -c Release -warnaserror
if ($LASTEXITCODE -ne 0) { throw 'Mod build failed' }
New-Item -ItemType Directory -Force $WorkDir | Out-Null
Get-ChildItem $BaselineQa -File | Copy-Item -Destination $WorkDir -Force
$project = Join-Path $WorkDir 'QA.csproj'
$text = Get-Content $project -Raw
$reference = '<Reference Include="AyameICCT"><HintPath>' + (Join-Path $root 'Assemblies\AyameICCT.dll') + '</HintPath></Reference>'
$text = [regex]::Replace($text, '<Reference Include="AyameICCT">.*?</Reference>', { param($match) $reference })
if (!$text.Contains('<Reference Include="Waylith">')) {
    $text = $text.Replace('<Reference Include="UnityStubs">', '<Reference Include="Waylith"><HintPath>$(GameRoot)/Waylith.dll</HintPath></Reference><Reference Include="UnityStubs">')
}
$text = $text.Replace('<ItemGroup>', '<ItemGroup><Compile Include="' + (Join-Path $PSScriptRoot 'Changfen.cs') + '" />')
Set-Content $project $text -Encoding utf8
$program = Join-Path $WorkDir 'Program.cs'
$text = (Get-Content $program -Raw).Replace('        Console.WriteLine("QA passed:', "        TestChangfen();`n        Console.WriteLine(`"QA passed:")
Set-Content $program $text -Encoding utf8
$env:EXPERIMENT_QA_CASE = 'all'
$env:REPROGRAM_QA_CASE = 'all'
$env:SHOP_QA_CASE = 'all'
dotnet run --project $project -c Release -warnaserror
if ($LASTEXITCODE -ne 0) { throw 'QA failed' }
