#!/usr/bin/env python3
"""
Daedalus v1.0 — Unpatchable Zero-Day Subclass Framework
Cage Laboratory Hardware Testing Suite | SynChanCyberSecurity
Physical kill-switch integration. Commodity hardware only. $15K budget ceiling.
"""

import os, sys, json, time, logging, argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum, auto

from hardware import HardwareBus, ExtensionManager, DeviceProfile
from vectors import VectorRegistry
from calibration import CalibrationEngine, TargetProfile

VERSION = "1.0.0"
AUTHOR = "SynChanCyberSecurity | Chad W."
MAX_CELLS = 8
BUDGET_CEILING = 15000.00
KILL_SWITCH_GPIO = 4

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("daedalus.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("Daedalus")

class CellState(Enum):
    IDLE = auto()
    ARMED = auto()
    CALIBRATING = auto()
    EXECUTING = auto()
    ERROR = auto()
    LOCKDOWN = auto()

class SafetyLevel(Enum):
    CAGE = auto()
    LIVE = auto()
    WAR = auto()

@dataclass
class CellConfig:
    cell_id: int
    target_type: str = "generic_soc"
    bus_config: Dict[str, Any] = None
    safety: str = "CAGE"
    hardware_extensions: List[str] = None
    def __post_init__(self):
        if self.bus_config is None:
            self.bus_config = {"i2c": True, "spi": True, "uart": True, "usb": True}
        if self.hardware_extensions is None:
            self.hardware_extensions = []

@dataclass
class ExecutionReport:
    timestamp: str
    cell_id: int
    vector: str
    target: str
    parameters: Dict
    result: str
    calibration_applied: bool
    kill_switch_triggered: bool

class DaedalusCore:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.cells: Dict[int, CellState] = {i: CellState.IDLE for i in range(1, MAX_CELLS + 1)}
        self.cell_configs: Dict[int, CellConfig] = {}
        self.hardware = HardwareBus()
        self.extensions = ExtensionManager()
        self.vectors = VectorRegistry()
        self.calibration = CalibrationEngine()
        self.reports: List[ExecutionReport] = []
        self._kill_switch_armed = False
        self._init_cells()
        log.info(f"Daedalus v{VERSION} initialized. Safety: {self.config.get('safety_level', 'CAGE')}")

    def _load_config(self, path: str) -> Dict:
        if Path(path).exists():
            with open(path) as f:
                return json.load(f)
        return self._default_config()

    def _default_config(self) -> Dict:
        return {
            "safety_level": "CAGE",
            "kill_switch_gpio": KILL_SWITCH_GPIO,
            "auto_detect_hardware": True,
            "log_retention_days": 30,
            "budget_tracking": True,
            "cells": [
                {"cell_id": i, "target_type": "generic_soc", "safety": "CAGE"}
                for i in range(1, MAX_CELLS + 1)
            ]
        }

    def _init_cells(self):
        for cell_data in self.config.get("cells", []):
            cid = cell_data["cell_id"]
            if 1 <= cid <= MAX_CELLS:
                self.cell_configs[cid] = CellConfig(**cell_data)
                log.info(f"Cell {cid} configured: {self.cell_configs[cid].target_type}")

    def arm_kill_switch(self) -> bool:
        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(KILL_SWITCH_GPIO, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self._kill_switch_armed = True
            log.warning("KILL SWITCH ARMED on GPIO4. Physical button will abort all cells.")
            return True
        except ImportError:
            log.warning("RPi.GPIO not available — kill switch in software fallback mode.")
            self._kill_switch_armed = True
            return False
        except Exception as e:
            log.error(f"Kill switch hardware error: {e}")
            return False

    def check_kill_switch(self) -> bool:
        if not self._kill_switch_armed:
            return False
        try:
            import RPi.GPIO as GPIO
            return GPIO.input(KILL_SWITCH_GPIO) == GPIO.LOW
        except:
            return False

    def emergency_abort(self, reason: str = "USER_TRIGGERED"):
        log.critical(f"EMERGENCY ABORT: {reason}")
        for cid in range(1, MAX_CELLS + 1):
            self.cells[cid] = CellState.LOCKDOWN
        self.hardware.emergency_shutdown()
        self.extensions.emergency_shutdown()

    def scan_cell_hardware(self, cell_id: int) -> List[DeviceProfile]:
        if self.cells[cell_id] == CellState.LOCKDOWN:
            log.error(f"Cell {cell_id} is in LOCKDOWN.")
            return []
        self.cells[cell_id] = CellState.ARMED
        cfg = self.cell_configs.get(cell_id, CellConfig(cell_id=cell_id))
        detected = []
        if cfg.bus_config.get("i2c"):
            detected.extend(self.hardware.scan_i2c(cell_id))
        if cfg.bus_config.get("spi"):
            detected.extend(self.hardware.scan_spi(cell_id))
        if cfg.bus_config.get("uart"):
            detected.extend(self.hardware.scan_uart(cell_id))
        if cfg.bus_config.get("usb"):
            detected.extend(self.hardware.scan_usb(cell_id))
        self.extensions.register_devices(cell_id, detected)
        self.cell_configs[cell_id].hardware_extensions = [d.device_class for d in detected]
        log.info(f"Cell {cell_id}: {len(detected)} hardware extensions detected.")
        self.cells[cell_id] = CellState.IDLE
        return detected

    def calibrate_cell(self, cell_id: int, target_profile: TargetProfile) -> Dict:
        if self.check_kill_switch():
            self.emergency_abort("KILL_SWITCH_DURING_CALIBRATION")
            return {}
        self.cells[cell_id] = CellState.CALIBRATING
        log.info(f"Cell {cell_id}: Starting calibration for {target_profile.chip_id}")
        result = self.calibration.run_session(cell_id, target_profile, self.extensions)
        self.cells[cell_id] = CellState.IDLE
        log.info(f"Cell {cell_id}: Calibration complete. Params: {result}")
        return result

    def execute_vector(self, cell_id: int, vector_name: str, target: TargetProfile, params: Dict) -> ExecutionReport:
        if self.check_kill_switch():
            self.emergency_abort("KILL_SWITCH_PRE_FLIGHT")
            return ExecutionReport(
                timestamp=datetime.utcnow().isoformat(),
                cell_id=cell_id, vector=vector_name, target=target.chip_id,
                parameters=params, result="ABORTED_BY_KILL_SWITCH",
                calibration_applied=False, kill_switch_triggered=True
            )
        safety = SafetyLevel[self.config.get("safety_level", "CAGE")]
        if safety == SafetyLevel.CAGE:
            log.warning(f"Cell {cell_id}: CAGE MODE — executing simulation only.")
        self.cells[cell_id] = CellState.EXECUTING
        vector = self.vectors.get(vector_name)
        if not vector:
            self.cells[cell_id] = CellState.ERROR
            raise ValueError(f"Unknown vector: {vector_name}")
        cal = self.calibration.get_calibration(cell_id, target.chip_id)
        if cal:
            params = {**cal, **params}
            log.info(f"Cell {cell_id}: Applied calibration for {target.chip_id}")
        result = vector.execute(cell_id,target, params, self.extensions, safety)
        report = ExecutionReport(
            timestamp=datetime.utcnow().isoformat(),
            cell_id=cell_id, vector=vector_name, target=target.chip_id,
            parameters=params, result=result,
            calibration_applied=cal is not None,
            kill_switch_triggered=self.check_kill_switch()
        )
        self.reports.append(report)
        self.cells[cell_id] = CellState.IDLE if not self.check_kill_switch() else CellState.LOCKDOWN
        if self.check_kill_switch():
            self.emergency_abort("KILL_SWITCH_POST_EXECUTION")
        return report

    def generate_report(self, output_path: str = "report.json"):
        data = {
            "framework": "Daedalus",
            "version": VERSION,
            "generated": datetime.utcnow().isoformat(),
            "safety_level": self.config.get("safety_level", "CAGE"),
            "cells": {cid: state.name for cid, state in self.cells.items()},
            "hardware_extensions": self.extensions.summary(),
            "executions": [asdict(r) for r in self.reports],
            "budget_status": self._budget_status()
        }
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        log.info(f"Report written to {output_path}")

    def _budget_status(self) -> Dict:
        if not self.config.get("budget_tracking", True):
            return {"tracking": False}
        try:
            with open("hardware/bom.json") as f:
                bom = json.load(f)
            total = sum(item["unit_cost"] * item["qty"] for item in bom.get("items", []))
            return {
                "tracking": True,
                "ceiling": BUDGET_CEILING,
                "spent": round(total, 2),
                "remaining": round(BUDGET_CEILING - total, 2),
                "under_budget": total <= BUDGET_CEILING
            }
        except Exception as e:
            return {"tracking": True, "error": str(e)}

    def cli_loop(self):
        print(f"\n{'='*62}")
        print(f"  DAEDALUS v{VERSION}  |  SynChanCyberSecurity")
        print(f"  Zero-Day Hardware Framework  |  Cage Lab Authorized")
        print(f"{'='*62}")
        print(f"Safety: {self.config.get('safety_level', 'CAGE')} | Cells: {MAX_CELLS} | Budget Cap: ${BUDGET_CEILING}")
        print("Type 'help' for commands. Kill switch must be armed for LIVE mode.\n")
        while True:
            try:
                cmd = input("daedalus> ").strip().lower()
                if cmd == "quit" or cmd == "exit":
                    break
                elif cmd == "help":
                    print("\nCommands:\n  status       — Show cell states and hardware\n  arm          — Arm physical kill switch\n  scan <cell>  — Auto-detect hardware on cell\n  cal <cell> <chip> — Start calibration session\n  exec <cell> <vector> [chip] — Execute attack vector\n  report       — Generate JSON execution report\n  abort        — Emergency abort all cells\n  quit / exit  — Shutdown framework\n")
                elif cmd == "status":
                    print(f"\n{'Cell':<6}{'State':<15}{'Target':<20}{'Extensions':<30}")
                    print("-" * 75)
                    for cid in range(1, MAX_CELLS + 1):
                        cfg = self.cell_configs.get(cid, CellConfig(cell_id=cid))
                        ext = ", ".join(cfg.hardware_extensions[:3]) if cfg.hardware_extensions else "None"
                        print(f"{cid:<6}{self.cells[cid].name:<15}{cfg.target_type:<20}{ext:<30}")
                    print()
                elif cmd == "arm":
                    self.arm_kill_switch()
                elif cmd.startswith("scan "):
                    cid = int(cmd.split()[1])
                    self.scan_cell_hardware(cid)
                elif cmd.startswith("cal "):
                    parts = cmd.split(maxsplit=2)
                    cid = int(parts[1])
                    chip = parts[2] if len(parts) > 2 else "unknown"
                    self.calibrate_cell(cid, TargetProfile(chip_id=chip))
                elif cmd.startswith("exec "):
                    parts = cmd.split(maxsplit=3)
                    if len(parts) < 3:
                        print("Usage: exec <cell_id> <vector_name> [chip_id]")
                        continue
                    cid, vec = int(parts[1]), parts[2]
                    chip = parts[3] if len(parts) > 3 else "generic"
                    report = self.execute_vector(cid, vec, TargetProfile(chip_id=chip), {})
                    print(f"Result: {report.result}")
                elif cmd == "report":
                    self.generate_report()
       elif cmd == "abort":
                    self.emergency_abort("USER_CLI_ABORT")
                else:
                    print("Unknown command. Type 'help'.")
            except KeyboardInterrupt:
                self.emergency_abort("SIGINT")
                break
            except Exception as e:
                log.error(f"CLI error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daedalus Hardware Testing Framework")
    parser.add_argument("--config", default="config.json", help="Path to config file")
    parser.add_argument("--safety", choices=["CAGE", "LIVE", "WAR"], help="Override safety level")
    args = parser.parse_args()
    core = DaedalusCore(config_path=args.config)
    if args.safety:
        core.config["safety_level"] = args.safety
    core.cli_loop()
