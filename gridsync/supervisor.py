import os
from pathlib import Path

# from subprocess import SubprocessError
from typing import Callable, List, Optional

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from gridsync.system import SubprocessProtocol, kill
from gridsync.types import TwistedDeferred


class Supervisor:
    def __init__(self) -> None:
        self._args: List[str] = []
        self._pidfile: Path = Path()
        self._started_trigger = ""
        self._stdout_line_collector: Optional[Callable] = None
        self._stderr_line_collector: Optional[Callable] = None

    def stop(self) -> None:
        kill(pidfile=self._pidfile)

    @inlineCallbacks
    def _start_process(self) -> TwistedDeferred[int]:
        protocol = SubprocessProtocol(
            callback_triggers=[self._started_trigger],
            stdout_line_collector=self._stdout_line_collector,
            stderr_line_collector=self._stderr_line_collector,
        )
        transport = yield reactor.spawnProcess(  # type: ignore
            protocol, self._args[0], args=self._args, env=os.environ
        )
        if self._started_trigger:
            yield protocol.done
        Path(self._pidfile).write_text(str(transport.pid), encoding="utf-8")
        return transport.pid

    @inlineCallbacks
    def start(  # pylint: disable=too-many-arguments
        self,
        args: list[str],
        pidfile: Path,
        started_trigger: str = "",
        stdout_line_collector: Optional[Callable] = None,
        stderr_line_collector: Optional[Callable] = None,
    ) -> TwistedDeferred[int]:

        self._args = args
        self._pidfile = Path(pidfile)
        self._started_trigger = started_trigger
        self._stdout_line_collector = stdout_line_collector
        self._stderr_line_collector = stderr_line_collector

        if self._pidfile.exists():
            self.stop()
        pid = yield self._start_process()
        return pid

    def restart(self) -> None:
        pass
