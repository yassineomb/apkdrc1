import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from app import create_app_icon


ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build" / "windows"
DIST_DIR = BUILD_DIR / "dist"
WORK_DIR = BUILD_DIR / "work"
SPEC_DIR = BUILD_DIR / "spec"
PAYLOAD_DIR = BUILD_DIR / "payload"
RELEASE_DIR = ROOT / "release"
ASSET_PATH = ROOT / "democratic-republic-of-congo-coat-of-arms-vector-24327882.webp"
APP_ICO = BUILD_DIR / "anr.ico"


def run_pyinstaller(script, name, *, windowed, onefile=False, add_data=()):
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        name,
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(WORK_DIR / name),
        "--specpath",
        str(SPEC_DIR),
        "--icon",
        str(APP_ICO),
    ]
    command.append("--onefile" if onefile else "--onedir")
    command.append("--windowed" if windowed else "--console")
    for source, destination in add_data:
        command.extend(["--add-data", f"{source};{destination}"])
    if script.name == "app.py":
        for module in ("customtkinter", "pandas", "openpyxl", "reportlab", "PIL"):
            command.extend(["--collect-all", module])
    command.append(str(script))
    subprocess.run(command, cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--installer-only",
        action="store_true",
        help="Rebuild the final installer from already-built application packages",
    )
    arguments = parser.parse_args()
    for directory in (BUILD_DIR, DIST_DIR, WORK_DIR, SPEC_DIR, RELEASE_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    if not arguments.installer_only:
        create_app_icon().save(
            APP_ICO, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)]
        )
        run_pyinstaller(
            ROOT / "app.py",
            "ApplicationANR",
            windowed=True,
            add_data=[(str(ASSET_PATH), ".")],
        )
        run_pyinstaller(
            ROOT / "mobile_portal.py",
            "PortailAndroid",
            windowed=False,
        )
        run_pyinstaller(
            ROOT / "setup_android.py",
            "ConfigurerPortailAndroid",
            windowed=False,
        )
    elif not all(
        (DIST_DIR / name).is_dir()
        for name in ("ApplicationANR", "PortailAndroid", "ConfigurerPortailAndroid")
    ):
        raise SystemExit(
            "Les paquets applicatifs sont absents. Lancez sans --installer-only."
        )

    if PAYLOAD_DIR.exists():
        shutil.rmtree(PAYLOAD_DIR)
    PAYLOAD_DIR.mkdir(parents=True)
    for name in ("ApplicationANR", "PortailAndroid", "ConfigurerPortailAndroid"):
        shutil.copytree(DIST_DIR / name, PAYLOAD_DIR / name)
    shutil.copy2(
        ROOT / "publier_android_tailscale.bat",
        PAYLOAD_DIR / "publier_android_tailscale.bat",
    )

    run_pyinstaller(
        ROOT / "windows_installer.py",
        "SetupApplicationANR",
        windowed=True,
        onefile=True,
        add_data=[(str(PAYLOAD_DIR), "payload")],
    )
    output = RELEASE_DIR / "SetupApplicationANR.exe"
    shutil.copy2(DIST_DIR / "SetupApplicationANR.exe", output)
    print(f"\nInstallateur créé : {output}")


if __name__ == "__main__":
    main()
