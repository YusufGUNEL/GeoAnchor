"""Küresel görüntü tanımlayıcıları (DINOv2).

Amaç: 8,8 x 7,3 km'lik uydu haritasını karolara bölüp her karo için bir vektör
üretmek, sonra İHA karesinin vektörüne en yakın karoları bulmak. Bu, pahalı
LoFTR eşlemesini binlerce karo yerine sadece birkaç adaya uygulamayı sağlar.

DINOv2 seçildi çünkü öz-denetimli eğitildiği için mevsim/aydınlatma değişimine
etiketli modellerden daha dayanıklı ve ince ayar gerektirmiyor — 4 GB'lık kartta
eğitim yapmadan çalışabilmek bu projenin kısıtı.
"""
from __future__ import annotations

import numpy as np
import timm
import torch
import torch.nn.functional as F

IMAGENET_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
IMAGENET_STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)


def gem_pool(x: torch.Tensor, p: float = 3.0, eps: float = 1e-6) -> torch.Tensor:
    """Genelleştirilmiş ortalama havuzlama — görüntü getirmede ortalamadan iyi."""
    return x.clamp(min=eps).pow(p).mean(dim=1).pow(1.0 / p)


class Dinov2Embedder:
    """Görüntü yığınından L2-normalize tanımlayıcı üretir.

    mode='cls'  : sınıf jetonu
    mode='gem'  : yama jetonlarının GeM havuzlaması
    mode='both' : ikisinin birleşimi (her biri ayrı normalize edilip eklenir)
    """

    def __init__(self, model_name: str = "vit_small_patch14_dinov2.lvd142m",
                 img_size: int = 224, device: str = "cuda",
                 mode: str = "both", half: bool = True):
        self.device = device
        self.mode = mode
        self.half = half
        # 224, 14'e tam bölünmüyor -> 14'ün katına yuvarla
        self.img_size = int(round(img_size / 14) * 14)
        self.model = timm.create_model(model_name, pretrained=True, num_classes=0,
                                       img_size=self.img_size)
        self.model = self.model.eval().to(device)
        if half:
            self.model = self.model.half()
        self.mean = IMAGENET_MEAN.to(device)
        self.std = IMAGENET_STD.to(device)

    @property
    def dim(self) -> int:
        d = self.model.embed_dim
        return d * 2 if self.mode == "both" else d

    def _prep(self, imgs: np.ndarray) -> torch.Tensor:
        """imgs: (B, H, W, 3) uint8 RGB -> normalize edilmiş tensör."""
        t = torch.from_numpy(imgs).to(self.device)
        t = t.permute(0, 3, 1, 2).float() / 255.0
        t = F.interpolate(t, size=(self.img_size, self.img_size),
                          mode="bilinear", align_corners=False)
        t = (t - self.mean) / self.std
        return t.half() if self.half else t

    @torch.no_grad()
    def embed(self, imgs: np.ndarray, batch: int = 32) -> np.ndarray:
        """(B, H, W, 3) uint8 -> (B, dim) float32, L2-normalize."""
        outs = []
        for i in range(0, len(imgs), batch):
            t = self._prep(imgs[i:i + batch])
            feats = self.model.forward_features(t)      # (b, 1+n, d)
            cls = feats[:, 0]
            patches = feats[:, self.model.num_prefix_tokens:]
            parts = []
            if self.mode in ("cls", "both"):
                parts.append(F.normalize(cls.float(), dim=-1))
            if self.mode in ("gem", "both"):
                parts.append(F.normalize(gem_pool(patches.float()), dim=-1))
            v = torch.cat(parts, dim=-1)
            outs.append(F.normalize(v, dim=-1).cpu().numpy())
        return np.concatenate(outs, axis=0).astype(np.float32)
