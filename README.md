# D.Z.D.E

*Daedalus SubZD Engine 1.0**
*Cage Laboratory Hardware Testing Suite*
SynChanCyberSecurity LLC | Agent X Authorized



# Overview

Daedalus eliminates the "can we talk to this chip" R&D phase,
leaving only the "how do we make it fail" calibration phase.

| Feature | Description |
|---------|-------------|
| *8 Cell Grid** | Independent testing cells with per cell hardware isolation |
| *Auto Discovery* | I2C / SPI / UART / USB extension scanning |
| *Physical Kill Switch* | GPIO4 hardware abort human hand is the only fail safe |
| *Per Target Calibration* | Physical, hands on analog tuning per silicon |
| *$15K Budget Ceiling* | Commodity hardware only no custom ASICs |
| *5 Attack Vectors* | Rowhammer, EMFI, Laser, Thermal, Voltage Glitch |

---

# Safety Levels

*[CAGE]* SIMULATION ONLY, No physical signals sent to targets
*[LIVE]* HARDWARE ACTIVE, Kill switch ARMED on GPIO4 required
*[WAR]* AUTONOMOUS MODE, Human hand on kill switch at ALL times

> *The human kill switch is the sole fail safe.*


# Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Launch framework (CAGE mode by default)
python3 daedalus.py
```

CLI commands:
```
daedalus> status          # Show all 8 cell states
daedalus> arm             # Arm physical kill switch
daedalus> scan 1          # Auto detect hardware on cell 1
daedalus> cal 1 MT41K256M16   # Calibrate for target chip
daedalus> exec 1 rowhammer MT41K256M16   # Execute vector
daedalus> report          # Generate JSON execution report
daedalus> abort           # EMERGENCY ABORT all cells
```

---

## Attack Vectors

| Vector | Target | Hardware | Safety Limit |
|--------|--------|----------|--------------|
| `rowhammer` | DRAM | SDR (optional) | 65,536 rows max |
| `emfi` | SoC logic | EM coil + driver | 1.0J pulse energy |
| `laser` | Die surface | 808nm diode + XY | 500mW power |
| `thermal` | Package | Peltier + sensors | +80C from ambient |
| `voltage_glitch` | Power rail | DAC + MOSFET | ±0.5V delta |

---

## Architecture

```
    Daedalus Core (daedalus.py)
             │
    ┌────┬────┬────┼────┬────┬────┐
    ▼    ▼    ▼    ▼    ▼    ▼    ▼
  Cell Cell Cell ... Cell Cell Cell
    1    2    3    6    7    8
    │    │    │    │    │    │
    └────┴────┴────┼────┴────┴────┘
                 ▼
      Hardware Bus Scanner
      I2C | SPI | UART | USB
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
 Extension    Attack      Calibration
 Manager     Vectors      Engine
```

---

## Hardware BOM

BUDGET: $4,853 / $15,000 (32% used)

| Category | Items | Cost |
|----------|-------|------|
| Controllers | 8x Raspberry Pi 5 8GB | $640 |
| RF/SDR | 4x RTL SDR + 2x HackRF | $380 |
| Comms | RFID, LoRa, GPS, CAN modules | $200 |
| Power | PSUs, relays, buck converters | $344 |
| Injection | EMFI coils, laser diodes, Peltier | $664 |
| Instruments | Logic analyzers, scopes, meters | $260 |
| Infrastructure | Enclosures, cables, storage | $1,365 |
| Contingency | Shipping, replacements, buffer | $500 |
| *TOTAL* | | *$4,853* |
| *REMAINING* | | *$10,147*l* |

Full BOM: `hardware/bom.json`


# Calibration Philosophy

> "The framework provides hardware interfaces and attack vectors, but analog tuning (laser positioning, thermal rates, EM pulse timing, DRAM row mapping, etc.) must be done manually per specific target silicon. This is normal in hardware security ops."

The calibration engine automates:
- Parameter sweep prompts
- Result logging
- Best parameter extraction
- Persistent calibration database (`calibration_db.json`)

*What YOU do physically:**l
- Position laser spot over die
- Adjust EM coil height and orientation
- Map DRAM row adjacencies
- Tune thermal ramp rates
- Time voltage glitch width/offset

---

# Legal Disclaimer

<details>
<summary><b>⚠️ CLICK TO EXPAND CRITICAL LEGAL NOTICE</b></summary>

### AUTHORIZED USE ONLY

This framework is intended *exclusively* for:
- Authorized red team operations with explicit written authorization
- Academic research in controlled laboratory settings
- Hardware security research on devices you *OWN* or have *explicit permission** to test
- Cage laboratory environments with proper containment

*YOU MAY NOT* use this framework to test, attack, or interrogate any system you do not own or have explicit written authorization to test.

### PHYSICAL SAFETY WARNING

This framework interfaces with *high voltage electronics, electromagnetic pulse generators, high powered lasers, and thermal manipulation systems*. Hazards include electrocution, permanent eye damage (Class 3B/4 laser), burns/fire, and component destruction.

*Operator Requirements:*
- Trained personnel ONLY
- ESD protection (wrist straps, grounded mats)
- Laser safety eyewear (808nm rated, OD 4+)
- Fire extinguisher within 3 meters
- Emergency stop armed before EVERY session
- Minimum two person rule for LIVE and WAR modes

# CFAA COMPLIANCE

Use may implicate the Computer Fraud and Abuse Act (18 U.S.C. 1030), DMCA (17 U.S.C. 1201), and analogous state laws. You represent that you have explicit written authorization for all testing.

# EXPORT CONTROL / ITAR

Certain components and findings may be subject to ITAR (22 CFR 120 130), EAR (15 CFR 730 774), or Wassenaar Arrangement controls. You are solely responsible for export compliance.

# NO WARRANTY

THIS SOFTWARE IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND. IN NO EVENT SHALL SYNCHANCYBERSECURITY LLC, AGENT X, OR CONTRIBUTORS BE LIABLE FOR PHYSICAL INJURY, PROPERTY DAMAGE, DATA LOSS, LEGAL PENALTIES, OR ECONOMIC LOSS.

# INDEMNIFICATION

By using Daedalus, you agree to indemnify and hold harmless SynChanCyberSecurity LLC from all claims a
from your use, misuse, or violation of law.

# ACKNOWLEDGMENT

*BY USING DAEDALUS, YOU ACKNOWLEDGE THAT YOU HAVE READ, UNDERSTOOD, AND AGREE TO BE BOUND BY THIS DISCLAIMER.**

</details>

# License

Apache 2.0 SynChanCyberSecurity LLC
ITAR controlled. Cage laboratory use only.

---

<div align="center">

**[GitHub](https://github.com/synchancybersecurity/Daedalus)** • **synchancybersecurity@gmail.com** • **Lead: Agent X**

```
  Cage Lab Authorized  |  Agent X  |  v1.0
```

</div>
