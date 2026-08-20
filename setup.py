#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"
JFC_DIR = PROJECT_ROOT / "jfc-pjproject"
BUILD_STATE_FILE = PROJECT_ROOT / ".jio-fiber-sip-build.json"

JFC_REPOSITORY = "https://github.com/JFC-Group/JFC-pjproject.git"
JFC_BRANCH = "v2.15.1"

PYTHON_PACKAGES = [
    "setuptools>=84.0.0",
    "requests>=2.32.0",
    "urllib3>=2.5.0",
]

SYSTEM_PACKAGES = {
    "build-essential": [
        "gcc",
        "g++",
        "make",
    ],
    "swig": [
        "swig",
    ],
    "libasound2-dev": [],
    "patchelf": ["patchelf"],
}


def print_step(message: str) -> None:
    print(f"\n==> {message}")


def run_command(command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print(f"$ {' '.join(command)}")
    subprocess.run(command, cwd=cwd, env=env, check=True)


def run_command_capture(command: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def require_linux() -> None:
    if platform.system() != "Linux":
        raise RuntimeError("Jio Fiber SIP setup currently supports Linux only.")


def ensure_virtual_environment() -> Path:
    print_step("Checking Python virtual environment")

    venv_python = VENV_DIR / "bin" / "python"

    if not venv_python.exists():
        print("Creating .venv...")
        run_command([sys.executable, "-m", "venv", str(VENV_DIR)])

    return venv_python


def ensure_python_packages(venv_python: Path) -> None:
    print_step("Installing Python dependencies")

    run_command([
        str(venv_python),
        "-m",
        "pip",
        "install",
        "--upgrade",
        "pip",
    ])

    run_command([
        str(venv_python),
        "-m",
        "pip",
        "install",
        *PYTHON_PACKAGES,
    ])


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def ensure_system_dependencies() -> None:
    print_step("Checking system dependencies")

    missing_packages = []

    for package, commands in SYSTEM_PACKAGES.items():
        if commands and all(command_exists(command) for command in commands):
            continue

        if package == "libasound2-dev" and Path("/usr/include/alsa/asoundlib.h").exists():
            continue

        missing_packages.append(package)

    if not missing_packages:
        print("All required system dependencies are already installed.")
        return

    if shutil.which("apt-get") is None:
        raise RuntimeError(
            "Required system dependencies are missing and apt-get is unavailable."
        )

    print("The following system packages are required:")
    for package in missing_packages:
        print(f"  - {package}")

    answer = input("\nInstall these packages using sudo apt? [Y/n]: ").strip().lower()

    if answer not in ("", "y", "yes"):
        raise RuntimeError("System dependency installation was declined.")

    run_command(["sudo", "apt-get", "update"])
    run_command(["sudo", "apt-get", "install", "-y", *missing_packages])


def ensure_jfc_source() -> None:
    print_step("Checking JFC PJSIP source")

    if JFC_DIR.exists() and (JFC_DIR / ".git").exists():
        current_revision = run_command_capture(
            ["git", "rev-parse", "HEAD"],
            cwd=JFC_DIR,
        )

        expected_revision = run_command_capture(
            ["git", "ls-remote", JFC_REPOSITORY, f"refs/heads/{JFC_BRANCH}"],
        ).split()[0]

        if current_revision == expected_revision:
            print(f"JFC PJSIP {JFC_BRANCH} is already available.")
            return

        print("Existing JFC PJSIP checkout does not match the required revision.")
        print("It will be replaced by the pinned version.")

        shutil.rmtree(JFC_DIR)

    if JFC_DIR.exists():
        raise RuntimeError(
            f"{JFC_DIR} exists but is not a Git repository. "
            "Please move it away before setup can continue."
        )

    run_command([
        "git",
        "clone",
        "--branch",
        JFC_BRANCH,
        "--depth",
        "1",
        JFC_REPOSITORY,
        str(JFC_DIR),
    ])


def get_jfc_revision() -> str:
    return run_command_capture(
        ["git", "rev-parse", "HEAD"],
        cwd=JFC_DIR,
    )


def get_python_version(venv_python: Path) -> str:
    return run_command_capture(
        [str(venv_python), "-c", "import platform; print(platform.python_version())"]
    )


def get_swig_version() -> str:
    output = run_command_capture(["swig", "-version"])

    for line in output.splitlines():
        if line.startswith("SWIG Version"):
            return line.strip()

    return output.splitlines()[0].strip()


def get_asound_header_state() -> str:
    header = Path("/usr/include/alsa/asoundlib.h")

    if not header.exists():
        return "missing"

    stat = header.stat()

    return f"{stat.st_mtime_ns}:{stat.st_size}"


def get_build_state(venv_python: Path) -> dict[str, str]:
    return {
        "jfc_revision": get_jfc_revision(),
        "jfc_branch": JFC_BRANCH,
        "python_version": get_python_version(venv_python),
        "swig_version": get_swig_version(),
        "alsa_header": get_asound_header_state(),
        "audio_backend": "alsa",
        "shared_libraries": "true",
    }


def load_build_state() -> dict[str, str] | None:
    if not BUILD_STATE_FILE.exists():
        return None

    try:
        with BUILD_STATE_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return None


def save_build_state(state: dict[str, str]) -> None:
    temporary_file = BUILD_STATE_FILE.with_suffix(".tmp")

    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(state, file, indent=2, sort_keys=True)
        file.write("\n")

    temporary_file.replace(BUILD_STATE_FILE)


def native_build_exists() -> bool:
    required_files = [
        JFC_DIR / "pjlib" / "lib" / "libpj.so.2",
        JFC_DIR / "pjlib-util" / "lib" / "libpjlib-util.so.2",
        JFC_DIR / "pjmedia" / "lib" / "libpjmedia.so.2",
        JFC_DIR / "pjsip" / "lib" / "libpjsip.so.2",
        JFC_DIR / "pjsip" / "lib" / "libpjsua.so.2",
        JFC_DIR / "pjsip" / "lib" / "libpjsua2.so.2",
    ]

    return all(path.exists() for path in required_files)


def native_build_needs_rebuild(
    current_state: dict[str, str],
    previous_state: dict[str, str] | None,
) -> bool:
    if not native_build_exists():
        return True

    if previous_state is None:
        return True

    return current_state != previous_state


def clean_native_build() -> None:
    print_step("Cleaning stale JFC native build")

    run_command(["make", "distclean"], cwd=JFC_DIR)


def configure_jfc_pjsip() -> None:
    print_step("Configuring JFC PJSIP")

    run_command(
        ["./configure", "--enable-shared"],
        cwd=JFC_DIR,
    )


def build_jfc_pjsip() -> None:
    print_step("Building JFC PJSIP")

    run_command(["make", "dep"], cwd=JFC_DIR)

    run_command(
        ["make", f"-j{os.cpu_count() or 1}"],
        cwd=JFC_DIR,
    )


def get_pjsua2_build_directory() -> Path:
    return JFC_DIR / "pjsip-apps" / "src" / "swig" / "python"


def build_pjsua2_python(venv_python: Path) -> Path:
    print_step("Building PJSUA2 Python binding")

    binding_dir = get_pjsua2_build_directory()

    run_command(
        [str(venv_python), "setup.py", "build"],
        cwd=binding_dir,
    )

    extension_files = list(
        (binding_dir / "build").glob(
            "lib.*/_pjsua2.cpython-*.so"
        )
    )

    if not extension_files:
        raise RuntimeError("PJSUA2 Python extension was not produced.")

    return extension_files[0]


def get_venv_site_packages(venv_python: Path) -> Path:
    return Path(
        run_command_capture([
            str(venv_python),
            "-c",
            "import site; print(site.getsitepackages()[0])",
        ])
    )


def install_pjsua2_python(venv_python: Path, extension_file: Path) -> None:
    print_step("Installing PJSUA2 Python binding")

    binding_dir = get_pjsua2_build_directory()
    source_python_file = binding_dir / "pjsua2.py"

    if not source_python_file.exists():
        raise RuntimeError("Generated pjsua2.py was not found.")

    site_packages = get_venv_site_packages(venv_python)

    shutil.copy2(source_python_file, site_packages / "pjsua2.py")
    shutil.copy2(extension_file, site_packages / extension_file.name)

    print(f"Installed PJSUA2 into {site_packages}")


def configure_jfc_runtime() -> None:
    print_step("Configuring JFC native runtime library paths")

    library_directories = [
        JFC_DIR / "pjsip" / "lib",
        JFC_DIR / "pjmedia" / "lib",
        JFC_DIR / "pjnath" / "lib",
        JFC_DIR / "pjlib-util" / "lib",
        JFC_DIR / "pjlib" / "lib",
        JFC_DIR / "third_party" / "lib",
    ]

    existing_directories = [
        directory
        for directory in library_directories
        if directory.exists()
    ]

    if not existing_directories:
        raise RuntimeError("No JFC native library directories were found.")

    for library_directory in existing_directories:
        native_libraries = list(library_directory.glob("*.so*"))

        if not native_libraries:
            continue

        runpaths = []

        for target_directory in existing_directories:
            relative_path = os.path.relpath(target_directory, library_directory)

            if relative_path == ".":
                runpaths.append("$ORIGIN")
            else:
                runpaths.append("$ORIGIN/" + relative_path)

        rpath = ":".join(dict.fromkeys(runpaths))

        for native_library in native_libraries:
            if not native_library.is_file():
                continue

            run_command([
                "patchelf",
                "--set-rpath",
                rpath,
                str(native_library),
            ])

    print("Configured RUNPATH for JFC native libraries")


def configure_pjsua2_runtime(venv_python: Path) -> None:
    print_step("Configuring PJSUA2 runtime library path")

    site_packages = get_venv_site_packages(venv_python)
    extension_files = list(site_packages.glob("_pjsua2.cpython-*.so"))

    if len(extension_files) != 1:
        raise RuntimeError("Expected exactly one installed PJSUA2 Python extension.")

    extension_file = extension_files[0]
    native_library_directories = [
        JFC_DIR / "pjsip" / "lib",
        JFC_DIR / "pjmedia" / "lib",
        JFC_DIR / "pjnath" / "lib",
        JFC_DIR / "pjlib-util" / "lib",
        JFC_DIR / "pjlib" / "lib",
        JFC_DIR / "third_party" / "lib",
    ]

    existing_directories = [
        directory
        for directory in native_library_directories
        if directory.exists()
    ]

    if not existing_directories:
        raise RuntimeError("No JFC native library directories were found.")

    runpaths = []

    for directory in existing_directories:
        relative_path = os.path.relpath(directory, site_packages)

        if relative_path == ".":
            runpaths.append("$ORIGIN")
        else:
            runpaths.append(f"$ORIGIN/{relative_path}")

    run_command([
        "patchelf",
        "--set-rpath",
        ":".join(dict.fromkeys(runpaths)),
        str(extension_file),
    ])

    print(f"Configured RUNPATH for {extension_file.name}")


def build_runtime_library_path() -> str:
    library_directories = [
        JFC_DIR / "pjsip" / "lib",
        JFC_DIR / "pjmedia" / "lib",
        JFC_DIR / "pjnath" / "lib",
        JFC_DIR / "pjlib-util" / "lib",
        JFC_DIR / "pjlib" / "lib",
        JFC_DIR / "third_party" / "lib",
    ]

    return ":".join(
        str(directory)
        for directory in library_directories
        if directory.exists()
    )


def verify_pjsua2(venv_python: Path) -> None:
    print_step("Verifying PJSUA2")

    library_path = build_runtime_library_path()

    environment = os.environ.copy()
    environment["LD_LIBRARY_PATH"] = (
        library_path
        + (":" + environment["LD_LIBRARY_PATH"] if environment.get("LD_LIBRARY_PATH") else "")
    )

    result = subprocess.run(
        [
            str(venv_python),
            "-c",
            "import pjsua2; endpoint=pjsua2.Endpoint(); print(endpoint.libVersion().full)",
        ],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    version = result.stdout.strip()

    if version != "2.15.1":
        raise RuntimeError(
            f"Unexpected PJSUA2 version: {version}"
        )

    print(f"PJSUA2 version: {version}")


def main() -> None:
    require_linux()

    print("Jio Fiber SIP setup")
    print("===================")

    venv_python = ensure_virtual_environment()

    ensure_python_packages(venv_python)
    ensure_system_dependencies()
    ensure_jfc_source()

    current_state = get_build_state(venv_python)
    previous_state = load_build_state()

    if native_build_needs_rebuild(current_state, previous_state):
        print_step("Native build requires regeneration")

        clean_native_build()
        configure_jfc_pjsip()
        build_jfc_pjsip()

        save_build_state(current_state)
    else:
        print_step("Native JFC build is already current")

    extension_file = build_pjsua2_python(venv_python)
    install_pjsua2_python(venv_python, extension_file)
    configure_jfc_runtime()
    configure_pjsua2_runtime(venv_python)
    verify_pjsua2(venv_python)

    print("\nSetup completed successfully.")
    print(f"Python environment: {VENV_DIR}")
    print(f"JFC PJSIP: {JFC_BRANCH}")
    print("PJSUA2 is ready.")


if __name__ == "__main__":
    main()
