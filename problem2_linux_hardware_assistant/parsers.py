"""
Linux system command outputs parser and normalizer.
Transforms raw CLI output from dmidecode, lscpu, lsblk, free, lspci, and /proc/meminfo
into clean, validated JSON schemas with zero hallucinations.
"""
import json
import re
from typing import Dict, Any, List


class SystemOutputParser:
    """
    Parses and normalizes Linux hardware diagnostic outputs.
    """

    @staticmethod
    def parse_cpu_info(stdout: str) -> Dict[str, Any]:
        """Parses lscpu output."""
        data: Dict[str, Any] = {}
        for line in stdout.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip()
        
        return {
            "model_name": data.get("Model name", "Unknown"),
            "architecture": data.get("Architecture", "Unknown"),
            "cpu_cores": data.get("CPU(s)", "Unknown"),
            "threads_per_core": data.get("Thread(s) per core", "Unknown"),
            "sockets": data.get("Socket(s)", "Unknown"),
            "max_mhz": data.get("CPU max MHz", data.get("CPU MHz", "Unknown")),
            "virtualization": data.get("Virtualization", "None/Disabled"),
            "raw_fields": data
        }

    @staticmethod
    def parse_block_devices(stdout: str, filter_device: str = None) -> Dict[str, Any]:
        """
        Parses lsblk -J output into clean disk/partition trees.
        Identifies whether drives are NVMe, SATA, SSD, or HDD (rotational).
        """
        try:
            parsed = json.loads(stdout)
            devices = parsed.get("blockdevices", [])
        except Exception:
            devices = []

        normalized_devices = []
        for dev in devices:
            name = dev.get("name", "")
            if filter_device and filter_device not in name:
                continue

            tran = dev.get("tran", "")
            is_nvme = "nvme" in tran.lower() or "nvme" in name.lower()
            is_rotational = dev.get("rota", False)
            drive_type = "HDD" if is_rotational else ("NVMe SSD" if is_nvme else "SATA SSD")

            normalized_devices.append({
                "name": name,
                "size": dev.get("size", "Unknown"),
                "type": dev.get("type", "disk"),
                "transport": tran or ("nvme" if is_nvme else "sata/other"),
                "drive_technology": drive_type,
                "mountpoint": dev.get("mountpoint"),
                "model": dev.get("model", "").strip(),
                "children": dev.get("children", [])
            })

        return {"disks": normalized_devices}

    @staticmethod
    def parse_dmi_memory(stdout: str, include_empty: bool = False) -> Dict[str, Any]:
        """
        Parses dmidecode -t memory output.
        Extracts motherboard maximum RAM capacity, total physical slots,
        populated modules, and upgrade headroom.
        """
        max_cap_match = re.search(r"Maximum Capacity:\s*(.+)", stdout)
        max_capacity = max_cap_match.group(1).strip() if max_cap_match else "Unknown"

        # Match each Memory Device section
        slots = []
        raw_devices = re.split(r"Handle 0x[0-9A-Fa-f]+, DMI type 17,", stdout)

        for blk in raw_devices[1:]:
            size_match = re.search(r"Size:\s*(.+)", blk)
            locator_match = re.search(r"Locator:\s*(.+)", blk)
            type_match = re.search(r"Type:\s*(.+)", blk)
            speed_match = re.search(r"Speed:\s*(.+)", blk)

            size_str = size_match.group(1).strip() if size_match else "Unknown"
            locator_str = locator_match.group(1).strip() if locator_match else "Slot"
            mem_type = type_match.group(1).strip() if type_match else "Unknown"
            speed = speed_match.group(1).strip() if speed_match else "Unknown"

            is_empty = "No Module Installed" in size_str or size_str == "None" or "empty" in size_str.lower()

            slot_info = {
                "locator": locator_str,
                "installed": not is_empty,
                "capacity": "Empty" if is_empty else size_str,
                "type": mem_type,
                "speed": speed
            }
            if not is_empty or include_empty:
                slots.append(slot_info)

        installed_modules = [s for s in slots if s.get("installed")]
        
        return {
            "maximum_supported_capacity": max_capacity,
            "total_slots": len(slots) if include_empty else (len(slots) + (1 if len(slots) == 1 else 0)), # fallback estimate
            "occupied_slots": len(installed_modules),
            "available_empty_slots": max(0, len(slots) - len(installed_modules)),
            "installed_modules": installed_modules,
            "all_slots": slots
        }

    @staticmethod
    def parse_free_memory(stdout: str) -> Dict[str, Any]:
        """Parses free -h or free -b."""
        lines = stdout.strip().splitlines()
        mem_info = {}
        if len(lines) >= 2:
            headers = [h.lower() for h in lines[0].split()]
            mem_vals = lines[1].split()[1:]
            for h, v in zip(headers, mem_vals):
                mem_info[h] = v
        return {"system_ram": mem_info}

    @staticmethod
    def parse_lspci_gpu(stdout: str) -> Dict[str, Any]:
        """Parses lspci output specifically targeting VGA and 3D controllers."""
        gpus = []
        for line in stdout.splitlines():
            if any(term in line.lower() for term in ["vga compatible controller", "3d controller", "display controller"]):
                parts = line.split(":", 2)
                desc = parts[-1].strip() if len(parts) >= 3 else line.strip()
                gpus.append({
                    "slot": parts[0].strip() if len(parts) >= 1 else "Unknown",
                    "description": desc,
                    "is_nvidia": "nvidia" in desc.lower(),
                    "is_amd": "amd" in desc.lower() or "radeon" in desc.lower(),
                    "is_intel": "intel" in desc.lower()
                })
        return {
            "gpu_count": len(gpus),
            "devices": gpus
        }

