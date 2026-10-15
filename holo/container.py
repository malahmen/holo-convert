"""--engine container: this engine, inside the pinned tools image.

The same rules as the bash engine's container mode: the image holds only the
tools; the engine and .fcc/ are mounted read-only from the checkout; every
folder the conversion touches is mounted at its own path; no network; the
caller's uid.
"""
import hashlib
import os
import shutil
import subprocess

from . import sh
from .state import REPO
from .ui import edie, enote

CONTAINERFILE = os.path.join(REPO, "container", "Containerfile")
LAUNCHER = os.path.join(REPO, "holo-convert.sh")


def container_image() -> str:
    if os.environ.get("HOLO_CONVERT_IMAGE"):
        return os.environ["HOLO_CONVERT_IMAGE"]
    if not os.path.isfile(CONTAINERFILE):
        edie(f"container/Containerfile not found next to the engine ({CONTAINERFILE}).")
    with open(CONTAINERFILE, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()[:12]
    return f"localhost/holo-convert-tools:{digest}"


def container_runtime(requested: str) -> str:
    rt = requested
    if not rt:
        if shutil.which("podman"):
            rt = "podman"
        elif shutil.which("docker"):
            rt = "docker"
        else:
            edie("--engine container needs podman or docker on PATH.")
    if rt not in ("podman", "docker"):
        edie(f"--runtime must be podman or docker, got '{rt}'.")
    if not shutil.which(rt):
        edie(f"{rt} not found on PATH.")
    return rt


def container_mounts(args) -> list:
    """The working folder, every argument that names an existing path (its
    folder, for a file), and the -o folder - created first so it can be mounted."""
    dirs, prev, out = [os.path.realpath(".")], "", ""
    for a in args:
        if prev in ("-o", "--output"):
            out = a
        prev = a
        if os.path.isdir(a):
            dirs.append(os.path.realpath(a))
        elif os.path.exists(a):
            dirs.append(os.path.realpath(sh.dirname(a)))
    if out:
        try:
            os.makedirs(out, exist_ok=True)
        except OSError:
            edie(f"cannot create output folder: {out}")
        dirs.append(os.path.realpath(out))
    return sorted(set(dirs))


def run_in_container(args, requested_runtime: str) -> int:
    rt = container_runtime(requested_runtime)
    image = container_image()
    setup, inner, passthrough = False, [], False
    for a in args:
        if passthrough:
            inner.append(a)
        elif a == "--":
            passthrough = True
            inner.append(a)
        elif a == "--setup":
            setup = True
        elif a == "--with-optional":
            setup = True
            enote("--with-optional: the image already holds the optional tools, except mermaid-cli.")
        else:
            inner.append(a)

    if setup:
        enote(f"building {image} with {rt} - the first build downloads TeX Live and takes several minutes...")
        if sh.run([rt, "build", "-t", image, "-f", CONTAINERFILE, os.path.dirname(CONTAINERFILE)]) != 0:
            edie("image build failed.")
        if not inner:
            enote(f"image ready: {image}")
            return 0
    if subprocess.call([rt, "image", "inspect", image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        edie(f"container image {image} is not built - run: holo-convert.sh --setup --engine container")

    run = [rt, "run", "--rm", "--network", "none", "-w", os.path.realpath("."),
           "-e", "HOME=/tmp", "-e", "HOLO_CONVERT_ENGINE=local", "--security-opt", "label=disable"]
    run += ["--userns=keep-id"] if rt == "podman" else ["--user", f"{os.getuid()}:{os.getgid()}"]
    if os.isatty(1):
        run.append("-t")
    repo_rw = False
    for d in container_mounts(inner):
        if d == "/":
            edie("refusing to mount / into the container - run from, and convert files in, a folder.")
        if d == REPO:
            repo_rw = True
        run += ["-v", f"{d}:{d}"]
    if not repo_rw:
        run += ["-v", f"{REPO}:{REPO}:ro"]
    return sh.run(run + [image, "bash", LAUNCHER, *inner])
