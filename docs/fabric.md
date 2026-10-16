# Microsoft Fabric Real-Time Intelligence: post-match analytics on the same feed

With `REGISTA_BUS=eventhubs`, every feed event is published to the `match-events` hub. The Bicep template creates a
dedicated `fabric-rti` consumer group so Fabric can read the stream without disturbing other consumers.

## Wire it up (about 5 minutes)
1. In Fabric, create an **Eventstream**, add source **Azure Event Hubs**, pick the namespace from the
   `EVENTHUB_NAMESPACE` azd output, hub `match-events`, consumer group `fabric-rti`, format JSON.
2. Add destination **Eventhouse** → new KQL database `regista`, table `MatchEvents`.
3. Each row is one `MatchEvent` (`backend/regista/schema/events.py`): `id, match_id, t, period, minute, clock, type,
   team, player, x, y, end_x, end_y, outcome, receiver, under_pressure, qualifiers`.

## Queries

```kusto
// Passing network edges for a team (who finds whom)
MatchEvents
| where type == "pass" and outcome == "complete" and team == "NOR"
| summarize passes = count() by player, receiver
| top 20 by passes

// Pressing intensity per 5 minutes (pressures in the opponent half)
MatchEvents
| where type == "pressure"
| extend att_x = iff(team == "NOR", todouble(x), 105.0 - todouble(x))
| where att_x > 52.5
| summarize pressures = count() by team, bin(minute, 5)
| render timechart

// Shot map with speeds
MatchEvents
| where type == "shot"
| project clock, team, player, x, y, outcome, speed_kmh = todouble(qualifiers.shot_speed_kmh)
```

The live pipeline stays the source of truth for on-air graphics; Fabric adds season-scale analytics, dashboards and
archival on top of the same stream.
