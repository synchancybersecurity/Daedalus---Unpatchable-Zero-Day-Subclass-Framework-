#!/usr/bin/env python3
import random, time, logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum
from hardware import ExtensionManager
from calibration import TargetProfile

log = logging.getLogger("Daedalus.Vectors")

class SafetyLevel(Enum):
    CAGE = "cage"
    LIVE = "live"
    WAR = "war"

class AttackVector(ABC):
    name: str = "base"
    description: str = ""
    requires_extensions: list = []
    def __init__(self):
        self.safety_limits = {
            "max_voltage_delta": 0.5,
            "max_temp_delta": 80,
            "max_em_pulse_energy": 1.0,
            "max_laser_power": 500,
            "max_dram_rows": 65536
        }
    def _check_safety(self, params: Dict, safety: SafetyLevel) -> bool:
        if safety == SafetyLevel.CAGE:
            return False
        if params.get("voltage_delta", 0) > self.safety_limits["max_voltage_delta"]:
            log.critical("SAFETY: Voltage delta exceeds limit!")
            return True
        if params.get("temp_target", 25) > self.safety_limits["max_temp_delta"] + 25:
            log.critical("SAFETY: Temperature target exceeds limit!")
            return True
        return False
    @abstractmethod
    def execute(self, cell_id: int, target: TargetProfile, params: Dict, extensions: ExtensionManager, safety: SafetyLevel) -> str:
        pass

class RowhammerVector(AttackVector):
    name = "rowhammer"
    description = "Induce bit flips via aggressive DRAM row activation."
    requires_extensions = ["sdr_rtl2832"]
    def execute(self, cell_id, target, params, extensions, safety):
        if self._check_safety(params, safety):
            return "SAFETY_ABORT"
        if safety == SafetyLevel.CAGE:
            log.info(f"[CAGE] Cell {cell_id}: Simulating rowhammer on {target.chip_id}")
            flip_prob = params.get("flip_probability", 0.001)
            flips = random.choices([0, 1], weights=[1-flip_prob, flip_prob], k=1000)
            total_flips = sum(flips)
            return f"SIMULATED: {total_flips} bit flips induced across 1000 hammer pairs"
        log.warning(f"[LIVE] Cell {cell_id}: Rowhammer executing on physical DRAM")
        aggressor_rows = params.get("aggressor_rows", [0, 1])
        hammer_count = params.get("hammer_count", 100000)
        refresh_interval = params.get("refresh_interval", 64)
        try:
            result = self._native_hammer(target, aggressor_rows, hammer_count, refresh_interval)
            return result
        except Exception as e:
            return f"HARDWARE_ERROR: {e}"
    def _native_hammer(self, target, aggressors, count, refresh):
        return f"LIVE: Hammered rows {aggressors} {count} times @ {refresh}ms refresh"

class EMFIVector(AttackVector):
    name = "emfi"
    description = "Induce computational faults via localized electromagnetic pulses."
    requires_extensions = ["gpio_extension", "sdr_rtl2832"]
    def execute(self, cell_id, target, params, extensions, safety):
        if self._check_safety(params, safety):
            return "SAFETY_ABORT"
        pulse_voltage = params.get("pulse_voltage", 300)
        pulse_width = params.get("pulse_width", 10)
        coil_position = params.get("coil_position", {"x": 0.0, "y": 0.0, "z": 1.0})
        trigger_offset = params.get("trigger_offset", 0)
        if safety == SafetyLevel.CAGE:
            log.info(f"[CAGE] Cell {cell_id}: EMFI simulation — {pulse_voltage}V, {pulse_width}ns")
            fault_prob = min(0.3, pulse_voltage / 1000)
            return f"SIMULATED: EM pulse at {coil_position} — fault probability {fault_prob:.2%}"
        log.warning(f"[LIVE] Cell {cell_id}: EMFI pulse firing — {pulse_voltage}V")
        try:
            import RPi.GPIO as GPIO
            trigger_pin = params.get("trigger_pin", 17)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(trigger_pin, GPIO.OUT)
            GPIO.output(trigger_pin, GPIO.HIGH)
            time.sleep(pulse_width / 1e9)
            GPIO.output(trigger_pin, GPIO.LOW)
            return ff"SIMULATED: EM pulse at {coil_position} — fault probability {fault_prob:.2%}"
        log.warning(f"[LIVE] Cell {cell_id}: EMFI pulse firing — {pulse_voltage}V")
        try:
            import RPi.GPIO as GPIO
            trigger_pin = params.get("trigger_pin", 17)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(trigger_pin, GPIO.OUT)
            GPIO.output(trigger_pin, GPIO.HIGH)
            time.sleep(pulse_width / 1e9)
            GPIO.output(trigger_pin, GPIO.LOW)
            return f"LIVE: EMFI pulse delivered at {coil_position}"
        except Exception as e:
            return f"HARDWARE_ERROR: {e}"

