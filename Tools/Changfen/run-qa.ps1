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
$text = $text.Replace('defName = "AyameICCT_PlasticSheet", label = "食品级塑料片", thingClass = typeof(ThingWithComps), category = ThingCategory.Item, useHitPoints = false, stackLimit = 75',
    'defName = "AyameICCT_PlasticSheet", label = "食品级塑料片", thingClass = typeof(ThingWithComps), category = ThingCategory.Item, useHitPoints = false, stackLimit = 320')
Set-Content $program $text -Encoding utf8
$shop = Join-Path $WorkDir 'Shop.cs'
$text = Get-Content $shop -Raw
$text = $text.Replace('contents.innerContainer.Count(t => t.def == shopSheetDef) == 7',
    'contents.innerContainer.Count(t => t.def == shopSheetDef) == 2')
$text = $text.Replace('goods are packed as legal 500-granule and 75-sheet stacks',
    'goods are packed as legal 500-granule and 320-sheet stacks')
$text = $text.Replace('maximum order: one pod with 40 + 267 legal stacks',
    'maximum order: one pod with 40 + 63 legal stacks')
$text = $text.Replace('bigContents.innerContainer.Count(t => t.def == shopSheetDef) == 267',
    'bigContents.innerContainer.Count(t => t.def == shopSheetDef) == 63')
$text = $text.Replace('maximum order is 40 granule stacks plus 267 sheet stacks, never 40000 Things',
    'maximum order is 40 granule stacks plus 63 sheet stacks, never 40000 Things')
$text = $text.Replace('bigContents.innerContainer.Where(t => t.def == shopSheetDef).Take(266).All(t => t.stackCount == 75)',
    'bigContents.innerContainer.Where(t => t.def == shopSheetDef).Take(62).All(t => t.stackCount == 320)')
$text = $text.Replace('bigContents.innerContainer.Where(t => t.def == shopSheetDef).Last().stackCount == 50',
    'bigContents.innerContainer.Where(t => t.def == shopSheetDef).Last().stackCount == 160')
Set-Content $shop $text -Encoding utf8
$env:EXPERIMENT_QA_CASE = 'all'
$env:REPROGRAM_QA_CASE = 'all'
$env:SHOP_QA_CASE = 'all'
dotnet run --project $project -c Release -warnaserror
if ($LASTEXITCODE -ne 0) { throw 'QA failed' }
