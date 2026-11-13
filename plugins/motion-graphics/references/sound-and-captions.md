# Sound and captions

The film must work muted. Sound then makes it feel finished.

## Get the timing map first

```bash
python scripts/mg.py cues film cues.json
```

```json
{"duration": 25.9, "fps": 30, "cues": [
  {"t": 0,    "type": "scene", "id": "s1-title", "dur": 4.4, "transition": "cut"},
  {"t": 0.3,  "type": "anim",  "scene": "s1-title", "anim": "pop", "cue": "", "text": "Ship faster with Orbit"},
  {"t": 5.25, "type": "anim",  "scene": "s2-bullets", "anim": "pop", "cue": "tick", "text": "01 One command to deploy"}
]}
```

Add `data-cue="whoosh"` to any element to label it. Every sound and caption is placed from these times, so a change to the film is followed by re-running `cues`.

## Voiceover

1. Write the script from the storyboard: about 2.5 words per second (150 words a minute). 30 s ≈ 70–75 words.
2. Get the final recording **before** locking scene lengths. The user records it or generates it with a service of their choice — that is their decision and their account.
3. Measure each line: `ffprobe -v error -show_entries format=duration -of csv=p=0 line.wav`, or one file with silences: `ffmpeg -i vo.wav -af silencedetect=n=-35dB:d=0.35 -f null -`.
4. Set each scene's `data-dur` to its line length plus 0.3–0.5 s, and start the on-screen words 0.1–0.2 s **before** the voice says them.

## Music

- Use only music the user owns or has licensed; note the source and licence in the delivery message.
- Pick by tempo: 90–110 BPM calm, 110–130 confident, 130+ energetic. Cut scenes on the beat: a beat lasts `60 / BPM` seconds (120 BPM → 0.5 s), so make scene lengths multiples of it.
- Under voice, music sits about 15–20 dB below the speech. Alone, it can be full.

```bash
python scripts/mg.py render film final.mp4 --audio music.mp3 --audio-volume 0.8   # trimmed to the film, faded out
```

## Sound effects

Less is more: mark transitions, the hero entrance and the final action. Not every bullet.

| Motion | Sound |
|---|---|
| scene transition, slide, push | short whoosh, starting just before the move |
| `pop`, `slam`, landing | soft click or thud exactly on the landing |
| `count`, typing | light ticks that stop when the number lands |
| logo or end card | one warm tone |

Build the mix with ffmpeg from the cue times (milliseconds in `adelay`), then mux without re-encoding video:

```bash
ffmpeg -i music.mp3 -i whoosh.wav -i click.wav -filter_complex \
"[0:a]volume=0.5[m];[1:a]adelay=3900|3900,volume=0.7[a1];[2:a]adelay=5250|5250,volume=0.6[a2];\
[m][a1][a2]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.89[mix]" \
-map "[mix]" -t 25.9 mix.wav
ffmpeg -i final-silent.mp4 -i mix.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest final.mp4
```

No sound files to hand? Make simple placeholders with ffmpeg and say plainly that they are placeholders:

```bash
ffmpeg -f lavfi -i "sine=frequency=880:duration=0.06" -af "afade=t=out:st=0.01:d=0.05" click.wav
ffmpeg -f lavfi -i "anoisesrc=color=pink:duration=0.4" -af "highpass=f=600,afade=t=in:d=0.15,afade=t=out:st=0.2:d=0.2,volume=0.5" whoosh.wav
```

## Loudness

Normalise the final mix for online platforms (about −14 LUFS, peaks under −1 dBTP):

```bash
ffmpeg -i final.mp4 -af loudnorm=I=-14:TP=-1.5:LRA=11 -c:v copy -c:a aac -b:a 192k final-loud.mp4
```

`mg.py check` warns about clipping and near-silence. It cannot tell whether the mix sounds good — say what was measured and what was not listened to.

## Captions

Give speech captions always; many people watch muted.

**Burned in, styled like the film** — add them as scenes or elements: one short line (≤ 7 words on vertical, ≤ 12 on wide) per phrase, `data-anim="fade"` at the phrase start from `cues`/the transcript, in the lower third but above the bottom 20% on 9:16.

**Sidecar file** — write `captions.srt` from the transcript times:

```
1
00:00:00,300 --> 00:00:02,900
Ship faster with Orbit.
```

Attach it without re-encoding (`-c copy -c:s mov_text`) or burn it in:

```bash
ffmpeg -i final.mp4 -i captions.srt -c copy -c:s mov_text final-cc.mp4
ffmpeg -i final.mp4 -vf "subtitles=captions.srt:force_style='FontSize=22,Outline=2'" -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a copy final-burned.mp4
```

Caption rules: 1–2 lines, on screen at least 1 s, never over other text, punctuation as spoken.
