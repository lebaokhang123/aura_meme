"""Pinned private object reads and exclusive writes; no client-supplied paths."""
from contextlib import ExitStack
from pathlib import Path
import logging
import os
import re
import stat
from uuid import uuid4


logger = logging.getLogger(__name__)
KEY = re.compile(r"[0-9a-f]{32}\.(jpg|png|webp|gif)\Z")


def windows_handle(path, *, directory, read=False):
    """Pin directories against replacement; open read handles or exclusive writers with DELETE access."""
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                               wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    api.CreateFileW.restype = wintypes.HANDLE
    handle = api.CreateFileW(str(path), 0 if directory else 0x80000000 if read else 0x40010000,
                             3 if directory else 1, None, 3 if directory or read else 1,
                             0x02200000 if directory else 0x00200080, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    return handle


def close_handle(handle):
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle(handle)


def read_private_object(root: Path, key: str, limit: int) -> bytes:
    """Pin the entire directory chain and read only one regular, unlinked object."""
    if not root.is_absolute() or '..' in root.parts or not KEY.fullmatch(key):
        raise ValueError('Invalid private object path.')
    with ExitStack() as stack:
        root_fd = None
        for parent in reversed([root, *root.parents]):
            if os.name == 'nt':
                stack.callback(close_handle, windows_handle(parent, directory=True))
                info = parent.lstat()
                if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                    raise OSError('Private directory links are forbidden.')
            else:
                root_fd = os.open(parent if root_fd is None else parent.name,
                                  os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
                stack.callback(os.close, root_fd)
        if os.name == 'nt':
            import msvcrt
            handle = windows_handle(root / key, directory=False, read=True)
            try:
                fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
            except BaseException:
                close_handle(handle)
                raise
        else:
            fd = os.open(key, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root_fd)
        with os.fdopen(fd, 'rb') as file:
            info = os.fstat(file.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or getattr(info, 'st_file_attributes', 0) & 0x400 or not 0 < info.st_size <= limit):
                raise OSError('Private object is not a bounded regular file.')
            data = file.read(limit + 1)
            if len(data) != info.st_size:
                raise OSError('Private object changed during reading.')
            return data


class LocalObject:
    """Own the newly-created file and its pinned root until commit or compensation."""
    def __init__(self, root: Path, extension: str, payload: bytes):
        self.key = None
        self.file = None
        self.root_fd = None
        self.stack = ExitStack()
        self.root = root
        try:
            if not root.is_absolute() or ".." in root.parts:
                raise OSError("Storage root must be an absolute private path.")
            for parent in reversed([root, *root.parents]):
                try:
                    parent.lstat()
                except FileNotFoundError:
                    try:
                        parent.mkdir(mode=0o700)
                    except FileExistsError:
                        pass  # Another upload may have created this same directory.
                if os.name == "nt":
                    handle = windows_handle(parent, directory=True)
                    self.stack.callback(close_handle, handle)
                info = parent.lstat()
                if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                        or getattr(info, "st_file_attributes", 0) & 0x400):
                    raise OSError("Reparse points are not permitted in the storage path.")
            if os.name != "nt":
                self.root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                self.stack.callback(os.close, self.root_fd)
                if os.fstat(self.root_fd).st_mode & 0o077:
                    raise OSError("Storage root must be private (0700).")
            for _ in range(3):
                key = uuid4().hex + "." + extension
                if not KEY.fullmatch(key):
                    raise OSError("Invalid server object key.")
                try:
                    if os.name == "nt":
                        import msvcrt
                        handle = windows_handle(root / key, directory=False)
                        try:
                            fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
                        except BaseException:
                            close_handle(handle)
                            raise
                    else:
                        fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                     0o600, dir_fd=self.root_fd)
                    self.key = key
                    self.file = os.fdopen(fd, "wb")
                    break
                except FileExistsError:
                    continue
            if self.file is None:
                raise OSError("Object key collision retry exhausted.")
            self.file.write(payload)
            self.file.flush()
            os.fsync(self.file.fileno())
        except BaseException:
            try:
                self.discard()
            finally:
                self.close()
            raise

    def discard(self):
        if self.file is None:
            return
        try:
            if os.name == "nt":
                import ctypes
                import msvcrt
                from ctypes import wintypes
                api = ctypes.WinDLL("kernel32", use_last_error=True)
                api.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                           wintypes.LPVOID, wintypes.DWORD]
                delete = wintypes.BOOL(True)
                if not api.SetFileInformationByHandle(msvcrt.get_osfhandle(self.file.fileno()),
                                                     4, ctypes.byref(delete), ctypes.sizeof(delete)):
                    raise ctypes.WinError(ctypes.get_last_error())
            else:
                os.unlink(self.key, dir_fd=self.root_fd)
        except OSError:
            logger.error("media_cleanup_failed object_key=%s reconcile_required", self.key)
            raise

    def close(self):
        try:
            if self.file is not None:
                self.file.close()
        finally:
            self.stack.close()
