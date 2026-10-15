"""--setup: install the engine's dependencies with whatever this host can use."""
import os
import subprocess
import platform

from . import fonts, sh
from .state import S
from .ui import edie, enote, warn


def host_immutable() -> bool:
    """The ostree marker, else a read-only /usr - NOT `[[ -w /usr ]]`, which is
    false for any unprivileged user on every Linux. HC_OSTREE_MARKER is a test
    seam."""
    if os.path.exists(os.environ.get("HC_OSTREE_MARKER") or "/run/ostree-booted"):
        return True
    if not sh.which("findmnt"):
        return False
    opts = sh.capture(["findmnt", "-no", "OPTIONS", "--target", "/usr"], stderr=subprocess.DEVNULL) or ""
    return "ro" in opts.split(",")


def pkg_manager():
    """(name, usable?). Asks "can this host install at all?" before "is dnf on
    PATH?": on an ostree desktop dnf exists and cannot install."""
    system = platform.system()
    if system == "Darwin":
        return ("brew", True) if sh.which("brew") else ("none-darwin", False)
    if system != "Linux":
        return ("unsupported-os", False)
    if host_immutable():
        if sh.which("brew"):
            return ("brew", True)
        if sh.which("rpm-ostree"):
            return ("rpm-ostree", True)
        return ("none-immutable", False)
    for name, binary in (("apt", "apt-get"), ("dnf", "dnf"), ("brew", "brew")):
        if sh.which(binary):
            return (name, True)
    return ("none", False)


def install_pkg(binary, brew_pkg, apt_pkg, dnf_pkg, cask=""):
    if sh.which(binary):
        enote(f"{binary}: already present.")
        return
    mgr, _ok = pkg_manager()
    enote(f"installing {binary} via {mgr}…")
    if mgr == "brew":
        sh.run(["brew", "install", "--cask", brew_pkg] if cask == "cask" else ["brew", "install", brew_pkg])
    elif mgr == "apt":
        if sh.run(["sudo", "apt-get", "update", "-qq"]) == 0:
            sh.run(["sudo", "apt-get", "install", "-y", apt_pkg])
    elif mgr == "dnf":
        sh.run(["sudo", "dnf", "install", "-y", dnf_pkg])
    elif mgr == "rpm-ostree":
        warn(f"{binary} will be layered onto the host image with rpm-ostree.")
        if sh.run(["sudo", "rpm-ostree", "install", "--apply-live", "--idempotent", dnf_pkg]) != 0 and \
                sh.run(["sudo", "rpm-ostree", "install", "--idempotent", dnf_pkg]) != 0:
            warn("rpm-ostree install failed; a reboot may be needed for a layered package to appear.")
    elif mgr == "none-immutable":
        edie(f"this host's /usr is read-only — an ostree image (Fedora Silverblue/Kinoite, Bazzite) — and neither brew nor rpm-ostree is available to install {binary}. Either install Homebrew (https://brew.sh; writable prefix, no reboot) or run holo-convert inside a distrobox/toolbox container.")
    elif mgr == "none-darwin":
        edie(f"Homebrew is required to install {binary} — see https://brew.sh")
    elif mgr == "unsupported-os":
        edie(f"unsupported OS for --setup: {platform.system()}")
    else:
        edie(f"no supported package manager (apt, dnf or brew) found to install {binary}.")
    if sh.which(binary):
        enote(f"{binary}: ready.")
    else:
        warn(f"{binary}: install may have failed — check the output above.")


def _dejavu_present() -> bool:
    home = os.environ.get("HOME", "")
    if os.path.isfile(f"{home}/Library/Fonts/DejaVuSansMono.ttf") or os.path.isfile("/Library/Fonts/DejaVuSansMono.ttf"):
        return True
    return sh.which("fc-list") and fonts.font_installed("DejaVu Sans Mono")


def install_dejavu():
    if _dejavu_present():
        enote("DejaVu Sans Mono: already present.")
        return
    enote("installing DejaVu fonts…")
    system = platform.system()
    if system == "Darwin":
        if not sh.which("brew"):
            warn("Homebrew is required to install fonts — see https://brew.sh")
            return
        if sh.run(["brew", "install", "--cask", "font-dejavu"]) != 0:
            warn("font-dejavu install failed.")
    elif system == "Linux":
        mgr, _ok = pkg_manager()
        cmds = {"brew": (["brew", "install", "--cask", "font-dejavu"], "font-dejavu install failed."),
                "apt": (["sudo", "apt-get", "install", "-y", "fonts-dejavu"], "fonts-dejavu install failed."),
                "dnf": (["sudo", "dnf", "install", "-y", "dejavu-sans-mono-fonts"], "dejavu fonts install failed."),
                "rpm-ostree": (["sudo", "rpm-ostree", "install", "--apply-live", "--idempotent",
                                "dejavu-sans-mono-fonts"], "dejavu fonts install failed.")}
        if mgr not in cmds:
            warn("no usable package manager found to install DejaVu fonts; code falls back to Courier New.")
            return
        cmd, msg = cmds[mgr]
        if sh.run(cmd) != 0:
            warn(msg)
        sh.run(["fc-cache", "-f"], stderr=subprocess.DEVNULL)
    else:
        warn(f"unsupported OS for font install: {system}")
    fonts.reset_fc()     # fonts just changed: the cached list is stale
    if _dejavu_present():
        enote("DejaVu Sans Mono: ready.")
    else:
        warn("DejaVu Sans Mono still not detected — check the output above.")


def install_mermaid():
    if sh.which("mmdc"):
        enote("mmdc: already present.")
        return
    if not sh.which("npm"):
        warn("npm not found — skipping mermaid-cli (install Node.js, then: npm i -g @mermaid-js/mermaid-cli).")
        return
    enote("installing mermaid-cli (npm -g @mermaid-js/mermaid-cli)…")
    if sh.run(["npm", "install", "-g", "@mermaid-js/mermaid-cli"]) != 0:
        warn("mermaid-cli install failed.")
    if sh.which("mmdc"):
        enote("mmdc: ready.")
    else:
        warn("mmdc still missing after install.")


def setup_deps():
    """pandoc always; LaTeX for PDF and python3 for DOCX, scoped by --to; the
    optional tools only with --with-optional (rsvg also with --raster-svg)."""
    enote("Setting up holo-convert dependencies…")
    install_pkg("pandoc", "pandoc", "pandoc", "pandoc")
    want_pdf = want_docx = False
    if S.output_format == "pdf":
        want_pdf = True
    elif S.output_format == "docx":
        want_docx = True
    elif S.output_format == "md":
        pass
    else:
        want_pdf = want_docx = True
    if want_pdf and not sh.which("xelatex"):
        warn("Installing a LaTeX engine (TeX Live / MacTeX) — this download is large.")
        install_pkg("xelatex", "mactex-no-gui", "texlive-xetex", "texlive-xetex", "cask")
    if want_docx:
        install_pkg("python3", "python", "python3", "python3")
    if S.with_optional:
        enote("Installing optional tools (--with-optional)…")
        install_pkg("rsvg-convert", "librsvg", "librsvg2-bin", "librsvg2-tools")
        install_pkg("magick", "imagemagick", "imagemagick", "ImageMagick")
        install_pkg("fc-list", "fontconfig", "fontconfig", "fontconfig")
        install_dejavu()
        install_mermaid()
    elif S.raster_svg:
        install_pkg("rsvg-convert", "librsvg", "librsvg2-bin", "librsvg2-tools")
    enote("Setup complete.")
