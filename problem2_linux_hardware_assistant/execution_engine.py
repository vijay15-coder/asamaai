"""
Secure Execution Engine with Allow-List, Non-Root Fallbacks, and Sandboxing.
Key architectural properties:
1. `shell=False`: Bypasses subshells, nullifying command injection (;, &&, |, ``, $())
2. Strict Allow-List: Rejects any unrecognized command or tool
3. Privileged Command Strategy: Scoped sudo wrapper with non-root fallback to unprivileged sysfs/procfs
4. Cross-platform / Mock execution mode for testing on non-Linux hosts
"""
import os
import shutil
import subprocess
from typing import Dict, Any, List, Optional
from .parsers import SystemOutputParser


# Strict mapping of allowable tools to fixed binary paths and flags
ALLOW_LISTED_COMMANDS: Dict[str, List[str]] = {
    "get_cpu_info": ["lscpu"],
    "get_block_devices": ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,MODEL,ROTA,TRAN"],
    "get_system_memory_summary": ["free", "-h"],
    "get_dmi_memory": ["sudo", "/usr/sbin/dmidecode", "-t", "memory"],
    "get_gpu_info": ["lspci"]
}


# Realistic Linux hardware mock fixtures for offline / non-Linux testing & CI
MOCK_SYSTEM_OUTPUTS = {
    "get_dmi_memory": """# dmidecode 3.5
Getting SMBIOS data from sysfs.
SMBIOS 3.3.0 present.

Handle 0x0010, DMI type 16, 23 bytes
Physical Memory Array
	Location: System Board
	Use: System Memory
	Error Correction Type: None
	Maximum Capacity: 64 GB
	Number Of Devices: 2

Handle 0x0011, DMI type 17, 92 bytes
Memory Device
	Array Handle: 0x0010
	Total Width: 64 bits
	Data Width: 64 bits
	Size: 16 GB
	Form Factor: SODIMM
	Set: None
	Locator: ChannelA-DIMM0
	Bank Locator: BANK 0
	Type: DDR4
	Type Detail: Synchronous Unbuffered (Unregistered)
	Speed: 3200 MT/s
	Manufacturer: Kingston

Handle 0x0012, DMI type 17, 92 bytes
Memory Device
	Array Handle: 0x0010
	Total Width: Unknown
	Data Width: Unknown
	Size: No Module Installed
	Form Factor: SODIMM
	Set: None
	Locator: ChannelB-DIMM0
	Bank Locator: BANK 1
	Type: Unknown
""",
    "get_block_devices": """{
   "blockdevices": [
      {
         "name": "nvme0n1",
         "size": "512G",
         "type": "disk",
         "mountpoint": null,
         "model": "Samsung SSD 980 500GB",
         "rota": false,
         "tran": "nvme",
         "children": [
            {
               "name": "nvme0n1p1",
               "size": "512M",
               "type": "part",
               "mountpoint": "/boot/efi",
               "model": null,
               "rota": false,
               "tran": null
            },
            {
               "name": "nvme0n1p2",
               "size": "511.5G",
               "type": "part",
               "mountpoint": "/",
               "model": null,
               "rota": false,
               "tran": null
            }
         ]
      }
   ]
}""",
    "get_cpu_info": """Architecture:                    x86_64
CPU op-mode(s):                  32-bit, 64-bit
Address sizes:                   39 bits physical, 48 bits virtual
Byte Order:                      Little Endian
CPU(s):                          16
On-line CPU(s) list:             0-15
Vendor ID:                       GenuineIntel
Model name:                      12th Gen Intel(R) Core(TM) i7-12700H
CPU family:                      6
Model:                           154
Thread(s) per core:              2
Core(s) per socket:              14
Socket(s):                       1
CPU max MHz:                     4700.0000
CPU min MHz:                     400.0000
Virtualization:                  VT-x
""",
    "get_gpu_info": """00:02.0 VGA compatible controller: Intel Corporation Alder Lake-P Integrated Graphics (rev 0c)
01:00.0 3D controller: NVIDIA Corporation GA106M [GeForce RTX 3060 Mobile / Max-Q] (rev a1)
""",
    "get_system_memory_summary": """               total        used        free      shared  buff/cache   available
Mem:            15Gi       4.2Gi       8.1Gi       240Mi       2.7Gi        10Gi
Swap:          2.0Gi          0B       2.0Gi
"""
}


