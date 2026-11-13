"""
Safe Tool Definitions and Schemas for Problem 2: Linux Hardware Q&A Assistant.
Adheres strictly to the allow-list security model:
- No arbitrary shell string execution
- `shell=False` direct execution
- Strong typing and validated parameter constraints
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ToolParameterSchema(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]


HARDWARE_TOOLS: List[ToolParameterSchema] = [
    ToolParameterSchema(
        name="get_memory_topology",
        description="Retrieves physical RAM details including installed capacity, total slots, available slots, speed, and maximum supported motherboard capacity.",
        parameters={
            "type": "object",
            "properties": {
                "include_empty_slots": {
                    "type": "boolean",
                    "description": "Set to true to return details on unused memory slots."
                }
            },
            "required": []
        }
    ),
    ToolParameterSchema(
        name="get_cpu_info",
        description="Retrieves CPU architecture, model name, core counts, threads, clock frequencies, and cache hierarchy.",
        parameters={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    ToolParameterSchema(
        name="get_block_devices",
        description="Retrieves storage disks, partitions, NVMe vs SATA transport types, models, mount points, and rotational indicators.",
        parameters={
            "type": "object",
            "properties": {
                "device_name": {
                    "type": "string",
                    "description": "Optional specific block device name (e.g. nvme0n1 or sda) to inspect."
                }
            },
            "required": []
        }
    ),
    ToolParameterSchema(
        name="get_gpu_info",
        description="Retrieves PCI graphics cards, display controllers, GPU vendors, and driver information.",
        parameters={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    ToolParameterSchema(
        name="get_system_memory_summary",
        description="Retrieves live RAM and swap usage from /proc/meminfo or unprivileged free command.",
        parameters={
            "type": "object",
            "properties": {},
            "required": []
        }
    )
]

