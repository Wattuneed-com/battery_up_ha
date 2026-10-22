# Battery UP for Home Assistant

Cloud-polling integration for the **Wattuneed Battery UP** box: brings your
battery's — and, since 0.3.0, your Deye or Sofar inverter's — live data (SOC, power, voltage, current, temperature, BMS flags)
into Home Assistant, so any HA automation can react to it — the classic use
case being a *solar router*: switch a water heater or a charger through any
HA-controllable plug/contactor based on the battery's state.

**Read-only for now.** Control of the box's own relays is a later phase,
gated on a command-acknowledgement path server-side.

## Installation (HACS custom repository)

1. HACS → Integrations → ⋮ → *Custom repositories* → add
   `https://github.com/Wattuneed-com/battery_up_ha`, category *Integration*.
   (Once the integration is accepted into the HACS default catalog, this
   step disappears — search "Battery UP" directly in HACS.)
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

## Inverters (0.3.0)

When your Battery UP box reads a **Deye** or **Sofar** hybrid inverter (by
cable or through the inverter's own Wi-Fi stick), the same device gets the
inverter's values:

| Entity | Notes |
|---|---|
| Battery state of charge / power / voltage / temperature | battery power **positive = discharging, negative = charging** |
| Solar power | total, plus one per string (disabled by default) |
| Grid power | **positive = importing, negative = exporting**; per phase disabled by default |
| Grid voltage L1 (L2, L3 on three-phase), grid frequency | |
| House consumption, backup output power | |
| Grid connected | OFF during a power cut while the backup output runs |
| Energy today / total | solar, house consumption, grid import, grid export, battery charge and discharge (kWh) |

Only the values your inverter gives are created (a single-phase inverter
has no L2/L3, a Deye has no lifetime battery counters — use the "today"
ones).

**Energy dashboard**: *Settings → Dashboards → Energy*: grid consumption =
*Grid import total*, return to grid = *Grid export total*, solar
production = *Solar energy total*, battery = *Battery charge today* /
*Battery discharge today* (Sofar: the *total* ones). The "today" counters
fall back to zero at midnight; Home Assistant counts that as a new cycle.

## Options

*Settings → Devices & services → Battery UP → Configure*: polling interval
(15–300 s, default 30) and the relay-control opt-in (advanced — the switches
stay unavailable until the cloud command feature is live and the box is in
MANUAL mode).

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
