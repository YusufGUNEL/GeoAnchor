"""Uçuş dizisi yükleme ve temel türetilmiş büyüklükler."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .geo import haversine_m_array, latlon_to_local_m


@dataclass
class Flight:
    """Tek bir İHA uçuşu: kareler, gerçek konumlar, uydu haritası yolu."""
    flight_id: str
    root: Path
    df: pd.DataFrame          # kare başına üstveri
    satellite_path: Path
    lat0: float               # yerel düzlem başlangıcı
    lon0: float

    @property
    def n_frames(self) -> int:
        return len(self.df)

    def image_path(self, i: int) -> Path:
        return self.root / "drone" / self.df.iloc[i]["filename"]

    def summary(self) -> str:
        d = self.df
        total_km = d["cum_dist_m"].iloc[-1] / 1000
        return (
            f"Uçuş {self.flight_id}: {self.n_frames} kare\n"
            f"  tarih         : {d['date'].iloc[0]} → {d['date'].iloc[-1]}\n"
            f"  süre          : {d['t_s'].iloc[-1]:.0f} sn ({d['t_s'].iloc[-1]/60:.1f} dk)\n"
            f"  irtifa        : {d['height'].min():.1f} – {d['height'].max():.1f} m "
            f"(ort {d['height'].mean():.1f})\n"
            f"  kat edilen yol: {total_km:.2f} km\n"
            f"  kare aralığı  : {d['step_m'][1:].mean():.1f} m ort "
            f"({d['step_m'][1:].min():.1f} – {d['step_m'][1:].max():.1f})\n"
            f"  yer hızı      : {d['speed_ms'][1:].mean():.1f} m/sn\n"
            f"  yönelim (Phi1): {d['Phi1'].min():.1f}° – {d['Phi1'].max():.1f}°\n"
            f"  eğim (Omega)  : {d['Omega'].min():.2f}° – {d['Omega'].max():.2f}°\n"
            f"  yalpa (Kappa) : {d['Kappa'].min():.2f}° – {d['Kappa'].max():.2f}°"
        )


def load_flight(data_root: str | Path, flight_id: str = "03") -> Flight:
    """UAV-VisLoc uçuş klasörünü yükler ve türetilmiş sütunları ekler."""
    root = Path(data_root) / flight_id
    df = pd.read_csv(root / f"{flight_id}.csv")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("num").reset_index(drop=True)

    # zaman (sn), başlangıçtan itibaren
    df["t_s"] = (df["date"] - df["date"].iloc[0]).dt.total_seconds()

    # ardışık kareler arası mesafe ve hız
    step = np.zeros(len(df))
    step[1:] = haversine_m_array(df["lat"].values[:-1], df["lon"].values[:-1],
                                 df["lat"].values[1:], df["lon"].values[1:])
    df["step_m"] = step
    dt = np.diff(df["t_s"].values, prepend=df["t_s"].values[0])
    df["speed_ms"] = np.divide(step, dt, out=np.zeros_like(step), where=dt > 0)
    df["cum_dist_m"] = np.cumsum(step)

    # yerel düzlem koordinatları (ilk kare başlangıç)
    lat0, lon0 = float(df["lat"].iloc[0]), float(df["lon"].iloc[0])
    north, east = latlon_to_local_m(df["lat"].values, df["lon"].values, lat0, lon0)
    df["north_m"] = north
    df["east_m"] = east

    return Flight(flight_id=flight_id, root=root, df=df,
                  satellite_path=root / f"satellite{flight_id}.tif",
                  lat0=lat0, lon0=lon0)
