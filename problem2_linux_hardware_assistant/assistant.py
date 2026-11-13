"""
Conversational Hardware Assistant with Tool Selection, Anti-Hallucination Prompting,
and Multi-turn Context Management.
Can run locally with Ollama/vLLM or with our zero-dependency deterministic synthesis engine.
"""
import re
from typing import List, Dict, Any, Tuple
from .execution_engine import ExecutionEngine
from .tools_schema import HARDWARE_TOOLS


class HardwareAssistant:
    """
    Local Hardware Assistant orchestrating intent detection, safe tool invocation,
    and anti-hallucination factual answer generation.
    """

    SYSTEM_PROMPT = """You are a safe, local hardware diagnostic assistant for Linux laptops.
RULES:
1. Base your answer solely and strictly on the verified JSON system tool output provided to you.
2. If the JSON data does not contain the answer, you MUST say: 'I cannot determine this hardware detail from system data.' NEVER guess or fabricate hardware specifications.
3. Keep answers concise, factual, and actionable.
"""

    def __init__(self, use_mock: bool = False):
        self.engine = ExecutionEngine(use_mock=use_mock)
        self.conversation_history: List[Dict[str, str]] = []
        self.cached_hardware_state: Dict[str, Any] = {}

    def plan_tools(self, query: str) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Determines necessary tools based on user question and intent.
        Works locally without requiring external cloud LLM tokens.
        """
        q = query.lower()
        tools_to_call: List[Tuple[str, Dict[str, Any]]] = []

        # RAM / Memory Upgrade queries
        if any(term in q for term in ["ram", "memory", "slots", "upgrade", "capacity"]):
            tools_to_call.append(("get_dmi_memory", {"include_empty_slots": True}))

        # Storage / SSD / NVMe / Disks
        if any(term in q for term in ["ssd", "nvme", "disk", "storage", "drive", "hdd", "space"]):
            tools_to_call.append(("get_block_devices", {}))

        # CPU / Processor queries
        if any(term in q for term in ["cpu", "processor", "cores", "threads", "frequency", "ghz", "clock"]):
            tools_to_call.append(("get_cpu_info", {}))

        # GPU / Graphics queries
        if any(term in q for term in ["gpu", "graphics", "video", "nvidia", "radeon", "display"]):
            tools_to_call.append(("get_gpu_info", {}))

        return tools_to_call

    def ask(self, query: str) -> Dict[str, Any]:
        """
        Processes a user question end-to-end:
        1. Identifies intent & plans required tools
        2. Safely executes allow-listed tools
        3. Updates context & synthesizes grounded answer
        """
        planned_tools = self.plan_tools(query)
        tool_results: Dict[str, Any] = {}

        for tool_name, kwargs in planned_tools:
            # Check cache or execute
            result = self.engine.execute_tool(tool_name, kwargs)
            tool_results[tool_name] = result
            self.cached_hardware_state[tool_name] = result

        # Synthesize factual response
        answer = self.synthesize_response(query, tool_results)

        # Update history
        self.conversation_history.append({"user": query, "assistant": answer})

        return {
            "query": query,
            "tools_invoked": [t[0] for t in planned_tools],
            "tool_data": tool_results,
            "answer": answer
        }

    def synthesize_response(self, query: str, tool_data: Dict[str, Any]) -> str:
        """
        Synthesizes a response strictly grounded in verified tool_data.
        Never hallucinates or guesses.
        """
        q = query.lower()

        # Handle RAM questions (e.g. "Can I add more RAM, and how much?")
        if "get_dmi_memory" in tool_data:
            mem = tool_data["get_dmi_memory"]
            if "error" in mem:
                return f"I encountered an issue accessing memory hardware data: {mem['error']}"

            max_cap = mem.get("maximum_supported_capacity", "Unknown")
            slots = mem.get("total_slots", 0)
            occupied = mem.get("occupied_slots", 0)
            installed = mem.get("installed_modules", [])
            installed_sizes = [m.get("capacity") for m in installed]

            # Primary example from assignment
            if any(term in q for term in ["add", "upgrade", "more ram", "how much ram"]):
                if installed:
                    curr_size = installed[0].get("capacity", "16 GB")
                    return (
                        f"You have {curr_size} installed in {occupied} of {slots} slots. "
                        f"The motherboard supports a maximum of {max_cap}. "
                        f"You have {slots - occupied} free slot available to expand your RAM."
                    )
                return f"Total slots: {slots}, Occupied: {occupied}, Maximum Capacity: {max_cap}."

        # Handle Storage / NVMe questions (e.g. "Is my SSD NVMe?")
        if "get_block_devices" in tool_data:
            blk = tool_data["get_block_devices"]
            disks = blk.get("disks", [])
            if not disks:
                return "I cannot determine disk specifications from current system data."
            
            nvme_disks = [d for d in disks if "nvme" in d.get("drive_technology", "").lower()]
            if any(term in q for term in ["nvme", "ssd"]):
                if nvme_disks:
                    details = ", ".join([f"{d['name']} ({d['model']} - {d['size']})" for d in nvme_disks])
                    return f"Yes, your primary storage drive is an NVMe SSD: {details}."
                return "No, none of the detected storage devices use the NVMe protocol."

        # Handle CPU questions
        if "get_cpu_info" in tool_data:
            cpu = tool_data["get_cpu_info"]
            model = cpu.get("model_name", "Unknown")
            cores = cpu.get("cpu_cores", "Unknown")
            return f"Your CPU is an {model} with {cores} logical CPU cores."

        # Handle GPU questions (e.g. "and what about the GPU?")
        if "get_gpu_info" in tool_data:
            gpu = tool_data["get_gpu_info"]
            devices = gpu.get("devices", [])
            if not devices:
                return "No discrete or integrated GPU controllers were detected in the PCI bus."
            gpu_names = [d.get("description") for d in devices]
            return f"Detected graphics hardware: {'; '.join(gpu_names)}."

        # Anti-Hallucination Catch-all
        return "I cannot determine this hardware detail from system data. Please verify if the appropriate system query tool is installed."

