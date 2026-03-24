# tests/test_agent.py
import json
from unittest.mock import MagicMock, patch
from src.agent import run_agent, TOOLS, AGENT_SYSTEM_PROMPT
from src.config import Config


def make_test_config(tmp_path):
    return Config(
        reddit_subreddits=["MachineLearning"],
        reddit_user_agent="test/1.0",
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        gmail_address="test@gmail.com",
        gmail_password="password",
        recipients=["recipient@test.com"],
        schedule_cron="0 8 * * *",
        timezone="Asia/Shanghai",
        llm_api_key="sk-test",
        llm_base_url="https://open.bigmodel.cn/api/anthropic",
        llm_model="glm-4.5-flash",
        max_tokens=8192,
        exa_api_key="exa-test",
        exa_default_num_results=10,
        max_tool_calls=15,
        max_runtime_seconds=300,
        db_path=str(tmp_path / "test.db"),
        cleanup_days=3,
    )


def test_tools_defined_correctly():
    assert len(TOOLS) == 4
    names = {t["name"] for t in TOOLS}
    assert names == {"exa_search_news", "exa_search_tweets", "exa_get_contents", "fetch_reddit_rss"}


def test_agent_system_prompt_contains_key_instructions():
    assert "今日概述" in AGENT_SYSTEM_PROMPT
    assert "模型层" in AGENT_SYSTEM_PROMPT
    assert "10 条" in AGENT_SYSTEM_PROMPT
    assert "容错" in AGENT_SYSTEM_PROMPT


@patch("src.agent.Exa")
@patch("src.agent.anthropic.Anthropic")
def test_agent_single_turn_no_tools(mock_anthropic_cls, mock_exa_cls, tmp_path):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = "# 今日概述\n\n今天没有重大新闻。"

    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_response.content = [mock_text_block]
    mock_client.messages.create.return_value = mock_response

    config = make_test_config(tmp_path)
    result = run_agent(config)
    assert "今日概述" in result


@patch("src.agent.execute_tool")
@patch("src.agent.Exa")
@patch("src.agent.anthropic.Anthropic")
def test_agent_with_tool_call(mock_anthropic_cls, mock_exa_cls, mock_execute, tmp_path):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    # First response: tool_use
    mock_tool_block = MagicMock()
    mock_tool_block.type = "tool_use"
    mock_tool_block.id = "tool_1"
    mock_tool_block.name = "exa_search_news"
    mock_tool_block.input = {"query": "AI news"}

    mock_response_1 = MagicMock()
    mock_response_1.stop_reason = "tool_use"
    mock_response_1.content = [mock_tool_block]

    # Second response: end_turn with digest
    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = "# 今日概述\n\nAI 领域有突破。"

    mock_response_2 = MagicMock()
    mock_response_2.stop_reason = "end_turn"
    mock_response_2.content = [mock_text_block]

    mock_client.messages.create.side_effect = [mock_response_1, mock_response_2]
    mock_execute.return_value = json.dumps([{"title": "News", "url": "https://example.com"}])

    config = make_test_config(tmp_path)
    result = run_agent(config)
    assert "今日概述" in result
    mock_execute.assert_called_once()


@patch("src.agent.execute_tool")
@patch("src.agent.Exa")
@patch("src.agent.anthropic.Anthropic")
def test_agent_respects_max_tool_calls(mock_anthropic_cls, mock_exa_cls, mock_execute, tmp_path):
    config = make_test_config(tmp_path)
    # Use a very small limit
    object.__setattr__(config, 'max_tool_calls', 2)

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    mock_tool_block = MagicMock()
    mock_tool_block.type = "tool_use"
    mock_tool_block.id = "tool_x"
    mock_tool_block.name = "exa_search_news"
    mock_tool_block.input = {"query": "AI"}

    mock_tool_response = MagicMock()
    mock_tool_response.stop_reason = "tool_use"
    mock_tool_response.content = [mock_tool_block]

    mock_text = MagicMock()
    mock_text.type = "text"
    mock_text.text = "# 今日概述\n\n强制结束。"
    mock_end_response = MagicMock()
    mock_end_response.stop_reason = "end_turn"
    mock_end_response.content = [mock_text]

    # 2 tool calls then forced end_turn
    mock_client.messages.create.side_effect = [
        mock_tool_response, mock_tool_response, mock_end_response
    ]
    mock_execute.return_value = "[]"

    result = run_agent(config)
    assert result  # Should produce some output
    assert mock_execute.call_count == 2
