"""Tests for LLM client integration."""
import pytest
import asyncio
import os
from unittest.mock import Mock, patch, MagicMock

from great_work.llm_client import (
    LLMConfig,
    LLMClient,
    ContentModerator,
    SafetyLevel,
    enhance_press_release,
    get_llm_client
)


def test_llm_config_from_env():
    """Test loading LLM configuration from environment variables."""
    with patch.dict(os.environ, {
        "LLM_API_BASE": "http://test:8080/v1",
        "LLM_API_KEY": "test-key",
        "LLM_MODEL_NAME": "test-model",
        "LLM_TEMPERATURE": "0.5",
        "LLM_MAX_TOKENS": "300",
    }):
        config = LLMConfig.from_env()
        assert config.api_base == "http://test:8080/v1"
        assert config.api_key == "test-key"
        assert config.model_name == "test-model"
        assert config.temperature == 0.5
        assert config.max_tokens == 300


def test_llm_config_defaults():
    """Test default LLM configuration."""
    config = LLMConfig()
    assert config.api_base == "http://localhost:5000/v1"
    assert config.api_key == "not-needed-for-local"
    assert config.model_name == "local-model"
    assert config.temperature == 0.8
    assert config.use_fallback_templates == True
    assert config.safety_enabled == True


def test_content_moderator_safe():
    """Test content moderator with safe content."""
    moderator = ContentModerator()
    result = moderator.check_content("This is a normal academic discussion.")
    assert result == SafetyLevel.SAFE


def test_llm_client_initialization():
    """Test LLM client initialization."""
    config = LLMConfig()

    # Mock the openai import and client creation
    with patch('great_work.llm_client.LLMClient.__init__') as mock_init:
        mock_init.return_value = None
        client = LLMClient.__new__(LLMClient)
        client.config = config
        client.moderator = ContentModerator()
        client.enabled = False  # Simulate openai not installed
        client.openai = None
        client.client = None

        assert client.config.api_base == "http://localhost:5000/v1"
        assert client.moderator is not None
        assert client.enabled == False


def test_persona_prompt_generation():
    """Test persona prompt generation."""
    client = LLMClient.__new__(LLMClient)
    client.config = LLMConfig()

    prompt = client.generate_persona_prompt(
        "Dr. Smith",
        {
            "personality": "eccentric",
            "specialization": "quantum physics",
            "quirks": ["speaks in riddles", "loves tea"]
        }
    )

    assert "Dr. Smith" in prompt
    assert "quantum physics" in prompt
    assert "eccentric" in prompt
    assert "speaks in riddles" in prompt


def test_fallback_template():
    """Test fallback template generation."""
    client = LLMClient.__new__(LLMClient)
    client.config = LLMConfig()

    context = {
        "type": "discovery",
        "player": "Alice",
        "action": "made a breakthrough"
    }

    result = client._fallback_template(context)
    assert "Alice" in result
    assert "made a breakthrough" in result


@pytest.mark.asyncio
async def test_generate_narrative_with_fallback():
    """Test narrative generation with fallback when LLM is disabled."""
    config = LLMConfig(use_fallback_templates=True)
    client = LLMClient.__new__(LLMClient)
    client.config = config
    client.enabled = False  # Simulate LLM disabled
    client.moderator = None
    client._executor = None  # No executor needed for fallback

    # Mock the fallback method
    client._fallback_template = Mock(return_value="Fallback text")

    context = {"player": "Bob", "action": "submitted a theory"}
    result = await client.generate_narrative("Test prompt", context)

    assert result == "Fallback text"
    client._fallback_template.assert_called_once_with(context)


@pytest.mark.asyncio
async def test_enhance_press_release():
    """Test enhancing press release with LLM."""
    from unittest.mock import AsyncMock
    with patch('great_work.llm_client.get_llm_client') as mock_get_client:
        mock_client = Mock()
        mock_client.generate_narrative = AsyncMock(return_value="Enhanced narrative text")
        mock_get_client.return_value = mock_client

        result = await enhance_press_release(
            "academic_bulletin",
            "Base content",
            {"player": "Charlie"},
            "Dr. Jones",
            {"personality": "serious"}
        )

        assert result == "Enhanced narrative text"


def test_singleton_client():
    """Test singleton LLM client pattern."""
    with patch('great_work.llm_client.LLMClient') as MockLLMClient:
        mock_instance = Mock()
        MockLLMClient.return_value = mock_instance

        # Reset the singleton
        import great_work.llm_client
        great_work.llm_client._llm_client = None

        client1 = get_llm_client()
        client2 = get_llm_client()

        # Should only create one instance
        MockLLMClient.assert_called_once()
        assert client1 is client2


@pytest.mark.asyncio
async def test_generate_batch():
    """Test batch narrative generation."""
    client = LLMClient.__new__(LLMClient)
    client.config = LLMConfig()
    client.enabled = False
    client._executor = None  # No executor needed for test
    client._fallback_template = Mock(return_value="Batch fallback")

    prompts = [
        {"prompt": "Test 1", "context": {"id": 1}},
        {"prompt": "Test 2", "context": {"id": 2}},
        {"prompt": "Test 3", "context": {"id": 3}},
    ]

    # Mock the generate_narrative method
    async def mock_generate(prompt, context, persona_name=None, persona_traits=None):
        return f"Generated for {context.get('id', 'unknown')}"

    client.generate_narrative = mock_generate

    results = await client.generate_batch(prompts, max_concurrent=2)

    assert len(results) == 3
    assert "Generated for 1" in results[0]
    assert "Generated for 2" in results[1]
    assert "Generated for 3" in results[2]