class LaserVector(AttackVector):
    name = "laser"
    description = "Induce faults via focused laser illumination of target die."
    requires_extensions = ["gpio_extension"]
    def execute(self, cell_id, target, params, extensions, safety):
        if self._check_safety(params, safety):
            return "SAFETY_ABORT"
        wavelength = params.get("wavelength", 808)
        power_mw = params.get("power_mw", 100)
        duration_us = params.get("duration_us", 50)
        x, y = params.get("die_x", 0.0), params.get("die_y", 0.0)
        if safety == SafetyLevel.CAGE:
            log.info(f"[CAGE] Cell {cell_id}: Laser simulation — {power_mw}mW @ {wavelength}nm, pos ({x},{y})")
            return f"SIMULATED: Laser fault at die coordinates ({x:.2f}, {y:.2f}) — latch-up risk: LOW"
        log.warning(f"[LIVE] Cell {cell_id}: Laser ARMED — {power_mw}mW")
        return f"LIVE: Laser pulse {power_mw}mW @ ({x},{y}) — MANUAL POSITIONING REQUIRED"

class ThermalVector(AttackVector):
    name = "thermal"
    description = "Induce timing/voltage faults via temperature extremes."
    requires_extensions = ["sensor"]
    def execute(self, cell_id, target, params, extensions, safety):
        if self._check_safety(params, safety):
            return "SAFETY_ABORT"
        target_temp = params.get("target_temp", 85)
        ramp_rate = params.get("ramp_rate", 5)
        hold_time = params.get("hold_time", 30)
        if safety == SafetyLevel.CAGE:
            log.info(f"[CAGE] Cell {cell_id}: Thermal simulation — {target_temp}C for {hold_time}s")
            drift_ppm = (target_temp - 25) * 20
            return f"SIMULATED: Thermal stress at {target_temp}C — clock drift ~{drift_ppm}ppm"
        log.warning(f"[LIVE] Cell {cell_id}: Thermal system active — target {target_temp}C")
        return f"LIVE: Thermal ramp to {target_temp}C @ {ramp_rate}C/s — MONITOR MANUALLY"

class VoltageGlitchVector(AttackVector):
    name = "voltage_glitch"
    description = "Induce faults via precisely timed power supply transients."
    requires_extensions = ["gpio_extension", "pwm_servo"]
    def execute(self, cell_id, target, params, extensions, safety):
        if self._check_safety(params, safety):
            return "SAFETY_ABORT"
        v_nominal = params.get("v_nominal", 1.2)
        v_glitch = params.get("v_glitch", 0.8)
        glitch_width_ns = params.get("glitch_width_ns", 100)
        trigger_delay = params.get("trigger_delay_us", 100)
        if safety == SafetyLevel.CAGE:
            log.info(f"[CAGE] Cell {cell_id}: Voltage glitch simulation — {v_glitch}V for {glitch_width_ns}ns")
            depth = (v_nominal - v_glitch) / v_nominal
            fault_prob = min(0.8, depth * 2)
            return f"SIMULATED: Glitch depth {depth:.1%} — fault probability {fault_prob:.1%}"
        log.warning(f"[LIVE] Cell {cell_id}: Voltage glitch armed — {v_glitch}V / {glitch_width_ns}ns")
        return f"LIVE: Glitch profile loaded — EXECUTE ON CONFIRMED TARGET POWER RAIL"

class VectorRegistry:
    def __init__(self):
        self._vectors: Dict[str, AttackVector] = {}
        self._register_all()
    def _register_all(self):
        for cls in [RowhammerVector, EMFIVector, LaserVector, ThermalVector, VoltageGlitchVector]:
            inst = cls()
            self._vectors[inst.name] = inst
    def get(self, name: str) -> Optional[AttackVector]:
        return self._vectors.get(name)
    def list_vectors(self) -> Dict[str, str]:
        return {k: v.description for k, v in self._vectors.items()}
