# Using Regista for real

Regista is not tied to its simulator. Anything that can send HTTP can feed it, and anything that can poll JSON or
receive a webhook can use its output. This guide covers the three integrations a broadcaster, club media team or
streaming platform needs on day one.

```
your data provider ──POST /api/feed──▶ Regista ──WebSocket──▶ fan app / web overlay
                                          ├──GET /api/onair──▶ vMix · CasparCG · OBS (your own title templates)
                                          ├──webhook──────────▶ Slack · Microsoft Teams · Discord
                                          └──/mcp────────────▶ GitHub Copilot · Foundry agents · any MCP client
```

## 1. Push a live feed

1. **Start the match.** Send the line-ups once as a `MatchInfo` (schema: `GET /api/schema/match`). `roster` fixes the
   order of player positions in every tracking frame; if you omit it, Regista uses home players then away players.
   ```bash
   curl -X POST $REGISTA/api/feed/start -H 'Content-Type: application/json' -d @match.json
   ```
2. **Stream data** in any batch size (we recommend every 250–500 ms):
   ```json
   {"frames": [{"t": 612.4, "b": [61.2, 30.5, 0.0], "p": [[12.1, 33.0], [40.2, 8.1], null]}],
    "events": [{"id": "e01234", "match_id": "...", "seq": 1234, "t": 611.8, "period": 1, "minute": 10, "second": 11,
                "clock": "11'", "type": "pass", "team": "NOR", "player": "NOR-10", "x": 48.0, "y": 30.2,
                "end_x": 70.4, "end_y": 12.0, "outcome": "complete", "receiver": "NOR-07", "under_pressure": false,
                "qualifiers": {"ball_speed_kmh": 61.0}}]}
   ```
   - Frames: 5 Hz, metres on a 105 × 68 pitch, home team attacking towards x = 105, one position per roster entry
     (`null` while a player is off the pitch).
   - Events: send each event once it is complete (schema: `GET /api/schema/event`). Re-sending is safe, because
     ingestion ignores frames it already has and event ids it has seen.
   - The response says what Regista made of it: `{"clock": "11'", "score": {...}, "new_moments": ["GOAL ..."]}`.
3. **Finish** with `POST /api/feed/stop`, which returns the service to the demo replay.

A complete reference provider ships with the repo: `regista publish --url $REGISTA --speed 4` streams a match exactly
this way. Use it to test your own deployment, or as the template for an adapter from your data vendor's format.

## 2. Drive your own graphics (vMix, CasparCG, OBS)

`GET /api/onair` returns what a viewer with a given profile would see right now, already personalised and verified:

```
/api/onair?mode=analyst&lang=en
/api/onair?mode=casual&lang=ar&team=CAL            # Arabic, partisan for Port Calder
/api/onair?mode=player_cam&lang=es&player=NOR-10   # one player's story
```

- `flat` is a single row: `home`, `away`, `home_score`, `away_score`, `clock`, `home_win_pct`, `draw_pct`, `away_win_pct`,
  `lower_title`, `lower_body`, `lower_explainer`, `card_title`, `card_body`, `side_title`, `side_body` and `ticker`.
  - In **vMix**, add a *Data Source* → JSON, point it at the URL, refresh every 1 s, and bind these fields to a GT title.
  - In **CasparCG**, have an HTML template poll the URL.
- `on_air` is the full list, with slot, kind, priority, evidence ids and whether the copy was verified.
- Each graphic stays in the response for a minimum number of seconds, so a 1–2 s polling interval never misses one.
- **OBS** users can skip all of this: add a *Browser Source* pointing at `/#/overlay?mode=casual&lang=en`
  (transparent background, 1920 × 1080).

## 3. Webhooks for media teams and fan communities

Set an incoming-webhook URL and Regista posts every goal, red card, tactical shift, half time and full time. The copy
is verified and grounded, and comes with evidence ids.

| Variable | Default | Meaning |
|---|---|---|
| `REGISTA_WEBHOOK_URL` | (off) | Slack, Teams or Discord incoming webhook; every post carries `text` and `content` |
| `REGISTA_WEBHOOK_LANG` | `en` | `en`, `es`, `fr`, `ar`, `pt` |
| `REGISTA_WEBHOOK_PERSONA` | `casual` | `casual`, `analyst`, `new_fan` |
| `REGISTA_WEBHOOK_KINDS` | `goal,red_card,press_shift,half_time,full_time` | which moments to post |

Delivery is retried once and never blocks the broadcast; `GET /api/health` reports sent and failed counts.

## 4. Run it safely in public

| Variable | Effect |
|---|---|
| `REGISTA_ADMIN_TOKEN` | Playback control, chaos and the live-feed API require the header `X-Regista-Token` (WebSocket: a `token` field). Viewers can still personalise and ask questions. |
| `REGISTA_ASK_PER_MINUTE` | Pundit questions per viewer per minute (default 8); extra questions get a polite "try again" in the viewer's language. |
| `REGISTA_AUTOPLAY=1` | The demo match plays on boot, loops 45 s after full time, and resumes if it has been left paused for 5 minutes. |
| (always on) | Chaos fault injection switches itself off after 90 s. |

Everything above runs with or without a language model. Without one, every graphic, webhook and answer still goes
out, built from the same verified facts.
