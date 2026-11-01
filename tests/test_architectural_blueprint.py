"""
Tests for Architectural Blueprint Integration:
  1. Multi-Account API Key Rotator & Resilient Cloud Gateway
  2. Fast Intent Router (Jev-Style Decision Engine)
  3. Model Context Protocol (MCP) Client Substrate
  4. GUI Visual Grounding & Safe Desktop Control
  5. Voice Pipeline Substrate (Kokoro-TTS & Faster-Whisper hooks)
"""

import os
import time
import pytest
from pathlib import Path

# Core imports
from jarvis.core.api_key_rotator import (
    BaseKeyRotator,
    GeminiKeyRotator,
    OpenRouterKeyRotator,
    APIKeyRotatorManager,
    KeyHealth,
    api_key_rotator,
)
from jarvis.core.intent_router import (
    FastIntentRouter,
    IntentCategory,
    SubsystemDestination,
    intent_router,
)
from jarvis.core.mcp_client import (
    MCPClient,
    MCPServerConfig,
    JSONRPCMessage,
    mcp_client,
)
from jarvis.core.visual_grounding import (
    VisualGroundingEngine,
    VisualAction,
    RestrictedZone,
    visual_grounding,
)
from jarvis.core.voice_stream import (
    AudioStreamBuffer,
    FasterWhisperSTT,
    KokoroTTS,
    VoicePipelineCoordinator,
    voice_stream,
)
from jarvis.core.model_router import model_router


