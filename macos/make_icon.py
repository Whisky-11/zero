"""Render Zero.icns (a white ring on black, like the HUD core) with AppKit.
Usage: python macos/make_icon.py out.icns   — used by build-app.sh."""
import os
import subprocess
import sys
import tempfile

from AppKit import (NSBezierPath, NSBitmapImageRep, NSColor, NSGraphicsContext,
                    NSPNGFileType, NSMakeRect)


def render(px: int, path: str) -> None:
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, px, px, 8, 4, True, False, "NSDeviceRGBColorSpace", 0, 0)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
    m = px * 0.1
    NSColor.colorWithCalibratedWhite_alpha_(0.03, 1).setFill()
    NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        NSMakeRect(m, m, px - 2 * m, px - 2 * m), px * 0.18, px * 0.18).fill()
    NSColor.whiteColor().setStroke()
    for r, w in ((0.30, 0.035), (0.12, 0.03)):
        c = NSBezierPath.bezierPathWithOvalInRect_(
            NSMakeRect(px / 2 - px * r, px / 2 - px * r, 2 * px * r, 2 * px * r))
        c.setLineWidth_(px * w)
        c.stroke()
    NSGraphicsContext.restoreGraphicsState()
    rep.representationUsingType_properties_(NSPNGFileType, None).writeToFile_atomically_(path, True)


def main(out: str) -> None:
    d = tempfile.mkdtemp(suffix=".iconset")
    for s in (16, 32, 128, 256, 512):
        render(s, os.path.join(d, f"icon_{s}x{s}.png"))
        render(s * 2, os.path.join(d, f"icon_{s}x{s}@2x.png"))
    subprocess.run(["iconutil", "-c", "icns", d, "-o", out], check=True)


if __name__ == "__main__":
    main(sys.argv[1])
