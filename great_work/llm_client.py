"""LLM integration for narrative generation with OpenAI-compatible API."""
from __future__ import annotations

import asyncio
import logging
import os
import random
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


_RANDOM = random.Random()  # nosec B311 - pseudo-RNG acceptable for template selection


def _random_choice(seq):
    return _RANDOM.choice(seq)


def _augment_prompt_with_related(prompt: str, context: Dict[str, Any]) -> str:
    related = context.get("related_press") if isinstance(context, dict) else None
    if not related:
        return prompt
    if not isinstance(related, list):
        return prompt
    items = [str(item).strip() for item in related if str(item).strip()]
    if not items:
        return prompt
    related_section = "\n".join(f"- {item}" for item in items)
    return f"{prompt}\n\nRelated context:\n{related_section}"


class LLMGenerationError(RuntimeError):
    """Raised when the LLM cannot generate narrative content."""


class LLMNotEnabledError(LLMGenerationError):
    """Raised when the LLM client is disabled."""


class SafetyLevel(Enum):
    """Content safety levels for moderation."""
    SAFE = "safe"
    MINOR_CONCERN = "minor_concern"
    MODERATE_CONCERN = "moderate_concern"
    BLOCKED = "blocked"


@dataclass
class LLMConfig:
    """Configuration for LLM client."""
    api_base: str = "http://localhost:5000/v1"  # Default to local server
    api_key: str = "not-needed-for-local"  # Local servers often don't need keys
    model_name: str = "local-model"  # Model identifier
    temperature: float = 0.8
    max_tokens: int = 500
    timeout: int = 30
    retry_attempts: int = 3
    batch_size: int = 10  # For batch processing
    use_fallback_templates: bool = True  # Fallback to templates if LLM fails
    safety_enabled: bool = True
    mock_mode: bool = False
    retry_schedule: Optional[List[float]] = None

    @classmethod
    def from_env(cls) -> 'LLMConfig':
        """Load configuration from environment variables."""
        mock_mode = os.getenv("LLM_MODE", "").lower() == "mock"
        schedule_env = os.getenv("LLM_RETRY_SCHEDULE")
        retry_schedule: Optional[List[float]] = None
        if schedule_env:
            try:
                retry_schedule = [float(item.strip()) for item in schedule_env.split(",") if item.strip()]
            except ValueError:
                logger.warning("Invalid LLM_RETRY_SCHEDULE value: %s", schedule_env)
                retry_schedule = None

        return cls(
            api_base=os.getenv("LLM_API_BASE", "http://localhost:5000/v1"),
            api_key=os.getenv("LLM_API_KEY", "not-needed-for-local"),
            model_name=os.getenv("LLM_MODEL_NAME", "local-model"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.8")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "500")),
            timeout=int(os.getenv("LLM_TIMEOUT", "30")),
            retry_attempts=int(os.getenv("LLM_RETRY_ATTEMPTS", "3")),
            batch_size=int(os.getenv("LLM_BATCH_SIZE", "10")),
            use_fallback_templates=os.getenv("LLM_USE_FALLBACK", "true").lower() == "true",
            safety_enabled=os.getenv("LLM_SAFETY_ENABLED", "true").lower() == "true",
            mock_mode=mock_mode,
            retry_schedule=retry_schedule,
        )


class ContentModerator:
    """Simple content moderation system."""

    def __init__(self):
        self.blocked_words = [
            "kill",
            "murder",
            "terrorist",
            "suicide",
            "bomb",
            "racist",
        ]
        self.warning_phrases = [
            "hate speech",
            "slur",
            "graphic violence",
        ]

    def check_content(self, text: str) -> SafetyLevel:
        """Check content for safety issues."""
        text_lower = text.lower()

        # Check for blocked words
        for word in self.blocked_words:
            if word in text_lower:
                return SafetyLevel.BLOCKED

        # Check for warning phrases
        concern_count = sum(1 for phrase in self.warning_phrases if phrase in text_lower)
        if concern_count >= 3:
            return SafetyLevel.MODERATE_CONCERN
        elif concern_count >= 1:
            return SafetyLevel.MINOR_CONCERN

        return SafetyLevel.SAFE


class LLMClient:
    """OpenAI-compatible LLM client for narrative generation."""

    def __init__(self, config: Optional[LLMConfig] = None):
        """Initialize LLM client with configuration."""
        self.config = config or LLMConfig.from_env()
        self.moderator = ContentModerator() if self.config.safety_enabled else None
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._retry_schedule = self.config.retry_schedule or [1.0, 3.0, 10.0, 30.0, 60.0, 120.0]
        self.enabled = True

        if self.config.mock_mode:
            self.openai = None
            self.client = None
            logger.info("LLM client initialised in mock mode")
            return

        # Import openai library if available
        try:
            import openai
            self.openai = openai
            # Configure OpenAI client with custom base URL
            self.client = openai.OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base,
                timeout=self.config.timeout
            )
            logger.info(f"LLM client initialized with base URL: {self.config.api_base}")
        except ImportError:
            logger.warning("OpenAI library not installed. LLM features will be disabled.")
            self.openai = None
            self.client = None
            self.enabled = False

    def generate_persona_prompt(self, scholar_name: str, traits: Dict[str, Any]) -> str:
        """Generate a prompt to establish scholar persona voice."""
        personality = traits.get("personality", "scholarly")
        specialization = traits.get("specialization", "general research")
        quirks = traits.get("quirks", [])

        prompt = f"""You are {scholar_name}, a renowned scholar in {specialization}.
Your personality is {personality}. Your unique traits include: {', '.join(quirks) if quirks else 'meticulous attention to detail'}.
Write in first person from this scholar's perspective, maintaining their distinct voice and mannerisms.
Be concise but flavorful. Maximum 2-3 sentences."""

        return prompt

    async def generate_narrative(
        self,
        prompt: str,
        context: Dict[str, Any],
        persona_name: Optional[str] = None,
        persona_traits: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate narrative text using LLM with optional persona voice."""
        if self.config.mock_mode:
            return self._mock_generation(prompt, context, persona_name)

        if not self.enabled:
            if self.config.use_fallback_templates:
                return self._fallback_template(context)
            raise LLMNotEnabledError("LLM client is disabled")

        try:
            # Build full prompt with persona if provided
            full_prompt = prompt
            if persona_name and persona_traits:
                persona_prompt = self.generate_persona_prompt(persona_name, persona_traits)
                full_prompt = f"{persona_prompt}\n\nContext: {prompt}"

            # Add context as system message
            messages = [
                {"role": "system", "content": "You are generating narrative content for an academic research game."},
                {"role": "user", "content": full_prompt}
            ]

            # Make API call with retries
            response = await self._call_with_retry(messages)

            if response:
                generated_text = response.choices[0].message.content.strip()

                # Check content safety
                if self.moderator:
                    safety = self.moderator.check_content(generated_text)
                    if safety == SafetyLevel.BLOCKED:
                        logger.warning(f"Generated content blocked for safety: {generated_text[:50]}...")
                        if self.config.use_fallback_templates:
                            return self._fallback_template(context)
                        raise LLMGenerationError("Generated content blocked by moderator")
                    elif safety in [SafetyLevel.MINOR_CONCERN, SafetyLevel.MODERATE_CONCERN]:
                        logger.info(f"Content passed with {safety.value}: {generated_text[:50]}...")

                return generated_text
            else:
                if self.config.use_fallback_templates:
                    return self._fallback_template(context)
                raise LLMGenerationError("LLM call exhausted retries")

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            if self.config.use_fallback_templates:
                return self._fallback_template(context)
            raise LLMGenerationError(str(e))

    async def _call_with_retry(self, messages: List[Dict[str, str]]) -> Optional[Any]:
        """Make API call with retry logic."""
        attempts = max(1, self.config.retry_attempts)
        for attempt in range(attempts):
            try:
                response = await asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    lambda: self.client.chat.completions.create(
                        model=self.config.model_name,
                        messages=messages,
                        temperature=self.config.temperature,
                        max_tokens=self.config.max_tokens
                    )
                )
                return response
            except Exception as e:
                logger.warning(f"LLM API call attempt {attempt + 1} failed: {e}")
                if attempt < attempts - 1:
                    delay = self._retry_schedule[min(attempt, len(self._retry_schedule) - 1)]
                    await asyncio.sleep(delay)
                else:
                    logger.error("All retry attempts exhausted for LLM call")
                    return None
        return None

    def _fallback_template(self, context: Dict[str, Any]) -> str:
        """Generate fallback text when LLM is unavailable."""
        # Extract key information from context
        player = context.get("player", "Unknown")
        action = context.get("action", "performed an action")

        templates = [
            f"{player} {action} in pursuit of academic excellence.",
            f"The scholarly community observes as {player} {action}.",
            f"Breaking: {player} {action}. The implications remain to be seen.",
            f"In today's developments, {player} {action}.",
        ]

        return _random_choice(templates)

    def _mock_generation(self, prompt: str, context: Dict[str, Any], persona_name: Optional[str]) -> str:
        """Return deterministic text in mock mode."""
        speaker = persona_name or context.get("player", "Narrator")
        summary = context.get("summary") or context.get("action") or context.get("type", "event")
        return f"[MOCK] {speaker}: {summary or prompt}"

    def generate_narrative_sync(
        self,
        prompt: str,
        context: Dict[str, Any],
        persona_name: Optional[str] = None,
        persona_traits: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Blocking helper for synchronous callers."""
        coro = self.generate_narrative(
            prompt=prompt,
            context=context,
            persona_name=persona_name,
            persona_traits=persona_traits,
        )
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        result_container: Dict[str, Any] = {}

        def runner() -> None:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                result_container["value"] = new_loop.run_until_complete(coro)
            finally:
                new_loop.close()

        thread = threading.Thread(target=runner)
        thread.start()
        thread.join()
        if "value" not in result_container:
            raise LLMGenerationError("Synchronous narrative generation failed")
        return result_container["value"]

    async def generate_batch(
        self,
        prompts: List[Dict[str, Any]],
        max_concurrent: int = 5
    ) -> List[str]:
        """Generate multiple narratives in batch with concurrency control."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def generate_with_limit(prompt_data):
            async with semaphore:
                return await self.generate_narrative(
                    prompt_data["prompt"],
                    prompt_data.get("context", {}),
                    prompt_data.get("persona_name"),
                    prompt_data.get("persona_traits")
                )

        tasks = [generate_with_limit(p) for p in prompts]
        return await asyncio.gather(*tasks)

    def close(self):
        """Clean up resources."""
        self._executor.shutdown(wait=True)
        # No background loop to tear down


# Singleton instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create singleton LLM client instance."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


async def enhance_press_release(
    press_type: str,
    base_content: str,
    context: Dict[str, Any],
    scholar_name: Optional[str] = None,
    scholar_traits: Optional[Dict[str, Any]] = None
) -> str:
    """Enhance a press release with LLM-generated narrative."""
    client = get_llm_client()

    # Create appropriate prompt based on press type
    prompts = {
        "academic_bulletin": f"Write an academic announcement: {base_content}",
        "research_manifesto": f"Write a bold research manifesto: {base_content}",
        "discovery_report": f"Write an exciting discovery report: {base_content}",
        "retraction_notice": f"Write a humble retraction notice: {base_content}",
        "academic_gossip": f"Write intriguing academic gossip: {base_content}",
        "recruitment_report": f"Write a recruitment update: {base_content}",
        "defection_notice": f"Write a dramatic defection announcement: {base_content}",
        "mentorship_announcement": f"Write a mentorship announcement: {base_content}",
        "conference_report": f"Write a conference debate summary: {base_content}",
        "symposium_announcement": f"Write a symposium topic announcement: {base_content}",
    }

    prompt = prompts.get(press_type, f"Write about: {base_content}")
    prompt = _augment_prompt_with_related(prompt, context)

    enhanced = await client.generate_narrative(
        prompt=prompt,
        context=context,
        persona_name=scholar_name,
        persona_traits=scholar_traits
    )

    return enhanced


def enhance_press_release_sync(
    press_type: str,
    base_content: str,
    context: Dict[str, Any],
    scholar_name: Optional[str] = None,
    scholar_traits: Optional[Dict[str, Any]] = None,
) -> str:
    """Synchronous variant backed by the client helper."""

    prompt_map = {
        "academic_bulletin": f"Write an academic announcement: {base_content}",
        "research_manifesto": f"Write a bold research manifesto: {base_content}",
        "discovery_report": f"Write an exciting discovery report: {base_content}",
        "retraction_notice": f"Write a humble retraction notice: {base_content}",
        "academic_gossip": f"Write intriguing academic gossip: {base_content}",
        "recruitment_report": f"Write a recruitment update: {base_content}",
        "defection_notice": f"Write a dramatic defection announcement: {base_content}",
        "mentorship_announcement": f"Write a mentorship announcement: {base_content}",
        "conference_report": f"Write a conference debate summary: {base_content}",
        "symposium_announcement": f"Write a symposium topic announcement: {base_content}",
    }
    prompt = prompt_map.get(press_type, f"Write about: {base_content}")
    prompt = _augment_prompt_with_related(prompt, context)

    client = get_llm_client()
    return client.generate_narrative_sync(
        prompt=prompt,
        context=context,
        persona_name=scholar_name,
        persona_traits=scholar_traits,
    )
