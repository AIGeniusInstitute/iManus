import asyncio
import pytest

from app.infrastructure.external.browser.playwright_browser import PlaywrightBrowser


class DummyPage:
    def __init__(self):
        self.closed = False
        self._closed = False

    async def close(self):
        self.closed = True

    def is_closed(self):
        return self.closed

    async def evaluate(self, script):
        return True

    async def screenshot(self):
        return b"screenshot"


class DummyContext:
    def __init__(self):
        self.closed = False

    async def new_page(self):
        return DummyPage()

    async def close(self):
        self.closed = True


class DummyBrowser:
    def __init__(self):
        self.contexts = []

    async def new_context(self):
        ctx = DummyContext()
        self.contexts.append(ctx)
        return ctx


class DummyChromium:
    def __init__(self, browser):
        self._browser = browser

    async def connect_over_cdp(self, cdp_url):
        return self._browser


class DummyPlaywright:
    def __init__(self, browser):
        self.chromium = DummyChromium(browser)

    async def start(self):
        return self


@pytest.mark.asyncio
async def test_playwright_browser_isolated_context(monkeypatch):
    dummy_browser = DummyBrowser()
    dummy_playwright = DummyPlaywright(dummy_browser)

    # Patch async_playwright to return our dummy
    monkeypatch.setattr('app.infrastructure.external.browser.playwright_browser.async_playwright', lambda: dummy_playwright)

    pw = PlaywrightBrowser(cdp_url="http://localhost:9222")

    # Initialize should create a context and a page
    ok = await pw.initialize()
    assert ok is True
    assert pw.context is not None
    assert pw.page is not None

    # Ensure _ensure_page returns the same page instance
    page = await pw._ensure_page()
    assert page is pw.page

    # Take screenshot (dummy implementation) via page.screenshot
    data = await pw.page.screenshot()
    assert data == b"screenshot"

    # Cleanup should close context and page
    await pw.cleanup()
    assert pw.context is None
    assert pw.page is None

    # Re-initialize after cleanup should work (creates new context/page)
    ok2 = await pw.initialize()
    assert ok2 is True
    assert pw.context is not None
    assert pw.page is not None

    await pw.cleanup()