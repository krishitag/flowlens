# Live Demo Script (Review 2) and Backup Video

Use this for rehearsal, the live demo, and recording the backup video (M3.9). The run is `scenarios/demo.json`, about 105 seconds.

## Before you start (5 minutes ahead)

1. Pull `main`. Check that the real models are in `models/` and `data/processed/test.parquet` exists.
2. Open two terminals **in the repo root** with the virtual environment active.
3. Terminal 1: `streamlit run dashboard/app.py`, then open http://localhost:8501 in full-screen (F11) and zoom the browser to 110–125% so the room can read it.
4. Check the **Results** tab shows real numbers. If not, run the report scripts and click **Reload reports**.
5. Do one dry run, `python -m pipeline.run --scenario scenarios/demo.json --speed 0`, to confirm everything loads. The next run resets the database.
6. Close notifications, Slack and email.

## Run of show

Start the pipeline in Terminal 2 at **T = 0**:

```bash
python -m pipeline.run --scenario scenarios/demo.json --speed 1
```

| Sim time | What's on screen | What to say |
|---|---|---|
| 0–30 s | Green **NORMAL** · ~40 flows/s · coverage ~10% | "Normal traffic. Tier 1 watches the flow rate. Tier 2 scores only a 10% sample, so we aren't paying to score and explain everything." |
| ~30–32 s | Flow rate jumps to ~400/s · z-score crosses the red line | "A DoS attack starts. The z-score jumps above 3…" |
| ~32 s | State flips to red **ELEVATED** · shaded band appears · coverage 100% | "…three windows in a row, so we go ELEVATED. Now every flow is scored by LightGBM *and* the Isolation Forest." |
| 32–50 s | Alerts table fills · Alerts-by-type shows DoS | **Toggle Pause live updates.** Scroll to *Why was it flagged?*, enter a DoS alert ID, then walk through the SHAP bars and the sentences. "This is the reason, in plain language, computed in under a millisecond." **Untoggle Pause.** |
| ~50–55 s | Traffic drops · state returns to **NORMAL** after 5 calm windows | "Attack over. Five calm windows and we drop back to sampling." |
| 70–85 s | PortScan · ELEVATED again (~72–89 s) | "A port scan. It's a different attack, and the explanation features are different too." Show one PortScan alert, ideally one tagged **low confidence ⚠**, and explain what that tag means. |
| ~90–105 s | NORMAL · status shows **RUN COMPLETE** at the end | Point at the sidebar: "Detection and explanation latency per flagged flow, and the share of work done per state. That's the saving from tiering." |
| After | **Results** tab | Headline: TreeSHAP vs Kernel SHAP speed-up. Then the per-class F1, the leave-one-attack-out table, and pipeline latency. |
| After | **How it works** tab | Only if asked. Also covers the known limitation (slow scan). |

**If something breaks live:** switch to the backup video. Don't debug in front of reviewers.

## Recording the backup video (M3.9)

- **Windows:** press `Win + Alt + R` (Xbox Game Bar) to start and stop recording the browser window. Files go to `Videos\Captures`.
- **macOS:** press `Cmd + Shift + 5` and choose *Record Selected Portion*.
- **Any OS:** OBS Studio, with a *Window Capture* of the browser.

Record the whole run-of-show above in one take (about 3 minutes including the Results tab), with voice-over if possible. Then trim it, export as MP4 (1080p), upload it to the team Drive, and put the link in `docs/STATUS.md` (M3.9 row).
