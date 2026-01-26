import pytest
import asyncio

from app.domain.services.agent_task_runner import AgentTaskRunner


class Dummy:
    pass


class DummyBrowser:
    def __init__(self):
        self.cleaned = False

    async def cleanup(self):
        self.cleaned = True


class DummySandbox:
    def __init__(self):
        self.destroyed = False

    async def destroy(self):
        self.destroyed = True


@pytest.mark.asyncio
async def test_destroy_calls_cleanup():
    # Prepare dummy dependencies
    browser = DummyBrowser()
    sandbox = DummySandbox()

    runner = AgentTaskRunner(
        session_id="s1",
        agent_id="a1",
        user_id="u1",
        llm=Dummy(),
        sandbox=sandbox,
        browser=browser,
        agent_repository=Dummy(),
        session_repository=Dummy(),
        json_parser=Dummy(),
        file_storage=Dummy(),
        mcp_repository=Dummy(),
        search_engine=None,
    )

    # Call destroy
    await runner.destroy()

    assert browser.cleaned is True
    assert sandbox.destroyed is True
