#!/usr/bin/env python3
import json, logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
from hardware import ExtensionManager

log = logging.getLogger("Daedalus.Calibration")

@dataclass
class TargetProfile:
    chip_id: str
    manufacturer: str = "unknown"
    package_type: str = "unknown"
    dram_rows: int = 0
    dram_banks: int = 0
    voltage_nominal: float = 1.2
    temp_coefficient: float = 20.0
    known_vulnerabilities: List[str] = None
    def __post_init__(self):
        if self.known_vulnerabilities is None:
            self.known_vulnerabilities = []

@dataclass
class CalibrationPoint:
    parameter: str
    value: Any
    result: str
    timestamp: str
    operator_notes: str

class CalibrationSession:
    def __init__(self, cell_id: int, target: TargetProfile):
        self.cell_id = cell_id
        self.target = target
        self.started = datetime.utcnow().isoformat()
        self.points: List[CalibrationPoint] = []
        self.active = True
        log.info(f"Calibration session started: Cell {cell_id} / {target.chip_id}")

    def log_point(self, parameter: str, value: Any, result: str, notes: str = ""):
        point = CalibrationPoint(
            parameter=parameter, value=value, result=result,
            timestamp=datetime.utcnow().isoformat(), operator_notes=notes
        )
        self.points.append(point)
        log.info(f"  Cal point: {parameter}={value} -> {result}")

    def export(self) -> Dict:
        return {
            "cell_id": self.cell_id,
            "target": asdict(self.target),
            "started": self.started,
            "points": [asdict(p) for p in self.points]
        }

class CalibrationEngine:
    def __init__(self, storage_path: str = "calibration_db.json"):
        self.storage_path = storage_path
        self.sessions: Dict[str, CalibrationSession] = {}
        self.calibration_db: Dict[str, Dict] = {}
        self._load_db()

    def _load_db(self):
        if Path(self.storage_path).exists():
            try:
                with open(self.storage_path) as f:
                    self.calibration_db = json.load(f)
                log.info(f"Loaded calibration DB: {len(self.calibration_db)} profiles")
            except Exception as e:
                log.error(f"Calibration DB load error: {e}")

    def _save_db(self):
        with open(self.storage_path, "w") as f:
            json.dump(self.calibration_db, f, indent=2)

    def run_session(self, cell_id: int, target: TargetProfile, extensions: ExtensionManager) -> Dict:
        key = f"{cell_id}_{target.chip_id}"
        session = CalibrationSession(cell_id, target)
        self.sessions[key] = session

        print(f"\n{'='*60}")
        print(f"CALIBRATION SESSION: Cell {cell_id} | Target {target.chip_id}")
        print(f"{'='*60}")
        print("This is a PHYSICAL calibration. The framework prompts parameters;")
        print("YOU must adjust the hardware and report results.\n")

        if target.dram_rows > 0:
            print("--- DRAM Rowhammer Calibration ---")
            for aggressor_pair in [(0,1), (2,3), (10,11)]:
                print(f"\nTesting aggressor pair: rows {aggressor_pair}")
                for hammer_count in [10000, 50000, 100000, 500000]:
                    user_result = input(f"  Hammer count {hammer_count}: flips observed? (y/n/count): ").strip()
                    session.log_point("rowhammer_aggressor_pair",
                        {"rows": aggressor_pair, "count": hammer_count}, user_result,
                        notes="Manual operator observation")
                    if user_result.lower().startswith("y"):
                        break

        print("\n--- EMFI Calibration ---")
        for voltage in [100, 200, 300, 400, 500]:
            for z_height in [0.5, 1.0, 2.0, 3.0]:
                user_result = input(f"  EMFI {voltage}V @ Z={z_height}mm: fault? (y/n/partial): ").strip()
                session.log_point("emfi_pulse",{"voltage": voltage, "z_height": z_height}, user_result)
                if user_result.lower().startswith("y"):
                    break
            if user_result.lower().startswith("y"):
                break

        print("\n--- Laser Fault Injection Calibration ---")
        for power in [50, 100, 200, 300]:
            for x in [0.0, 0.5, 1.0, -0.5, -1.0]:
                for y in [0.0, 0.5, 1.0, -0.5, -1.0]:
                    user_result = input(f"  Laser {power}mW @ ({x},{y}): fault? (y/n): ").strip()
                    session.log_point("laser_position", {"power_mw": power, "x": x, "y": y}, user_result)
                    if user_result.lower().startswith("y"):
                        break
                if user_result.lower().startswith("y"):
                    break
            if user_result.lower().startswith("y"):
                break

        print("\n--- Thermal Calibration ---")
        for temp in [40, 60, 80, 100, 120]:
            user_result = input(f"  Target temp {temp}C: stable? errors? (stable/errors/crash): ").strip()
            session.log_point("thermal_stress", temp, user_result)
            if "crash" in user_result.lower():
                break

        print("\n--- Voltage Glitch Calibration ---")
        for v_glitch in [1.0, 0.9, 0.8, 0.7, 0.6]:
            for width in [50, 100, 200, 500]:
                user_result = input(f"  Glitch to {v_glitch}V for {width}ns: fault? (y/n): ").strip()
                session.log_point("voltage_glitch", {"v_glitch": v_glitch, "width_ns": width}, user_result)
                if user_result.lower().startswith("y"):
                    break
            if user_result.lower().startswith("y"):
                break

        best_params = self._extract_best_params(session)
        self.calibration_db[key] = best_params
        self._save_db()

        session_path = f"calibration_{key}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(session_path, "w") as f:
            json.dump(session.export(), f, indent=2)

        log.info(f"Calibration complete. Best params saved. Log: {session_path}")
        return best_params

    def _extract_best_params(self, session: CalibrationSession) -> Dict:
        best = {}
        for point in session.points:
            if point.result.lower().startswith("y"):
                if point.parameter == "rowhammer_aggressor_pair":
                    best["rowhammer_aggressors"] = point.value["rows"]
                    best["rowhammer_count"] = point.value["count"]
                elif point.parameter == "emfi_pulse":
                    best["emfi_voltage"] = point.value["voltage"]
                    best["emfi_z_height"] = point.value["z_height"]
                elif point.parameter == "laser_position":
                    best["laser_power_mw"] = point.value["power_mw"]
                    best["laser_x"] = point.value["x"]
                    best["laser_y"] = point.value["y"]
                elif point.parameter == "thermal_stress":
                    best["thermal_target"] = point.value
                elif point.parameter == "voltage_glitch":
                    best["glitch_voltage"] = point.value["v_glitch"]
                    best["glitch_width_ns"] = point.value["width_ns"]
        return best

    def get_calibration(self, cell_id: int, chip_id: str) -> Optional[Dict]:
        key = f"{cell_id}_{chip_id}"
        return self.calibration_db.get(key)
