try:
    from importlib.metadata import version, PackageNotFoundError
    try:
        __version__ = version("puls-kernel-mgr")
    except PackageNotFoundError:
        __version__ = "1.3.0"
except ImportError:
    __version__ = "1.3.0"

__author__ = "Barın Güzeldemirci"
__license__ = "GPL-3.0"