# ============================================================================
# 1. Multi-Account API Key Rotator Tests
# ============================================================================
class TestApiKeyRotator:
    def test_key_health_tracking_and_cooldown(self):
        tracker = KeyHealth("test_secret_key_12345", provider="gemini")
        assert tracker.redacted_key == "test...2345"
        assert tracker.is_available() is True

        tracker.record_success()
        assert tracker.total_requests == 1
        assert tracker.successful_requests == 1
        assert tracker.consecutive_failures == 0

        # Simulate 429 rate limit
        tracker.record_429(cooldown_seconds=10.0)
        assert tracker.rate_limit_429_count == 1
        assert tracker.is_available() is False
        assert tracker.consecutive_failures == 1

        d = tracker.to_dict()
        assert d["in_cooldown"] is True
        assert d["rate_limit_429_count"] == 1

    def test_multi_key_round_robin_rotation(self):
        rotator = BaseKeyRotator("test", keys=["key_A", "key_B", "key_C"])
        assert rotator.key_count == 3

        k1 = rotator.get_next_key()
        k2 = rotator.get_next_key()
        k3 = rotator.get_next_key()
        k4 = rotator.get_next_key()

        assert [k1, k2, k3] == ["key_A", "key_B", "key_C"]
        assert k4 == "key_A"

    def test_automatic_429_failover_and_cooldown_selection(self):
        rotator = BaseKeyRotator("test", keys=["key_A", "key_B", "key_C"])

        # Simulate key_A is rate limited
        tracker_a = rotator.get_tracker("key_A")
        tracker_a.record_429(cooldown_seconds=60.0)

        # get_next_key should skip key_A and return key_B
        next_key = rotator.get_next_key(enforce_cooldown=True)
        assert next_key == "key_B"

        # Simulate key_B also gets rate-limited
        tracker_b = rotator.get_tracker("key_B")
        tracker_b.record_429(cooldown_seconds=60.0)

        # Next key should be key_C
        next_key = rotator.get_next_key(enforce_cooldown=True)
        assert next_key == "key_C"

    def test_gemini_rotator_key_discovery(self, monkeypatch):
        monkeypatch.setenv("GEMINI_KEY_ACCOUNT_1", "gemini_mock_key_1")
        monkeypatch.setenv("GEMINI_KEY_ACCOUNT_2", "gemini_mock_key_2")
        monkeypatch.setenv("GEMINI_KEY_ACCOUNT_3", "gemini_mock_key_3")

        gemini = GeminiKeyRotator()
        assert gemini.key_count >= 3
        assert "gemini_mock_key_1" in gemini.keys
        assert "gemini_mock_key_2" in gemini.keys
        assert "gemini_mock_key_3" in gemini.keys

        metrics = gemini.get_metrics()
        assert metrics["provider"] == "gemini"
        assert len(metrics["keys"]) >= 3

    def test_openrouter_rotator_initialization(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEYS", "sk-or-key1,sk-or-key2")
        openrouter = OpenRouterKeyRotator()
        assert openrouter.key_count >= 2
        assert "sk-or-key1" in openrouter.keys

    def test_model_router_status_includes_rotator_summary(self):
        status = model_router.get_status()
        assert "tier_3_cloud" in status
        assert "key_rotator_summary" in status["tier_3_cloud"]
        summary = status["tier_3_cloud"]["key_rotator_summary"]
        assert "gemini" in summary
        assert "openrouter" in summary


# ============================================================================
# 2. Fast Intent Router Tests
# ============================================================================
class TestFastIntentRouter:
    def test_ultra_low_latency_guarantee(self):
        queries = [
            "open notepad",
            "volume up",
            "read file data/log.txt",
            "click on submit button",
            "architect a high throughput hybrid compute system",
            "who are you",
        ]
        router = FastIntentRouter()
        for q in queries:
            res = router.triage(q)
            # Must finish well within 10ms (typically <0.5ms)
            assert res.latency_ms < 10.0, f"Query '{q}' took {res.latency_ms}ms, exceeding 10ms limit!"

    def test_instant_macro_triage(self):
        router = FastIntentRouter()

        res1 = router.triage("open notepad")
        assert res1.intent_category == IntentCategory.INSTANT_MACRO
        assert res1.target_subsystem == SubsystemDestination.LOCAL_MACRO
        assert res1.entities.get("action") == "app_launch"
        assert res1.entities.get("target") == "notepad"
        assert res1.requires_confirmation is False

        res2 = router.triage("volume up")
        assert res2.intent_category == IntentCategory.INSTANT_MACRO
        assert res2.target_subsystem == SubsystemDestination.LOCAL_MACRO

        res3 = router.triage("sleep")
        assert res3.intent_category == IntentCategory.INSTANT_MACRO
        assert res3.requires_confirmation is True

        res4 = router.triage("take screenshot")
        assert res4.intent_category == IntentCategory.INSTANT_MACRO
        assert res4.suggested_action == "screenshot"

    def test_local_mcp_tool_triage(self):
        router = FastIntentRouter()

        res_fs = router.triage("read file data/powers_catalog.json")
        assert res_fs.intent_category == IntentCategory.LOCAL_TOOL
        assert res_fs.target_subsystem == SubsystemDestination.LOCAL_MCP
        assert res_fs.entities.get("mcp_server") == "filesystem"
        assert res_fs.entities.get("tool") == "read_file"

        res_git = router.triage("git status")
        assert res_git.intent_category == IntentCategory.LOCAL_TOOL
        assert res_git.entities.get("mcp_server") == "git"

        res_mem = router.triage("remember user prefers dark mode")
        assert res_mem.intent_category == IntentCategory.LOCAL_TOOL
        assert res_mem.entities.get("mcp_server") == "memory"

    def test_gui_action_triage(self):
        router = FastIntentRouter()

        res_click = router.triage("click on the login button")
        assert res_click.intent_category == IntentCategory.GUI_ACTION
        assert res_click.target_subsystem == SubsystemDestination.GUI_GROUNDING
        assert res_click.suggested_action == "click_element"

        res_type = router.triage("type 'admin123' into username field")
        assert res_type.intent_category == IntentCategory.GUI_ACTION
        assert res_type.suggested_action == "type_in_element"

    def test_cloud_reasoning_triage(self):
        router = FastIntentRouter()

        res_arch = router.triage("architect a distributed cognitive control architecture with asynchronous state machines")
        assert res_arch.intent_category == IntentCategory.CLOUD_REASONING
        assert res_arch.target_subsystem == SubsystemDestination.CLOUD_ROTATOR

    def test_voice_stream_triage(self):
        router = FastIntentRouter()

        res_voice = router.triage("[voice] turn on the desk lamp")
        assert res_voice.intent_category == IntentCategory.VOICE_COMMAND
        assert res_voice.target_subsystem == SubsystemDestination.VOICE_BUS


# ============================================================================
# 3. Model Context Protocol (MCP) Substrate Tests
# ============================================================================
class TestMCPSubstrate:
    def test_mcp_config_loading(self):
        client = MCPClient()
        assert "filesystem" in client.servers
        assert "memory" in client.servers
        assert "git" in client.servers
        assert "sequential-thinking" in client.servers

    def test_jsonrpc_message_builder(self):
        req = JSONRPCMessage.build_request("tools/call", {"name": "test_tool", "arguments": {"x": 1}}, req_id="msg_001")
        assert req["jsonrpc"] == "2.0"
        assert req["id"] == "msg_001"
        assert req["method"] == "tools/call"
        assert req["params"]["name"] == "test_tool"

        res = JSONRPCMessage.build_response("msg_001", result={"status": "ok"})
        assert res["jsonrpc"] == "2.0"
        assert res["result"]["status"] == "ok"

    def test_mcp_tool_listing(self):
        client = MCPClient()
        fs_tools = client.list_tools("filesystem")
        tool_names = [t["name"] for t in fs_tools]
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "list_directory" in tool_names

        mem_tools = client.list_tools("memory")
        mem_names = [t["name"] for t in mem_tools]
        assert "create_entities" in mem_names
        assert "search_nodes" in mem_names

        git_tools = client.list_tools("git")
        git_names = [t["name"] for t in git_tools]
        assert "git_status" in git_names

    def test_mcp_tool_execution_filesystem(self, tmp_path):
        client = MCPClient()
        # Write file
        w_res = client.call_tool("filesystem", "write_file", {"path": "test_mcp.txt", "content": "MCP Hello World"})
        assert w_res.get("isError") is False

        # Read back
        r_res = client.call_tool("filesystem", "read_file", {"path": "test_mcp.txt"})
        assert r_res.get("isError") is False
        assert "MCP Hello World" in r_res["content"][0]["text"]

    def test_mcp_tool_execution_memory_and_sequential_thinking(self):
        client = MCPClient()
        # Memory creation
        mem_res = client.call_tool("memory", "create_entities", {"entities": [{"name": "User", "role": "Architect"}]})
        assert mem_res.get("isError") is False

        search_res = client.call_tool("memory", "search_nodes", {"query": "Architect"})
        assert search_res.get("isError") is False
        assert "Architect" in search_res["content"][0]["text"]

        # Sequential thinking
        think_res = client.call_tool("sequential-thinking", "sequentialthinking", {
            "thought": "Decomposing GUI action coordinates",
            "thoughtNumber": 1,
            "totalThoughts": 3,
        })
        assert think_res.get("isError") is False
        assert "Decomposing GUI action coordinates" in think_res["content"][0]["text"]

    def test_mcp_unknown_server_raises_keyerror(self):
        client = MCPClient()
        with pytest.raises(KeyError):
            client.call_tool("unknown_nonexistent_server", "test", {})


# ============================================================================
# 4. GUI Visual Grounding & Safe Desktop Control Tests
# ============================================================================
class TestVisualGrounding:
    def test_coordinate_conversion_0_to_1000_scale(self):
        engine = VisualGroundingEngine(display_width=1920, display_height=1080)

        # Center point
        abs_x, abs_y = engine.normalized_to_absolute(500.0, 500.0)
        assert abs_x == 960
        assert abs_y == 540

        # Corners
        top_left_x, top_left_y = engine.normalized_to_absolute(0.0, 0.0)
        assert top_left_x == 0
        assert top_left_y == 0

        bot_right_x, bot_right_y = engine.normalized_to_absolute(1000.0, 1000.0)
        assert bot_right_x == 1919
        assert bot_right_y == 1079

        # Inversion
        norm_x, norm_y = engine.absolute_to_normalized(960, 540)
        assert norm_x == 500.0
        assert norm_y == 500.0

    def test_coordinate_clamping(self):
        engine = VisualGroundingEngine(display_width=1920, display_height=1080)
        # Out-of-bounds inputs clamped safely
        x, y = engine.normalized_to_absolute(-150.0, 1200.0)
        assert x == 0
        assert y == 1079

    def test_parse_uitars_output(self):
        engine = VisualGroundingEngine()
        sample_output = """
        Thought: I need to click the search input and type the query.
        Action: click(point='[450, 120]')
        Action: type(content='autonomous cognitive assistant')
        Action: hotkey(key='enter')
        """
        actions = engine.parse_uitars_output(sample_output)
        assert len(actions) == 3

        assert actions[0].action_type == "click"
        assert actions[0].norm_x == 450.0
        assert actions[0].norm_y == 120.0

        assert actions[1].action_type == "type"
        assert actions[1].target_text == "autonomous cognitive assistant"

        assert actions[2].action_type == "hotkey"
        assert actions[2].keys == "enter"

    def test_safety_guardrails_blocks_restricted_zones(self):
        engine = VisualGroundingEngine(display_width=1920, display_height=1080)

        # 1. Top right window close button zone (norm_x: 975-1000, norm_y: 0-40)
        dangerous_close_action = VisualAction(action_type="click", norm_x=990.0, norm_y=15.0)
        is_safe, violation = engine.validate_action_safety(dangerous_close_action)
        assert is_safe is False
        assert "top_right_system_close" in violation

        # 2. UAC Shield prompt zone (norm_x: 400-600, norm_y: 450-550)
        dangerous_uac_action = VisualAction(action_type="click", norm_x=500.0, norm_y=500.0)
        is_safe_uac, violation_uac = engine.validate_action_safety(dangerous_uac_action)
        assert is_safe_uac is False
        assert "uac_prompt_shield" in violation_uac

        # 3. Safe coordinate
        safe_action = VisualAction(action_type="click", norm_x=200.0, norm_y=300.0)
        is_safe_ok, violation_ok = engine.validate_action_safety(safe_action)
        assert is_safe_ok is True
        assert violation_ok is None

    def test_dry_run_action_execution(self):
        engine = VisualGroundingEngine(display_width=1920, display_height=1080)

        # Safe click dry-run
        safe_action = VisualAction(action_type="click", norm_x=300.0, norm_y=400.0)
        res = engine.execute_action(safe_action, dry_run=True)
        assert res["status"] == "success"
        assert res["executed"] is True
        assert res["abs_coords"] == (576, 432)

        # Blocked dangerous click dry-run
        dangerous_action = VisualAction(action_type="click", norm_x=995.0, norm_y=10.0)
        blocked_res = engine.execute_action(dangerous_action, dry_run=True)
        assert blocked_res["status"] == "blocked"
        assert blocked_res["executed"] is False

    def test_screen_capture_perception(self):
        engine = VisualGroundingEngine()
        meta = engine.capture_screen()
        assert meta["status"] in ("success", "simulated")
        assert meta["width"] > 0
        assert meta["height"] > 0
        assert "timestamp" in meta


# ============================================================================
# 5. Voice Pipeline Substrate Tests
# ============================================================================
class TestVoiceStreamPipeline:
    def test_audio_stream_buffer_fifo_operations(self):
        buffer = AudioStreamBuffer(max_duration_sec=1.0, sample_rate=16000)
        # 16000 samples * 2 bytes = 32000 bytes per second

        # Write 1000 bytes
        chunk = b"\x00\x01" * 500
        bytes_written = buffer.write_chunk(chunk)
        assert bytes_written == 1000
        assert buffer.size_bytes == 1000

        # Read 400 bytes
        pulled = buffer.read_chunk(400)
        assert len(pulled) == 400
        assert buffer.size_bytes == 600

        # Clear
        buffer.clear()
        assert buffer.size_bytes == 0

    def test_audio_buffer_overflow_eviction(self):
        # 0.1s max duration at 16000 samples/sec * 2 bytes = 3200 bytes max
        buffer = AudioStreamBuffer(max_duration_sec=0.1, sample_rate=16000)
        large_chunk = b"\xFF" * 5000
        buffer.write_chunk(large_chunk)

        assert buffer.size_bytes <= buffer.max_bytes
        assert buffer.size_bytes == 3200

    def test_faster_whisper_transcription_and_wake_detection(self):
        stt = FasterWhisperSTT(wake_phrases=["hey jarvis", "jarvis"])
        assert stt.is_wake_word("Hey Jarvis what time is it?") is True
        assert stt.is_wake_word("Turn off the screen") is False

        # Transcribe synthetic PCM
        dummy_pcm = b"\x00\x05" * 1600  # 0.1 sec of audio
        res = stt.transcribe_pcm(dummy_pcm)
        assert "text" in res
        assert "duration_ms" in res
        assert res["duration_ms"] >= 0

    def test_kokoro_tts_synthesis_and_streaming(self):
        tts = KokoroTTS()
        synth_res = tts.synthesize("System online and operational.")
        assert len(synth_res["pcm_data"]) > 0
        assert synth_res["sample_rate"] == 24000
        assert synth_res["duration_ms"] < 200.0

        # Stream chunks
        chunks = list(tts.stream_chunks("Low latency streaming chunk verification.", chunk_size_bytes=1024))
        assert len(chunks) > 0
        assert all(isinstance(c, bytes) for c in chunks)

    def test_voice_pipeline_coordinator(self):
        coordinator = VoicePipelineCoordinator()
        wake_events = []
        coordinator.on_wake_word(lambda txt: wake_events.append(txt))

        # Ingest audio chunk
        coordinator.ingest_audio_chunk(b"\x01\x02" * 500)
        assert coordinator.stream_buffer.size_bytes == 1000

        # Process buffer
        res = coordinator.process_buffer()
        assert "text" in res
        assert coordinator.stream_buffer.size_bytes == 0  # Buffer cleared after processing


# ============================================================================
# 6. Blueprint Edge Case & Extended API Tests
# ============================================================================
class TestBlueprintExtendedAPI:
    def test_gemini_rotator_blueprint_get_client_and_retry(self):
        rotator = GeminiKeyRotator(keys=["mock_key_acc1", "mock_key_acc2", "mock_key_acc3"])
        assert len(rotator.valid_keys) == 3

        # Test get_client cycling
        client1 = rotator.get_client()
        client2 = rotator.get_client()
        assert client1 is not None
        assert client2 is not None

        # Test generate_content_with_retry with mock client
        class MockClient:
            def __init__(self):
                self.calls = 0

            class _Models:
                def __init__(self, parent):
                    self.parent = parent

                def generate_content(self, model, contents, config=None):
                    self.parent.calls += 1
                    if self.parent.calls == 1:
                        class RateLimitError(Exception):
                            code = 429
                        raise RateLimitError("Rate limit 429")
                    class Resp:
                        text = "Synthesized response from Account 2"
                    return Resp()

            @property
            def models(self):
                return self._Models(self)

        mock_instance = MockClient()
        for k in rotator.valid_keys:
            rotator.clients[k] = mock_instance

        resp = rotator.generate_content_with_retry("test prompt", model="gemini-2.0-flash")
        assert resp.text == "Synthesized response from Account 2"
        assert mock_instance.calls == 2

    def test_jarvis_core_config_wiring(self):
        import jarvis.core.config as core_config
        assert hasattr(core_config, "settings")
        assert hasattr(core_config, "api_key_rotator")
        assert hasattr(core_config, "gemini_rotator")
        assert hasattr(core_config, "openrouter_rotator")
        assert core_config.settings is not None

    def test_uitars_start_box_and_advanced_actions(self):
        engine = VisualGroundingEngine(display_width=1920, display_height=1080)
        output = """
        Action: click(start_box='[100, 200, 300, 400]')
        Action: right_click(point='(150, 250)')
        Action: scroll(direction='down')
        Action: drag(start=[50, 50], end=[500, 500])
        Action: type(text="Testing UI-TARS 1.5 format")
        """
        actions = engine.parse_uitars_output(output)
        assert len(actions) == 5

        # Bounding box centroid: (100+300)/2 = 200, (200+400)/2 = 300
        assert actions[0].action_type == "click"
        assert actions[0].norm_x == 200.0
        assert actions[0].norm_y == 300.0

        # Right click with parentheses
        assert actions[1].action_type == "right_click"
        assert actions[1].norm_x == 150.0
        assert actions[1].norm_y == 250.0

        # Scroll
        assert actions[2].action_type == "scroll"
        assert actions[2].keys == "down"

        # Drag
        assert actions[3].action_type == "drag"
        assert actions[3].drag_to_norm_x == 500.0

        # Type text
        assert actions[4].action_type == "type"
        assert actions[4].target_text == "Testing UI-TARS 1.5 format"
