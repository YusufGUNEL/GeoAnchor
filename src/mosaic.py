"""Cok parcali uydu haritalarini tek bir sanal raster olarak sunar.

Bazi ucuslarda temel harita tek dosya degil, duzenli bir izgaraya bolunmus
birkac GeoTIFF olarak geliyor (ornegin ucus 09: 2x2, toplam 4,5 GB). Gercek
konuslandirmalarda da haritalar karolu gelir, dolayisiyla bu bir istisna degil
normal durum.

Dosyalari birlestirip diske yazmak 4,5 GB'lik bir kopya demek olurdu. Bunun
yerine GDAL'in sanal raster (VRT) bicimi kullaniliyor: kaynaklara isaret eden
kucuk bir XML. rasterio bunu tek bir raster gibi aciyor, pencere okumalari
dogru kaynaga yonlendiriliyor, hicbir sey kopyalanmiyor.
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

import rasterio


def build_vrt(tif_paths: list[str | Path], out_path: str | Path) -> Path:
    """Duzenli izgaraya dizilmis GeoTIFF'lerden bir VRT uretir.

    Kaynaklarin ayni piksel boyutuna ve ayni koordinat sistemine sahip oldugu
    varsayilir — bir haritanin parcalari icin bu zaten gecerlidir.
    """
    tifs = [Path(p) for p in tif_paths]
    if not tifs:
        raise ValueError("kaynak dosya listesi bos")

    metas = []
    for p in tifs:
        with rasterio.open(p) as d:
            metas.append({"path": p, "w": d.width, "h": d.height,
                          "b": d.bounds, "count": d.count,
                          "dtype": d.dtypes[0], "crs": d.crs,
                          "res_x": (d.bounds.right - d.bounds.left) / d.width,
                          "res_y": (d.bounds.top - d.bounds.bottom) / d.height})

    res_x = metas[0]["res_x"]
    res_y = metas[0]["res_y"]
    left = min(m["b"].left for m in metas)
    right = max(m["b"].right for m in metas)
    top = max(m["b"].top for m in metas)
    bottom = min(m["b"].bottom for m in metas)
    W = int(round((right - left) / res_x))
    H = int(round((top - bottom) / res_y))
    count = metas[0]["count"]
    dtype = {"uint8": "Byte", "uint16": "UInt16", "float32": "Float32"}.get(
        metas[0]["dtype"], "Byte")
    crs = metas[0]["crs"]
    epsg = crs.to_string() if crs else "EPSG:4326"

    lines = [f'<VRTDataset rasterXSize="{W}" rasterYSize="{H}">',
             f'  <SRS>{escape(epsg)}</SRS>',
             f'  <GeoTransform>{left}, {res_x}, 0.0, {top}, 0.0, {-res_y}</GeoTransform>']
    for band in range(1, count + 1):
        lines.append(f'  <VRTRasterBand dataType="{dtype}" band="{band}">')
        for m in metas:
            xoff = int(round((m["b"].left - left) / res_x))
            yoff = int(round((top - m["b"].top) / res_y))
            lines += [
                '    <SimpleSource>',
                f'      <SourceFilename relativeToVRT="0">{escape(str(m["path"]))}</SourceFilename>',
                f'      <SourceBand>{band}</SourceBand>',
                f'      <SrcRect xOff="0" yOff="0" xSize="{m["w"]}" ySize="{m["h"]}"/>',
                f'      <DstRect xOff="{xoff}" yOff="{yoff}" xSize="{m["w"]}" ySize="{m["h"]}"/>',
                '    </SimpleSource>']
        lines.append('  </VRTRasterBand>')
    lines.append('</VRTDataset>')

    out = Path(out_path)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def resolve_basemap(flight_dir: str | Path, flight_id: str) -> Path:
    """Bir ucusun temel haritasini bulur; parcaliysa VRT uretip onu dondurur."""
    d = Path(flight_dir)
    single = d / f"satellite{flight_id}.tif"
    if single.exists():
        return single
    parts = sorted(d.glob(f"satellite{flight_id}_*.tif"))
    if not parts:
        raise FileNotFoundError(f"ucus {flight_id}: temel harita bulunamadi")
    vrt = d / f"satellite{flight_id}.vrt"
    if not vrt.exists():
        build_vrt(parts, vrt)
    return vrt
