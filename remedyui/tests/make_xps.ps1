# Writes a real XPS file with Windows' own writer (WPF), for tests/xps.py.
# Run with Windows PowerShell: powershell.exe -STA -File make_xps.ps1 out.xps picture.png
param([string]$Out, [string]$Picture)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName ReachFramework, PresentationCore, PresentationFramework, WindowsBase, System.Printing

$xaml = @"
<FixedDocument xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation">
 <PageContent>
  <FixedPage Width="816" Height="1056" Background="White">
   <TextBlock FixedPage.Left="96" FixedPage.Top="80" FontFamily="Arial" FontSize="36" FontWeight="Bold">Quarterly report</TextBlock>
   <TextBlock FixedPage.Left="96" FixedPage.Top="150" FontFamily="Times New Roman" FontSize="20" Width="600" TextWrapping="Wrap">The quick brown fox jumps over the lazy dog. Officially, AVATAR waffles cost 1234 each. Zo&#xEB; and na&#xEF;ve caf&#xE9;.</TextBlock>
   <TextBlock FixedPage.Left="96" FixedPage.Top="230" FontFamily="Segoe UI" FontSize="22" FontStyle="Italic" Foreground="#FF1E4FC0">Italic blue words</TextBlock>
   <TextBlock FixedPage.Left="500" FixedPage.Top="230" FontFamily="Arial" FontSize="22" FlowDirection="RightToLeft">&#x5E9;&#x5DC;&#x5D5;&#x5DD;</TextBlock>
   <Rectangle FixedPage.Left="96" FixedPage.Top="300" Width="200" Height="120" Fill="#FFC81E1E" Stroke="Black" StrokeThickness="4"/>
   <Ellipse FixedPage.Left="330" FixedPage.Top="300" Width="200" Height="120" Stroke="#FF117733" StrokeThickness="8" StrokeDashArray="3 1">
    <Ellipse.Fill><RadialGradientBrush><GradientStop Color="Yellow" Offset="0"/><GradientStop Color="#FF2050C0" Offset="1"/></RadialGradientBrush></Ellipse.Fill>
   </Ellipse>
   <Rectangle FixedPage.Left="560" FixedPage.Top="300" Width="160" Height="120">
    <Rectangle.Fill><LinearGradientBrush StartPoint="0,0" EndPoint="1,1"><GradientStop Color="White" Offset="0"/><GradientStop Color="Black" Offset="1"/></LinearGradientBrush></Rectangle.Fill>
   </Rectangle>
   <Path FixedPage.Left="96" FixedPage.Top="460" Fill="#80FF8800" Stroke="#FF000000" StrokeThickness="2" Data="M 0,100 C 40,0 120,0 160,100 S 260,200 300,100 L 300,180 A 80,40 0 0 1 140,180 Z"/>
   <Image FixedPage.Left="450" FixedPage.Top="470" Width="240" Height="120" Source="$Picture"/>
   <Canvas FixedPage.Left="150" FixedPage.Top="720">
    <Canvas.RenderTransform><RotateTransform Angle="-12"/></Canvas.RenderTransform>
    <TextBlock FontFamily="Courier New" FontSize="28">Rotated monospace text</TextBlock>
   </Canvas>
   <Rectangle FixedPage.Left="450" FixedPage.Top="650" Width="250" Height="150" Fill="#FF208080">
    <Rectangle.Clip><EllipseGeometry Center="125,75" RadiusX="110" RadiusY="60"/></Rectangle.Clip>
   </Rectangle>
   <Rectangle FixedPage.Left="96" FixedPage.Top="860" Width="620" Height="80">
    <Rectangle.Fill><ImageBrush ImageSource="$Picture" TileMode="Tile" ViewportUnits="Absolute" Viewport="0,0,80,40"/></Rectangle.Fill>
   </Rectangle>
  </FixedPage>
 </PageContent>
 <PageContent>
  <FixedPage Width="1056" Height="816" Background="White">
   <TextBlock FixedPage.Left="96" FixedPage.Top="80" FontFamily="Georgia" FontSize="28">Second page, turned sideways</TextBlock>
  </FixedPage>
 </PageContent>
 <PageContent>
  <FixedPage Width="400" Height="300" Background="White">
   <Rectangle FixedPage.Left="40" FixedPage.Top="20" Width="320" Height="130">
    <Rectangle.Fill><VisualBrush TileMode="Tile" Viewport="0,0,80,60" ViewportUnits="Absolute"><VisualBrush.Visual><Canvas Width="80" Height="60"><Ellipse Width="50" Height="40" Fill="Green"/><Rectangle Canvas.Left="45" Canvas.Top="30" Width="30" Height="25" Fill="Orange"/></Canvas></VisualBrush.Visual></VisualBrush></Rectangle.Fill>
   </Rectangle>
   <Rectangle FixedPage.Left="40" FixedPage.Top="170" Width="320" Height="110" Fill="#FF204080">
    <Rectangle.OpacityMask><LinearGradientBrush StartPoint="0,0" EndPoint="1,0"><GradientStop Color="#FF000000" Offset="0"/><GradientStop Color="#00000000" Offset="1"/></LinearGradientBrush></Rectangle.OpacityMask>
   </Rectangle>
  </FixedPage>
 </PageContent>
</FixedDocument>
"@

$document = [System.Windows.Markup.XamlReader]::Parse($xaml)
foreach ($content in $document.Pages) {
    $page = $content.Child
    $size = New-Object System.Windows.Size($page.Width, $page.Height)
    $page.Measure($size)
    $page.Arrange((New-Object System.Windows.Rect($size)))
    $page.UpdateLayout()
}
if (Test-Path $Out) { Remove-Item $Out }
$package = New-Object System.Windows.Xps.Packaging.XpsDocument($Out, [System.IO.FileAccess]::ReadWrite)
[System.Windows.Xps.Packaging.XpsDocument]::CreateXpsDocumentWriter($package).Write($document)
$package.Close()
