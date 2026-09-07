"""Create the Hugging Face Space if it does not exist, and push this folder to it.

Live at https://huggingface.co/spaces/MANOROMAN/GeoAnchor. It is a *static*
Space -- Hugging Face bills Gradio Spaces even on free CPU, and this page never
needed a running process, so it ships as index.html plus one JSON.

The upload refuses to run if the assets are missing: a Space that starts and
then throws on its first read is worse than not deploying.

    python space/hazirla.py     # build the assets from results/ and night/
    python space/dagit.py --kuru-calisma   # show what would be uploaded
    python space/dagit.py                  # create it public
    python space/dagit.py --gizli          # private -- needs a PRO account

A private Gradio Space requires PRO; on a free account the review step is
running it locally (`python space/app.py`) before making it public.

A Space is a web page under your account. Nothing uploaded is generated here
that is not already in the public repository -- the precomputed result arrays,
the demo clip and the night evidence figure -- but the page itself is yours to
publish, so --gizli exists and is the sensible first run.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
REPO_ID = "MANOROMAN/GeoAnchor"

# Everything the Space needs at run time. assets/ is generated, never committed.
REQUIRED = ["index.html", "README.md"]
REQUIRED_ASSETS = ["data.json", "demo.mp4"]


def check() -> list[Path]:
    """The exact file list to upload, or exit explaining what is missing."""
    missing = [n for n in REQUIRED if not (HERE / n).exists()]
    if missing:
        sys.exit(f"space/ eksik: {', '.join(missing)}")
    if not ASSETS.is_dir():
        sys.exit("space/assets/ yok -- once: python space/hazirla.py")
    missing = [n for n in REQUIRED_ASSETS if not (ASSETS / n).exists()]
    if missing:
        sys.exit(f"space/assets/ eksik: {', '.join(missing)}\n"
                 "once: python space/hazirla.py")

    files = [HERE / n for n in REQUIRED]
    files += sorted(p for p in ASSETS.iterdir() if p.is_file())
    return files


def izin_kontrol(info: dict) -> None:
    """Fail with the fix, not with a 403 traceback.

    The token on this machine turned out to be fine-grained and read-only, so
    create_repo died 25 lines into huggingface_hub with a stack trace that says
    nothing about what to do. Checking first costs one API call that has already
    been made.
    """
    user = info.get("name", "?")
    auth = info.get("auth", {}).get("accessToken", {}) or {}
    role = auth.get("role")
    if role in ("write", "admin"):
        return
    fg = auth.get("fineGrained") or {}
    izinler = sorted({p for s in fg.get("scoped", [])
                      for p in s.get("permissions", [])} | set(fg.get("global", [])))
    yeterli = {"repo.write", "repo.content.write"}
    if yeterli & set(izinler):
        return
    sys.exit(
        f"\nJeton '{auth.get('displayName', '?')}' ({user}) yazma yetkisine sahip degil.\n"
        f"  su an: {', '.join(izinler) or 'yetki yok'}\n"
        f"  gereken: repo.write (ya da 'write' rollu klasik jeton)\n\n"
        "huggingface.co/settings/tokens adresinden yazma yetkili bir jeton olustur,\n"
        "sonra: hf auth login")


def main() -> int:
    files = check()
    total = sum(f.stat().st_size for f in files) / 1e6
    print(f"{len(files)} dosya, {total:.1f} MB\n")
    for f in files:
        print(f"  {f.relative_to(HERE)}  ({f.stat().st_size / 1e6:.2f} MB)")

    if "--kuru-calisma" in sys.argv:
        print(f"\nkuru calisma: {REPO_ID} icin hicbir sey gonderilmedi")
        return 0

    from huggingface_hub import HfApi, get_token, whoami
    token = get_token()
    if not token:
        sys.exit("\nHugging Face oturumu yok -- once: hf auth login")
    izin_kontrol(whoami(token))

    gizli = "--gizli" in sys.argv
    api = HfApi()
    # Private first is the safe default when someone will look before the world
    # does: the Space builds and runs exactly the same, and making it public
    # later is one switch in the Space settings.
    try:
        api.create_repo(REPO_ID, repo_type="space", space_sdk="static",
                        private=gizli, exist_ok=True)
    except Exception as ex:
        # A private Gradio Space needs a PRO subscription; on a free account
        # only public Gradio Spaces (or private *static* ones) are allowed.
        # The API reports this as a bare 402 and the traceback says nothing
        # useful, so the alternative is spelled out here instead.
        if "402" in str(ex):
            sys.exit(
                "\nGizli Gradio Space PRO abonelik istiyor (402).\n"
                "Ucretsiz hesapta Gradio Space'leri yalnizca herkese acik olabiliyor.\n\n"
                "Iki secenek:\n"
                "  1. Once yerelde bak, sonra herkese acik dagit:\n"
                "       python space/app.py         # http://127.0.0.1:7860\n"
                "       python space/dagit.py       # --gizli olmadan\n"
                "  2. Space'i sil: huggingface.co/spaces/" + REPO_ID + " -> Settings\n"
                "     Silmek geri donusu olan bir islem, tek tikla.")
        raise
    api.upload_folder(
        repo_id=REPO_ID, repo_type="space", folder_path=str(HERE),
        # __pycache__ and the generator scripts have no business on the Space.
        # The Gradio app, the generators and the caches stay behind: a static
        # Space serves index.html and assets/, nothing else is read.
        ignore_patterns=["__pycache__/*", "hazirla.py", "dagit.py", "app.py",
                         "requirements.txt", "*.pyc"],
    )
    url = f"https://huggingface.co/spaces/{REPO_ID}"
    print(f"\n-> {url}  ({'GIZLI' if gizli else 'herkese acik'})")
    if gizli:
        print("Space ayarlarindan herkese acik yaptiktan sonra baglantiyi")
        print("PAYLASIM-EN.md'deki <SPACE_LINK> yerlerine koy.")
    else:
        print("Bu baglantiyi PAYLASIM-EN.md'deki <SPACE_LINK> yerlerine koy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
