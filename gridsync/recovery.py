# -*- coding: utf-8 -*-

import json
import logging
import os
from pathlib import Path
from typing import Awaitable, Callable, Optional, cast

from atomicwrites import atomic_write
from qtpy.QtCore import QObject, QPropertyAnimation, QThread, Signal
from qtpy.QtWidgets import QFileDialog, QMessageBox, QProgressDialog
from twisted.internet.defer import Deferred, succeed
from twisted.internet.interfaces import IReactorThreads
from twisted.internet.threads import deferToThreadPool
from twisted.python.failure import Failure

from gridsync import APP_NAME
from gridsync.crypto import Crypter, encrypt
from gridsync.gui.password import PasswordDialog
from gridsync.msg import error, question
from gridsync.tahoe import Tahoe


def get_recovery_key(
    password: Optional[str], gateway: Tahoe
) -> Awaitable[bytes]:
    """
    Get the recovery material and, if a password is given, encrypt it.
    """
    from twisted.internet import reactor

    settings = gateway.get_settings(include_secrets=True)
    if gateway.use_tor:
        settings["hide-ip"] = True
    plaintext = json.dumps(settings).encode("utf-8")
    if password:
        return deferToThreadPool(
            reactor,
            # Module has no attribute "getThreadPool"
            reactor.getThreadPool(),  # type: ignore
            encrypt,
            plaintext,
            password,
        )
    return succeed(plaintext)


def export_recovery_key(
    ciphertext: bytes,
    path: Path,
) -> None:
    """
    Export a recovery key to the filesystem.

    :param plaintext: The plaintext of the recovery key.
    """
    with atomic_write(path, mode="wb", overwrite=True) as f:
        f.write(ciphertext)


class RecoveryKeyImporter(QObject):

    done = Signal(dict)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.filepath = None
        self.progress = None
        self.animation = None
        self.crypter = None
        self.crypter_thread = None

    def _on_decryption_failed(self, msg):
        logging.error("%s", msg)
        self.crypter_thread.quit()
        self.crypter_thread.wait()
        if msg == "Decryption failed. Ciphertext failed verification":
            msg = "The provided passphrase was incorrect. Please try again."
        reply = QMessageBox.critical(
            self.parent,
            "Decryption Error",
            msg,
            QMessageBox.Abort | QMessageBox.Retry,
        )
        if reply == QMessageBox.Retry:
            self._load_from_file(self.filepath)

    def _on_decryption_succeeded(self, plaintext):
        logging.debug("Decryption of %s succeeded", self.filepath)
        self.crypter_thread.quit()
        self.crypter_thread.wait()
        try:
            settings = json.loads(plaintext.decode("utf-8"))
        except (UnicodeDecodeError, json.decoder.JSONDecodeError) as e:
            error(self, type(e).__name__, str(e))
            return
        if not isinstance(settings, dict):
            raise TypeError(f"settings must be 'dict'; got '{type(settings)}'")
        self.done.emit(settings)

    def _decrypt_content(self, data, password):
        logging.debug("Trying to decrypt %s...", self.filepath)
        self.progress = QProgressDialog(
            "Trying to decrypt {}...".format(os.path.basename(self.filepath)),
            None,
            0,
            100,
        )
        self.progress.show()
        self.animation = QPropertyAnimation(self.progress, b"value")
        self.animation.setDuration(6000)  # XXX
        self.animation.setStartValue(0)
        self.animation.setEndValue(99)
        self.animation.start()
        self.crypter = Crypter(data, password.encode())
        self.crypter_thread = QThread()
        self.crypter.moveToThread(self.crypter_thread)
        self.crypter.succeeded.connect(self.animation.stop)
        self.crypter.succeeded.connect(self.progress.close)
        self.crypter.succeeded.connect(self._on_decryption_succeeded)
        self.crypter.failed.connect(self.animation.stop)
        self.crypter.failed.connect(self.progress.close)
        self.crypter.failed.connect(self._on_decryption_failed)
        self.crypter_thread.started.connect(self.crypter.decrypt)
        self.crypter_thread.start()

    def _parse_content(self, content):
        try:
            settings = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.decoder.JSONDecodeError):
            logging.debug(
                "JSON decoding failed; %s is likely encrypted", self.filepath
            )
            password, ok = PasswordDialog.get_password(
                label="Decryption passphrase (required):",
                ok_button_text="Decrypt Recovery Key...",
                help_text="This Recovery Key is protected by a passphrase. "
                "Enter the correct passphrase to decrypt it.",
                show_stats=False,
                parent=self.parent,
            )
            if ok:
                self._decrypt_content(content, password)
            return
        if not isinstance(settings, dict):
            raise TypeError(f"settings must be 'dict'; got '{type(settings)}'")
        self.done.emit(settings)

    def _load_from_file(self, path):
        logging.debug("Loading %s...", self.filepath)
        try:
            with open(path, "rb") as f:
                content = f.read()
        except IsADirectoryError as err:
            error(
                self.parent,
                "Error loading Recovery Key",
                f"{path} is a directory, and not a valid Recovery Key."
                "\n\nPlease try again, selecting a valid Recovery Key file.",
                str(err),
            )
            return
        except Exception as e:  # pylint: disable=broad-except
            error(self.parent, "Error loading Recovery Key", str(e))
            return
        if not content:
            error(
                self.parent,
                "Invalid Recovery Key",
                f"The file {path} is empty."
                "\n\nPlease try again, selecting a valid Recovery Key file.",
            )
            return
        try:
            self._parse_content(content)
        except TypeError as err:
            error(
                self.parent,
                "Error parsing Recovery Key content",
                f"The file {path} does not appear to be a valid Recovery Key."
                "\n\nPlease try again, selecting a valid Recovery Key file.",
                str(err),
            )

    def _select_file(self):
        dialog = QFileDialog(self.parent, "Select a Recovery Key")
        dialog.setDirectory(os.path.expanduser("~"))
        dialog.setFileMode(QFileDialog.ExistingFile)
        if dialog.exec_():
            selected = dialog.selectedFiles()[0]
            if question(
                self.parent,
                f'Restore from "{Path(selected).name}"?',
                "By restoring from a Recovery Key, the configuration from "
                "the original device will be applied to this device -- "
                "including access to any previously-uploaded folders. Once "
                f"this process has completed, continuing to run {APP_NAME} "
                "on the original device can, in some circumstances, lead to "
                "data-loss. As a result, you should only restore from a "
                "Recovery Key in the event that the original device is no "
                f"longer running {APP_NAME}.\n\n"
                "Are you sure you wish to continue?",
            ):
                return selected
        return None

    def do_import(self, filepath=None):
        if not filepath:
            filepath = self._select_file()
        self.filepath = filepath
        if self.filepath:
            self._load_from_file(self.filepath)
