# Bear Basin measurement and calibration checklist

Status: planning only, 2026-10-06. Companion to [the realistic physics and wear plan](realistic-physics-and-wear-plan.md). No measurements or testing requested now.

## First collection: useful without specialist equipment

Record what is known; leave uncertain values unknown rather than guessing them precisely.

| Item | What to record | Why |
| --- | --- | --- |
| Identity | Product/model, hardware revisions, substitutions, assembly date, prior repairs. | Match the manual and physical set. |
| Condition | Existing cracks, movement, corrosion, visible gaps, damaged hardware; dated photos. | Start from actual condition rather than “new.” |
| Swing geometry | Rope length, spacing, seat mass if available, hanger positions. | Pendulum dynamics and beam load locations. |
| Load-bearing wood | Actual beam/leg/brace cross-sections and spans; species/grade if documented; grain/knots near connections. | Stiffness, load sharing and local behavior. |
| Connections | Close views identifying screws versus bolts/nuts, washer stacks, visible engagement and bracket fit. | Hardware-specific laws and correct geometry. |
| Ground | Surface, slope, ground contact, stake/anchor configuration, known settlement. | Support compliance and frame reaction. |
| Use | Typical session length/frequency, swing amplitude/cadence, one or several users. | Convert active hours into actual load exposure. |
| Calendar exposure | Location/climate scenario, shade, rain exposure, storage and sealing history. | Moisture and ageing between sessions. |
| Maintenance | Dates and actual actions; manufacturer instructions/torque specifications if available. | Condition resets and history. |

The initial simulation holds child mass at 80 lb. No need to infer child motion from identity, age, or photographs.

If ordinary-use motion observations are appropriate, short supervised video with a visible scale and fixed camera can help measure swing period, peak angle, beam deflection and frame sway. Two views help separate perspective from actual motion. Do not increase swing intensity or postpone maintenance to obtain data. Keep child footage private; extracting anonymous motion measurements is preferable to uploading video.

## Measurements that need care or expertise

- Wood moisture at representative locations, with instrument/species correction and uncertainty recorded.
- Connection displacement under known loads; optical readings or gauges need resolution checks.
- Existing visible witness marks for rotation, where appropriate. Rotation does not directly measure clamp force.
- Preload using a suitable calibrated method. Breakaway torque is not a reliable substitute and can disturb the connection.
- Support stiffness/settlement characterized without unsafe loading or alteration of anchors.

Do not invent installation torque from a generic bolt chart or loosen installed hardware to characterize it. Follow the manufacturer’s assembly/maintenance guidance. Inspection observations can be useful even when preload remains unidentified.

## Controlled calibration: separate representative specimens

Use spare matching material and hardware in a properly designed bench fixture. Select specimens after load analysis identifies the important mechanisms. A qualified test operator should define loads, restraint and instrumentation.

For each connection family, record:

1. Species/grade, grain, moisture, geometry, hole preparation and thread engagement.
2. Fastener type/material, washers, nut/locking feature, assembly procedure and initial condition.
3. Applied shear/axial force/moment, frequency and displacement history.
4. Slip/hysteresis, clamp relaxation, rotation/withdrawal, indentation and clearance over cycles.
5. Rest/moisture intervals and maintenance interventions.
6. Replicate specimens, measurement uncertainty and held-out validation specimens.

Cover the relevant range of loads and moisture. Increasing frequency/load is allowed only after establishing that it preserves the mechanism being extrapolated. Long-horizon predictions need evidence about cycle count and calendar exposure, not just a successful short static test.

Never use a child or an occupied playset as a fatigue-test actuator. Tests on sacrificial fixtures must not reduce the condition of the equipment children use.

## Minimum useful outcome when calibration is unavailable

A verified load-path model, connection demand ranges, sensitivity to unknown preload/support/moisture, and a prioritized list of measurements. Label individual loosening rates as unknown. This is a useful first analysis and a foundation for later calibration.

## Data record format

Each measurement should include: stable part/connection ID, quantity, value, units, method, timestamp, uncertainty, source/photo reference, and whether observed, documented or inferred. Keep raw observations separate from fitted parameters.

Store calibration and validation datasets separately. Retain scenario inputs, random seed and solver version with every analysis report. Do not publish personal measurement data automatically to the public GitHub repository.