class ExecutionEngine:
    """
    Safely executes allow-listed commands or falls back to parsed hardware fixtures/unprivileged interfaces.
    """

    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock or (os.name != "posix")

    def execute_tool(self, tool_name: str, kwargs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes a validated allow-listed tool and returns normalized structured JSON.
        """
        if tool_name not in ALLOW_LISTED_COMMANDS:
            return {
                "error": f"Security Exception: Tool '{tool_name}' is not in the authorized allow-list.",
                "status": "REJECTED"
            }

        kwargs = kwargs or {}

        # 1. Mock / Non-Linux Test Environment Handling
        if self.use_mock:
            raw_stdout = MOCK_SYSTEM_OUTPUTS.get(tool_name, "")
            return self._dispatch_parser(tool_name, raw_stdout, kwargs)

        # 2. Production Live Execution
        cmd = ALLOW_LISTED_COMMANDS[tool_name]
        binary = cmd[0] if cmd[0] != "sudo" else cmd[1]

        # Verify binary presence
        if not shutil.which(binary):
            # Fallback for dmidecode when unprivileged or binary missing
            if tool_name == "get_dmi_memory":
                return self._fallback_unprivileged_memory()
            return {"error": f"System utility '{binary}' is not available on this distribution."}

        try:
            # shell=False ensures argument array is passed directly to execve without subshell
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
                shell=False
            )
            return self._dispatch_parser(tool_name, res.stdout, kwargs)
        except subprocess.TimeoutExpired:
            return {"error": f"Tool '{tool_name}' timed out after 5 seconds."}
        except subprocess.CalledProcessError as e:
            # If sudo failed or permission denied, attempt unprivileged fallback
            if tool_name == "get_dmi_memory":
                return self._fallback_unprivileged_memory()
            return {"error": f"Execution failed for '{tool_name}': {e.stderr.strip()}"}
        except Exception as e:
            return {"error": f"Unexpected execution error: {str(e)}"}

    def _fallback_unprivileged_memory(self) -> Dict[str, Any]:
        """
        Fallback reading /proc/meminfo or /sys/class/dmi/id when root/dmidecode is inaccessible.
        """
        if os.path.exists("/proc/meminfo"):
            try:
                with open("/proc/meminfo", "r") as f:
                    content = f.read()
                mem_total = 0
                for line in content.splitlines():
                    if line.startswith("MemTotal:"):
                        mem_total = line.split(":")[1].strip()
                return {
                    "maximum_supported_capacity": "Unknown (dmidecode requires root privilege)",
                    "installed_capacity_approx": mem_total,
                    "note": "Read from /proc/meminfo fallback. Deep BIOS DMI information requires scoped sudo access."
                }
            except Exception:
                pass
        return {"error": "Root access required for BIOS memory slots and /proc/meminfo unreadable."}

    def _dispatch_parser(self, tool_name: str, stdout: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Routes raw output to appropriate normalizer."""
        if tool_name == "get_memory_topology":
            return SystemOutputParser.parse_dmi_memory(stdout, kwargs.get("include_empty_slots", True))
        elif tool_name == "get_cpu_info":
            return SystemOutputParser.parse_cpu_info(stdout)
        elif tool_name == "get_block_devices":
            return SystemOutputParser.parse_block_devices(stdout, kwargs.get("device_name"))
        elif tool_name == "get_gpu_info":
            return SystemOutputParser.parse_lspci_gpu(stdout)
        elif tool_name == "get_system_memory_summary":
            return SystemOutputParser.parse_free_memory(stdout)
        elif tool_name == "get_dmi_memory":
            return SystemOutputParser.parse_dmi_memory(stdout, kwargs.get("include_empty_slots", True))
        return {"raw": stdout}

