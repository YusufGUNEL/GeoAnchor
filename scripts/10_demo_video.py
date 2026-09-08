"""Faz 6 — gosterim videosu (LinkedIn/README icin).

Duzen (16:9, cerceve tam doldurulur):
  sol       : IHA kamerasi, kuzey-yukari
  sag ust   : uydu haritasinda canli konum + gercek yorunge + belirsizlik
  sag alt   : hata egrisi (odometri vs fuzyon), o ana kadar

Cikti: figures/demo.mp4 (h264) ve figures/demo.gif (README icin kisa surum)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

from src.figtext import figdir, pick
from src.flight import load_flight
from src.geo import SatelliteMap, local_m_to_latlon

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(r"D:\GeoAnchorData\cache")
FIG = figdir()

T = pick({
 "en": {
  "cam": "UAV camera   ·   frame {}/{}   ·   altitude {:.0f} m",
  "map": "NO GPS   ·   absolute position on the satellite map   ·   {}",
  "hud": "error {:5.1f} m     flown {:5.1f} km",
  "vo": "odometry only",
  "pf": "fusion",
  "x": "distance flown (km)",
  "y": "error (m)",
 },
 "tr": {
  "cam": "IHA kamerasi   ·   kare {}/{}   ·   irtifa {:.0f} m",
  "map": "GPS YOK   ·   uydu haritasinda mutlak konum   ·   {}",
  "hud": "hata {:5.1f} m     yol {:5.1f} km",
  "vo": "sadece odometri",
  "pf": "fuzyon",
  "x": "kat edilen yol (km)",
  "y": "hata (m)",
 },
})

FPS = 15
# The GIF is a 12-second excerpt at 10 fps, so 120 frames -- which is also what
# the README caption claims it is. 640x360 and 64 colours keep it under 8 MB;
# at 800x450 and full colour the same animation came out at 32 MB, which GitHub
# will not render inline.
GIF_EVERY, GIF_FRAMES, GIF_SIZE, GIF_COLORS = 6, 120, (640, 360), 128
BG = "#0a0a0e"
C_GT = "#7fdfff"
C_PF = "#00ff6a"
C_VO = "#ff2d55"


def main():
    flight = load_flight(r"D:\GeoAnchorData\raw", "03")
    sat = SatelliteMap(flight.satellite_path)
    q = np.load(CACHE / "northup_03_640.npy", mmap_mode="r")
    z = np.load(ROOT / "results" / "07_sequential_ana.npz")
    vo = np.load(ROOT / "results" / "06_odometry.npz")
    d = flight.df

    lat0, lon0 = float(d["lat"].iloc[0]), float(d["lon"].iloc[0])
    gt_n, gt_e = d["north_m"].values, d["east_m"].values
    pf_n, pf_e, err, spread = z["north"], z["east"], z["err"], z["spread"]
    modes = z["modes"]
    vo_err = vo["err"]

    ov = sat.overview(1200)
    sx, sy = ov.shape[1] / sat.width, ov.shape[0] / sat.height

    def to_px(n, e):
        la, lo = local_m_to_latlon(n, e, lat0, lon0)
        x, y = sat.latlon_to_px(la, lo)
        return np.asarray(x) * sx, np.asarray(y) * sy

    gx, gy = to_px(gt_n, gt_e)
    px, py = to_px(pf_n, pf_e)
    vx, vy = to_px(vo["vo_north"], vo["vo_east"])
    km = d["cum_dist_m"].values / 1000
    n = len(d)
    px_per_m = float(np.hypot(gx[20] - gx[0], gy[20] - gy[0])
                     / max(1e-6, np.hypot(gt_n[20] - gt_n[0], gt_e[20] - gt_e[0])))

    ov_ar = ov.shape[1] / ov.shape[0]
    fig = plt.figure(figsize=(16, 9), dpi=100)
    fig.patch.set_facecolor(BG)

    # kamera: kare, yuksekligi cerceveyi doldurur
    cam_h = 0.84
    cam_w = cam_h * 9 / 16
    ax_cam = fig.add_axes([0.015, 0.08, cam_w, cam_h])
    # harita: en-boy orani korunacak sekilde sag ust
    map_w = 0.985 - (0.03 + cam_w)
    map_h = map_w * 16 / 9 / ov_ar
    map_h = min(map_h, 0.62)
    map_w = map_h * ov_ar * 9 / 16
    map_x = 0.03 + cam_w
    ax_map = fig.add_axes([map_x, 0.965 - map_h, map_w, map_h])
    ax_err = fig.add_axes([map_x + 0.05, 0.10, map_w - 0.06, 0.22])

    writer = None
    try:
        import imageio
        # Explicit bitrate rather than quality=: the quality scale is
        # interpreted differently across imageio-ffmpeg versions and the same
        # call that produced 16 MB once produced 81 MB later, which is too
        # large to ship to the Space.
        writer = imageio.get_writer(FIG / "demo.mp4", fps=FPS, codec="libx264",
                                    bitrate="2500k", macro_block_size=8)
    except Exception as ex:
        print("imageio yazici acilamadi:", ex)
        import cv2
        writer = None
        vw = cv2.VideoWriter(str(FIG / "demo.mp4"),
                             cv2.VideoWriter_fourcc(*"mp4v"), FPS, (1600, 900))

    gif_frames = []
    for i in range(n):
        for ax in (ax_cam, ax_map, ax_err):
            ax.clear()

        # --- kamera ---
        ax_cam.imshow(np.ascontiguousarray(q[i]))
        ax_cam.plot(320, 320, "+", color=C_PF, ms=18, mew=2.2)
        ax_cam.set_title(T["cam"]
                         .format(i + 1, n, d["height"].iloc[i]),
                         color="w", fontsize=12, pad=7)
        ax_cam.axis("off")

        # --- harita ---
        ax_map.imshow(ov)
        ax_map.plot(gx, gy, "-", lw=1.1, color=C_GT, alpha=0.45)
        ax_map.plot(vx[:i + 1], vy[:i + 1], "-", lw=1.3, color=C_VO, alpha=0.85)
        ax_map.plot(px[:i + 1], py[:i + 1], "-", lw=1.7, color=C_PF)
        if np.isfinite(px[i]):
            if np.isfinite(spread[i]):
                r = max(4.0, spread[i] * px_per_m * 3)
                ax_map.add_patch(Circle((px[i], py[i]), r, fill=False,
                                        color=C_PF, lw=1.3, alpha=0.85))
            ax_map.plot(px[i], py[i], "o", ms=9, color=C_PF, mec="k",
                        mew=0.7, zorder=6)
        ax_map.plot(gx[i], gy[i], "o", ms=6, color=C_GT, mec="k", mew=0.6, zorder=5)
        mode = str(modes[i]) if i < len(modes) else ""
        ax_map.set_title(T["map"]
                         .format(mode), color="w", fontsize=12, pad=7)
        ax_map.axis("off")
        ax_map.text(0.012, 0.025,
                    T["hud"].format(err[i], km[i]),
                    transform=ax_map.transAxes, color="w", fontsize=13,
                    family="monospace",
                    bbox=dict(fc="#000000cc", ec="none", pad=5))

        # --- hata egrisi ---
        ax_err.set_facecolor("#14141a")
        ax_err.plot(km[:i + 1], vo_err[:i + 1], color=C_VO, lw=1.3,
                    label=T["vo"])
        ax_err.plot(km[:i + 1], err[:i + 1], color=C_PF, lw=1.5, label=T["pf"])
        ax_err.set_xlim(0, km[-1])
        ax_err.set_yscale("log")
        ax_err.set_ylim(0.5, 4000)
        ax_err.set_xlabel(T["x"], color="w", fontsize=10)
        ax_err.set_ylabel(T["y"], color="w", fontsize=10)
        ax_err.tick_params(colors="w", labelsize=9)
        for s in ax_err.spines.values():
            s.set_color("#3a3a45")
        ax_err.grid(alpha=0.18, which="both", color="#666")
        ax_err.legend(fontsize=9, loc="upper left", facecolor="#14141a",
                      edgecolor="#3a3a45", labelcolor="w", ncol=2)

        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba())[:, :, :3]
        if writer is not None:
            writer.append_data(buf)
        else:
            import cv2
            vw.write(cv2.cvtColor(buf, cv2.COLOR_RGB2BGR))
        if i % GIF_EVERY == 0 and len(gif_frames) < GIF_FRAMES:
            import cv2
            gif_frames.append(cv2.resize(buf, GIF_SIZE))
        if (i + 1) % 150 == 0:
            print("  {}/{}".format(i + 1, n), flush=True)

    if writer is not None:
        writer.close()
    else:
        vw.release()
    plt.close(fig)
    mb = (FIG / "demo.mp4").stat().st_size / 1e6
    print("figures/demo.mp4 yazildi ({:.0f} sn, {:.1f} MB)".format(n / FPS, mb))

    try:
        import imageio
        # One adaptive palette for the whole animation, and disposal=1 so PIL
        # stores only what changes between frames. disposal=2 forces a full
        # frame every time and doubles the file for no visible gain.
        from PIL import Image
        imgs = [Image.fromarray(f) for f in gif_frames]
        # The palette comes from the whole animation, not from frame 0. At
        # frame 0 no trajectory has been drawn yet, so a palette taken there
        # spends every slot on the satellite imagery and quantises the three
        # tracks to grey -- which is the one thing the animation exists to
        # show. The track colours are then appended by hand: they cover a few
        # hundred thin-line pixels per frame, too few for median cut to keep
        # them however many frames it looks at.
        w, h = imgs[0].size
        sample = imgs[::4]
        strip = Image.new("RGB", (w, h * len(sample)))
        for k, im in enumerate(sample):
            strip.paste(im, (0, k * h))
        base = strip.quantize(colors=GIF_COLORS - 3, method=Image.MEDIANCUT)
        pal = base.getpalette()[: (GIF_COLORS - 3) * 3]
        for hexcol in (C_GT, C_PF, C_VO):
            pal += [int(hexcol[j:j + 2], 16) for j in (1, 3, 5)]
        pal_img = Image.new("P", (1, 1))
        pal_img.putpalette(pal + [0] * (768 - len(pal)))
        # No dithering: Floyd-Steinberg scatters the saturated track colours
        # across the camera image as green speckle, and costs 1.4 MB doing it.
        q = [im.quantize(palette=pal_img, dither=Image.NONE) for im in imgs]
        q[0].save(FIG / "demo.gif", save_all=True, append_images=q[1:],
                  duration=100, loop=0, optimize=True, disposal=1)
        print("figures/demo.gif yazildi ({:.1f} MB)".format(
            (FIG / "demo.gif").stat().st_size / 1e6))
    except Exception as ex:
        print("GIF atlandi:", ex)
    sat.close()


if __name__ == "__main__":
    main()
