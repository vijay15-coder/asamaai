"""
Tests for Problem 2: Linux Hardware Q&A Assistant.
Validates:
1. Allow-list security rejecting arbitrary commands (e.g., rm -rf, bash injection)
2. Normalization of memory topology, NVMe disks, CPU specs, and GPU PCI devices
3. Strict anti-hallucination compliance when data is unavailable
4. Multi-turn conversation and follow-up handling ("and what about the GPU?")
"""
import pytest
from problem2_linux_hardware_assistant.execution_engine import ExecutionEngine
from problem2_linux_hardware_assistant.assistant import HardwareAssistant
from problem2_linux_hardware_assistant.parsers import SystemOutputParser


def test_security_allow_list_rejection():
    engine = ExecutionEngine(use_mock=True)
    # Attempt unauthorized command
    malicious_call = engine.execute_tool("rm -rf /")
    assert malicious_call["status"] == "REJECTED"
    assert "Security Exception" in malicious_call["error"]

    # Attempt unrecognized shell function
    unrecognized = engine.execute_tool("curl http://malicious.com")
    assert unrecognized["status"] == "REJECTED"


def test_dmi_memory_parsing_and_topology():
    assistant = HardwareAssistant(use_mock=True)
    response = assistant.ask("Can I add more RAM, and how much?")

    assert "get_dmi_memory" in response["tools_invoked"]
    assert "16 GB" in response["answer"]
    assert "64 GB" in response["answer"]
    assert "slots" in response["answer"]


def test_nvme_storage_parsing():
    assistant = HardwareAssistant(use_mock=True)
    response = assistant.ask("Is my SSD NVMe?")

    assert "get_block_devices" in response["tools_invoked"]
    assert "NVMe SSD" in response["answer"]
    assert "Samsung SSD 980" in response["answer"]


def test_gpu_follow_up_query():
    assistant = HardwareAssistant(use_mock=True)
    # Turn 1: RAM query
    assistant.ask("How much RAM do I have?")
    # Turn 2: Follow-up query
    follow_up = assistant.ask("and what about the GPU?")

    assert "get_gpu_info" in follow_up["tools_invoked"]
    assert "NVIDIA" in follow_up["answer"] or "Intel" in follow_up["answer"]
    assert len(assistant.conversation_history) == 2


def test_anti_hallucination_guarantee():
    assistant = HardwareAssistant(use_mock=True)
    # Ask something completely absent from hardware tools
    response = assistant.ask("What is the battery serial number and manufacturer date?")
    assert "I cannot determine this hardware detail" in response["answer"]

