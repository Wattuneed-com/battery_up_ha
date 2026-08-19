# Battery UP for Home Assistant

Cloud-polling integration for the **Wattuneed Battery UP** box: brings your
battery's live data (SOC, power, voltage, current, temperature, BMS flags)
into Home Assistant, so any HA automation can react to it — the classic use
case being a *solar router*: switch a water heater or a charger through any
HA-controllable plug/contactor based on the battery's state.

**Read-only for now.** Control of the box's own relays is a later phase,
gated on a command-acknowledgement path server-side.

## Installation (HACS custom repository)

1. HACS → Integrations → ⋮ → *Custom repositories* → add this repository
   URL, category *Integration*.
2. Install **Battery UP**, restart Home Assistant.
3. Settings → Devices & services → *Add integration* → **Battery UP**.
4. Sign in with your Battery UP account (the same as the app/site).

Home Assistant exchanges your password for a **revocable access token** and
stores only the token — never the password. You can see and revoke the
token ("Home Assistant (…)") from your Battery UP account's integration
tokens; revoking it makes HA ask to re-link.

One HA *device* is created per registered battery box, named as in the app.

## Entities

Enabled by default:

| Entity | Notes |
|---|---|
| State of charge | % — reports **unknown** instead of implausible values (see below); raw value in the `raw_soc` attribute |
| Battery power | W, derived v × i — **positive = charging, negative = discharging** |
| Voltage / Current / Cell temperature | pack-level values |
| Charge allowed / Discharge allowed | the BMS's own permissions — "the battery refuses to charge" signal |
| Problem | ON when any protection/alarm flag is raised |
| BMS communication | connectivity of the box↔battery link |

Disabled by default (enable per entity if wanted): State of health, BMS
charge/discharge limits, module count, and the 14 individual
protection/alarm flags (diagnostic category).

## Data honesty — read this before automating

- The box publishes every **15 s**; the integration polls every **30 s**.
  Reaction time for an automation is up to ~1 minute. This is load
  steering, not fine-grained surplus modulation.
- Entities go **unavailable** when the newest reading is older than
  **2 minutes** — an automation acting on stale battery data is worse than
  one that pauses. Build automations that handle `unavailable`.
- Some devices interleave invalid frames (SOC 0 while charging, or
  voltage/current/temperature all exactly 0). The integration reports
  **unknown** rather than a plausible-looking zero. Automations should
  treat `unknown` as "hold", not as 0.
- There is no energy (kWh) counter in the data, and no per-cell detail —
  pack-level only.

## Requirements

- A Battery UP account with at least one registered battery box
  (Pylontech-connected). Solar trackers and energy-meter devices are
  ignored by this integration.
- Home Assistant 2025.1 or newer.
