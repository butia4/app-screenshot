"""Composition root: wires config, adapters and the capture session."""

import os
import sys
import threading
from datetime import datetime

from app_screenshot.config.loader import load_config
from app_screenshot.config.settings import AppConfig, ConfigError
from app_screenshot.shared.layout import SessionLayout

EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_CONFIG = 2
EXIT_PLATFORM = 3


def format_banner(cfg: AppConfig, layout: SessionLayout, fmt: str) -> str:
    bar = "=" * 64
    return "\n".join(
        [
            bar,
            " app-screenshot: YOUR SCREEN IS BEING RECORDED",
            bar,
            f" output       : {layout.session_dir}",
            f" capture      : every {cfg.capture_interval:g}s ({fmt}, max width {cfg.max_width}px,"
            f" quality {cfg.quality})",
            f" archive      : every {cfg.archive_interval:g}s (zip)",
            f" size cap     : {cfg.max_archive_size // 2**20} MiB of archives",
            f" min free disk: {cfg.min_free_disk // 2**20} MiB",
            " Press Ctrl+C to stop (pending frames are archived before exit).",
            bar,
        ]
    )


def main(argv: list[str] | None = None) -> int:
    from app_screenshot.capture.platform_guard import check_platform
    from app_screenshot.shared.notifier import ConsoleNotifier

    notifier = ConsoleNotifier()
    try:
        cfg = load_config(argv)
    except ConfigError as exc:
        notifier.notify("error", f"configuration error: {exc}")
        return EXIT_CONFIG

    problem = check_platform(os.environ)
    if problem:
        notifier.notify("error", problem)
        return EXIT_PLATFORM

    try:
        return _run(cfg, notifier)
    except Exception as exc:
        notifier.notify("error", f"unexpected error: {exc!r}")
        return EXIT_UNEXPECTED


def _run(cfg: AppConfig, notifier) -> int:
    # The mss backend must exist before Pillow (or any GUI toolkit) is imported so that
    # mss sets Windows DPI awareness first.
    from app_screenshot.capture.mss_capturer import MssCapturer

    try:
        capturer = MssCapturer()
    except Exception as exc:
        notifier.notify("error", f"cannot initialise screen capture: {exc}")
        return EXIT_PLATFORM

    from app_screenshot.archiving.recovery import Recovery
    from app_screenshot.archiving.service import ArchiveService
    from app_screenshot.archiving.zip_archiver import ZipArchiver
    from app_screenshot.capture.session import CaptureSession
    from app_screenshot.capture.signals import install_stop_handlers
    from app_screenshot.encoding.blank import BlankFrameMonitor
    from app_screenshot.encoding.pillow_encoder import PillowEncoder
    from app_screenshot.retention.disk_guard import DiskGuard
    from app_screenshot.retention.enforcer import RetentionEnforcer
    from app_screenshot.shared.clock import SystemClock
    from app_screenshot.shared.fs_storage import FsStorage
    from app_screenshot.shared.layout import current_hostname

    clock, storage, archiver = SystemClock(), FsStorage(), ZipArchiver()
    layout = SessionLayout(cfg.output_root, current_hostname(), datetime.now())
    encoder = PillowEncoder(cfg.max_width, cfg.quality, notifier)
    enforcer = RetentionEnforcer(storage, notifier, layout.host_dir, cfg.max_archive_size)
    service = ArchiveService(storage, archiver, notifier, after_archive=enforcer.on_archive)

    print(format_banner(cfg, layout, encoder.fmt), flush=True)

    enforcer.begin_startup()
    try:
        Recovery(storage, archiver, service, notifier).run(layout.host_dir)
    finally:
        enforcer.end_startup()

    stop = threading.Event()
    restore = install_stop_handlers(stop, notifier)
    session = CaptureSession(
        clock=clock,
        capturer=capturer,
        encoder=encoder,
        storage=storage,
        notifier=notifier,
        guard=DiskGuard(storage, notifier, cfg.output_root, cfg.min_free_disk),
        blank=BlankFrameMonitor(notifier, clock),
        archiver=service,
        layout=layout,
        capture_interval=cfg.capture_interval,
        archive_interval=cfg.archive_interval,
        wait=stop.wait,
        failure_limit=cfg.failure_limit,
    )
    try:
        return session.run()
    finally:
        restore()
        capturer.close()


if __name__ == "__main__":
    sys.exit(main())
