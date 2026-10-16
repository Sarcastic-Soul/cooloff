# Video storyboard (target 2:40, hard limit 3:00)

No music, no logos, no real people. Voice: text-to-speech narration (Kokoro, voice af_heart). Call voices: Amazon Polly.
Every scene is a recording of the real demo page or a slide made from numbers in `bench/results/summary.json`.

| Time | Scene | On screen | Narration idea |
| --- | --- | --- | --- |
| 0:00 to 0:20 | Hook | Named character, Margaret, 78, and what a scam call costs her | The call is the attack. Nobody else is on the line. |
| 0:20 to 0:25 | Title | Cooloff, with the two tags | So we built Cooloff. |
| 0:25 to 1:35 | Fake grandchild call | Demo page, live: transcript, four signal bars, gate goes red on two kinds of signal, payment held, balance unchanged, messages, family replies KEEP | Decider reads every sentence on the device. Bedrock only writes after the freeze. |
| 1:35 to 2:00 | Real pharmacy call | Demo page: gate stays green, bill is paid | It must not get in the way of a normal call. |
| 2:00 to 2:40 | Slides | How the pattern works, the numbers (caught 23/23, false freezes 5/23, 144 ms on GPU, 3.5 s on CPU), what we got wrong | Say the limits out loud. |
| 2:40 to 2:55 | Outro | Repo link, `rolling_risk_gate`, tags | Take the pattern and use it on your own agent. |

Rules for the cut: say "simulation" once in the narration and once on screen. Say plainly that the real bank alert gets
frozen by mistake and that CPU speed is slow. Never show anything that looks like a real bank's brand.
