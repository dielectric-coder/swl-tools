#!/usr/bin/env python3
"""Capture SVG screenshots of the SWL dashboard and checksked output."""

import sys
import os
import asyncio
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

SCREENSHOT_DIR = os.path.dirname(os.path.abspath(__file__))


def capture_checksked():
    """Capture checksked output as SVG via Rich Console recording."""
    from rich.console import Console

    result = subprocess.run(
        [sys.executable, "-m", "eibi_swl.checksked", "6070"],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": os.path.join(SCREENSHOT_DIR, "..", "src")},
    )
    output = result.stdout or result.stderr or "(no output)"

    console = Console(record=True, width=120, force_terminal=True)
    for line in output.splitlines():
        console.print(line)

    svg = console.export_svg(title="checksked 6070")
    path = os.path.join(SCREENSHOT_DIR, "checksked.svg")
    with open(path, "w") as f:
        f.write(svg)
    print(f"Saved {path}")


def capture_dashboard():
    """Capture SWL dashboard with a frequency search as SVG."""
    from textual.widgets import Input, DataTable
    from eibi_swl.swl import SWLApp

    class ScreenshotApp(SWLApp):
        async def on_mount(self):
            super().on_mount()
            await asyncio.sleep(0.3)

            # Take empty dashboard screenshot
            self.save_screenshot(
                os.path.join(SCREENSHOT_DIR, "swl-dashboard.svg")
            )

            # Set search value and trigger search directly
            freq_input = self.query_one("#freq-input", Input)
            freq_input.value = "6070"
            self._do_search()
            await asyncio.sleep(0.3)

            self.save_screenshot(
                os.path.join(SCREENSHOT_DIR, "swl-search.svg")
            )

            # Open detail modal on first row
            table = self.query_one("#schedule-table", DataTable)
            if table.row_count > 0:
                table.focus()
                await asyncio.sleep(0.1)
                table.action_select_cursor()
                await asyncio.sleep(0.3)
                self.save_screenshot(
                    os.path.join(SCREENSHOT_DIR, "swl-detail.svg")
                )

            self.exit()

    app = ScreenshotApp()
    app.run(headless=True, size=(120, 36))
    print(f"Dashboard screenshots saved to {SCREENSHOT_DIR}")


if __name__ == "__main__":
    capture_checksked()
    capture_dashboard()
