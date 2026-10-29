Add-Type -AssemblyName System.Drawing

$imagesDirectory = Join-Path $PSScriptRoot '..\static\images'
$imagesDirectory = [System.IO.Path]::GetFullPath($imagesDirectory)

function New-RoundedRectanglePath {
    param(
        [System.Drawing.RectangleF]$Rectangle,
        [float]$Radius
    )

    $diameter = $Radius * 2
    $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
    $path.AddArc($Rectangle.X, $Rectangle.Y, $diameter, $diameter, 180, 90)
    $path.AddArc($Rectangle.Right - $diameter, $Rectangle.Y, $diameter, $diameter, 270, 90)
    $path.AddArc($Rectangle.Right - $diameter, $Rectangle.Bottom - $diameter, $diameter, $diameter, 0, 90)
    $path.AddArc($Rectangle.X, $Rectangle.Bottom - $diameter, $diameter, $diameter, 90, 90)
    $path.CloseFigure()
    return $path
}

function Draw-BrandMark {
    param(
        [System.Drawing.Graphics]$Graphics,
        [System.Drawing.RectangleF]$Bounds
    )

    $path = New-RoundedRectanglePath -Rectangle $Bounds -Radius ($Bounds.Width * 0.22)
    $gradient = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
        $Bounds,
        [System.Drawing.ColorTranslator]::FromHtml('#4668ff'),
        [System.Drawing.ColorTranslator]::FromHtml('#6c42ee'),
        45
    )
    $Graphics.FillPath($gradient, $path)

    $penWidth = [Math]::Max(4, $Bounds.Width * 0.065)
    $pen = [System.Drawing.Pen]::new([System.Drawing.Color]::White, $penWidth)
    $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round

    $x = $Bounds.X
    $y = $Bounds.Y
    $w = $Bounds.Width
    $h = $Bounds.Height
    $Graphics.DrawLines($pen, @(
        [System.Drawing.PointF]::new($x + $w * 0.39, $y + $h * 0.30),
        [System.Drawing.PointF]::new($x + $w * 0.22, $y + $h * 0.50),
        [System.Drawing.PointF]::new($x + $w * 0.39, $y + $h * 0.70)
    ))
    $Graphics.DrawLines($pen, @(
        [System.Drawing.PointF]::new($x + $w * 0.61, $y + $h * 0.30),
        [System.Drawing.PointF]::new($x + $w * 0.78, $y + $h * 0.50),
        [System.Drawing.PointF]::new($x + $w * 0.61, $y + $h * 0.70)
    ))
    $Graphics.DrawLine($pen, $x + $w * 0.56, $y + $h * 0.22, $x + $w * 0.44, $y + $h * 0.78)

    $pen.Dispose()
    $gradient.Dispose()
    $path.Dispose()
}

$shareImage = [System.Drawing.Bitmap]::new(1200, 630)
$graphics = [System.Drawing.Graphics]::FromImage($shareImage)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

$background = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
    [System.Drawing.RectangleF]::new(0, 0, 1200, 630),
    [System.Drawing.ColorTranslator]::FromHtml('#061120'),
    [System.Drawing.ColorTranslator]::FromHtml('#102748'),
    12
)
$graphics.FillRectangle($background, 0, 0, 1200, 630)

$glow = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(35, 56, 212, 200))
$graphics.FillEllipse($glow, 820, -180, 540, 540)
$graphics.FillEllipse($glow, -180, 410, 430, 430)

Draw-BrandMark -Graphics $graphics -Bounds ([System.Drawing.RectangleF]::new(82, 78, 116, 116))

$brandFont = [System.Drawing.Font]::new('Segoe UI', 35, [System.Drawing.FontStyle]::Bold)
$headlineFont = [System.Drawing.Font]::new('Segoe UI', 58, [System.Drawing.FontStyle]::Bold)
$bodyFont = [System.Drawing.Font]::new('Segoe UI', 24, [System.Drawing.FontStyle]::Regular)
$smallFont = [System.Drawing.Font]::new('Segoe UI', 18, [System.Drawing.FontStyle]::Bold)
$white = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White)
$muted = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#afbdd0'))
$cyan = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#38d4c8'))

$graphics.DrawString('MENA Tech Careers', $brandFont, $white, 226, 103)
$graphics.DrawString('TECHNOLOGY CAREERS ACROSS MENA', $smallFont, $cyan, 84, 250)
$graphics.DrawString('Your next tech role', $headlineFont, $white, 78, 295)
$graphics.DrawString('starts here.', $headlineFont, $cyan, 78, 368)
$graphics.DrawString('Software  |  ERP  |  Data  |  Cloud  |  DevOps  |  IT', $bodyFont, $muted, 84, 485)
$graphics.DrawString('menatechcareers.vercel.app', $smallFont, $white, 84, 548)

$sharePath = Join-Path $imagesDirectory 'social-share.png'
$shareImage.Save($sharePath, [System.Drawing.Imaging.ImageFormat]::Png)

$favicon = [System.Drawing.Bitmap]::new(192, 192)
$faviconGraphics = [System.Drawing.Graphics]::FromImage($favicon)
$faviconGraphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$faviconGraphics.Clear([System.Drawing.Color]::Transparent)
Draw-BrandMark -Graphics $faviconGraphics -Bounds ([System.Drawing.RectangleF]::new(0, 0, 192, 192))
$faviconPath = Join-Path $imagesDirectory 'favicon-192.png'
$favicon.Save($faviconPath, [System.Drawing.Imaging.ImageFormat]::Png)

$faviconGraphics.Dispose()
$favicon.Dispose()
$graphics.Dispose()
$shareImage.Dispose()
$background.Dispose()
$glow.Dispose()
$brandFont.Dispose()
$headlineFont.Dispose()
$bodyFont.Dispose()
$smallFont.Dispose()
$white.Dispose()
$muted.Dispose()
$cyan.Dispose()

Write-Output "Generated $sharePath and $faviconPath"
