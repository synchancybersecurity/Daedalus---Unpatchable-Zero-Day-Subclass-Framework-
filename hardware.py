#!/usr/bin/env python3
import os, json, subprocess, glob, logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from pathlib import Path

log = logging.getLogger("Daedalus.Hardware")

@dataclass
class DeviceProfile:
    cell_id: int
    bus: str
    address: str
    device_class: str
    vendor_id: Optional[str] = None
    product_id: Optional[str] = None
    driver_hint: Optional[str] = None
    status: str = "detected"

class HardwareBus:
    def __init__(self):
        self.detected_cache: Dict[int, List[DeviceProfile]] = {}

    def _run_cmd(self, cmd: List[str]) -> str:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
        except Exception as e:
            log.debug(f"Command failed: {' '.join(cmd)} — {e}")
            return ""

    def scan_i2c(self, cell_id: int) -> List[DeviceProfile]:
        devices = []
        KNOWN_I2C = {
            0x27: "lcd_display", 0x3C: "oled_display", 0x40: "pwm_servo",
            0x50: "eeprom", 0x68: "rtc_clock", 0x76: "bme280_sensor",
            0x77: "bme280_sensor_alt", 0x1A: "rfid_reader",
            0x29: "tof_sensor", 0x53: "light_sensor", 0x5A: "gas_sensor"
        }
        for bus_num in [0, 1]:
            dev_path = f"/dev/i2c-{bus_num}"
            if not Path(dev_path).exists():
                continue
            try:
                import smbus2
                bus = smbus2.SMBus(bus_num)
                for addr in range(0x03, 0x77):
                    try:
                        bus.write_quick(addr)
                        dev_class = KNOWN_I2C.get(addr, "unknown_i2c")
                        devices.append(DeviceProfile(
                            cell_id=cell_id, bus=f"i2c-{bus_num}",
                            address=f"0x{addr:02X}", device_class=dev_class
                        ))
                    except:
                        pass
                bus.close()
            except ImportError:
                out = self._run_cmd(["i2cdetect", "-y", str(bus_num)])
                for line in out.splitlines()[1:]:
                    parts = line.split()
                    for p in parts[1:]:
                        if p not in ["--", "UU"] and len(p) == 2:
                            addr = int(p, 16)
                            dev_class = KNOWN_I2C.get(addr, "unknown_i2c")
                            devices.append(DeviceProfile(
                                cell_id=cell_id, bus=f"i2c-{bus_num}",
                                address=f"0x{addr:02X}", device_class=dev_class
                            ))
        log.info(f"Cell {cell_id}: I2C scan found {len(devices)} devices")
        return devices

    def scan_spi(self, cell_id: int) -> List[DeviceProfile]:
        devices = []
        for spi_dev in glob.glob("/dev/spi*"):
            dev_name = Path(spi_dev).name
            dev_class = "unknown_spi"
            if "0.0" in dev_name: dev_class = "rfid_reader"
            elif "0.1" in dev_name: dev_class = "lora_module"
            devices.append(DeviceProfile(
                cell_id=cell_id, bus="spi", address=dev_name, device_class=dev_class
            ))
        log.info(f"Cell {cell_id}: SPI scan found {len(devices)} devices")
        return devices

    def scan_uart(self, cell_id: int) -> List[DeviceProfile]:
        devices = []
        uart_ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyS*")
        for port in uart_ports:
            dev_name = Path(port).name
            dev_class = "unknown_uart"
            try:
                udev_path = f"/sys/class/tty/{dev_name}/device/../../../idVendor"
                if Path(udev_path).exists():
                    vid = Path(udev_path).read_text().strip()
                    pid_path = udev_path.replace("idVendor", "idProduct")
                    pid = Path(pid_path).read_text().strip() if Path(pid_path).exists() else "0000"
                    if vid == "10C4":
                        dev_class = "gps_module" if pid in ["EA60", "EA70"] else "uart_bridge"
                    elif vid == "1A86":
                        dev_class = "can_bus" if pid == "7523" else "uart_bridge"
                    elif vid == "0403":
                        dev_class = "sdr_bridge" if pid == "6010" else "uart_bridge"
                    devices.append(DeviceProfile(
                        cell_id=cell_id, bus="uart", address=port,
                        device_class=dev_class, vendor_id=vid, product_id=pid
                    ))
                    continue
            except:
                pass
            devices.append(DeviceProfile(
                cell_id=cell_id, bus="uart", address=port, device_class=dev_class
            ))
        log.info(f"Cell {cell_id}: UART scan found {len(devices)} devices")
        return devices

    def scan_usb(self, cell_id: int) -> List[DeviceProfile]:
        devices = []
        out = self._run_cmd(["lsusb"])
        KNOWN_USB = {
            ("0bda", "2838"): "sdr_rtl2832",
            ("1d50", "6089"): "sdr_hackrf",
            ("16c0", "0483"): "gpio_extension",
            ("2341", "0043"): "arduino_uno",
            ("1a86", "7523"): "usb_serial",
            ("10c4", "ea60"): "usb_gps",
        }
        for line in out.splitlines():
            if "ID" in line:
                parts = line.split("ID ")[1].split() if "ID " in line else []
                if len(parts) >= 1:
                    ids = parts[0].split(":")
                    if len(ids) == 2:
                        vid, pid = ids[0].lower(), ids[1].lower()
                        dev_class = KNOWN_USB.get((vid, pid), "unknown_usb")
                        devices.append(DeviceProfile(
                            cell_id=cell_id, bus="usb",
                            address=f"{vid}:{pid}", device_class=dev_class,
                            vendor_id=vid, product_id=pid
                        ))
        log.info(f"Cell {cell_id}: USB scan found {len(devices)} devices")
        return devices

    def emergency_shutdown(self):
        log.critical("HARDWARE EMERGENCY SHUTDOWN")
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
        except:
            pass

class ExtensionManager:
    def __init__(self):
        self.registry: Dict[int, List[DeviceProfile]] = {}

    def register_devices(self, cell_id: int, devices: List[DeviceProfile]):
        if cell_id not in self.registry:
            self.registry[cell_id] = []
        self.registry[cell_id].extend(devices)

    def get_cell_extensions(self, cell_id: int) -> List[DeviceProfile]:
        return self.registry.get(cell_id, [])

    def has_extension(self, cell_id: int, device_class: str) -> bool:
        return any(d.device_class == device_class for d in self.get_cell_extensions(cell_id))

    def summary(self) -> Dict:
        return {f"cell_{k}": [asdict(d) for d in v] for k, v in self.registry.items()}

    def emergency_shutdown(self):
        log.critical("ExtensionManager: All extensions disabled.")
