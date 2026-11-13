---
name: video-making
description: Use this skill whenever the user wants to create, edit, or convert a video file (.mp4, .mov, .webm, .gif) — slideshows from images, clips with text or captions, trimming, merging, adding music or voiceover, resizing for social media, or rendering animations to video.
license: MIT. Complete terms in LICENSE.txt
---

# Video Making Skill

> For animated motion graphics made from code — kinetic type, explainers, launch videos, animated charts, lower thirds with a choice of visual styles — use the `motion-graphics` skill. This skill is for footage, photos, audio and ffmpeg editing.

Build videos programmatically with **ffmpeg** (core engine) and **Python** (Pillow for frames/graphics, MoviePy for higher-level editing). Always plan first, build second, verify last.

---

## 1. Plan before building

Settle these before writing any command:

| Decision | Default | Notes |
|---|---|---|
| Aspect ratio | 16:9 (1920x1080) | 9:16 (1080x1920) for Reels/Shorts/TikTok, 1:1 (1080x1080) for feeds |
| Frame rate | 30 fps | 24 for cinematic, 60 for screen recordings/gameplay |
| Length | As asked | Reels/Shorts ≤ 60–90 s |
| Format | MP4 (H.264 + AAC) | Plays everywhere; WebM only if asked; GIF only for short loops |
| Audio | Optional | Music, voiceover, or silent |

Write a short shot list: each scene → duration, visual, text, transition, audio.

---

## 2. Check the toolchain

```bash
which ffmpeg ffprobe || (apt-get update && apt-get install -y ffmpeg)
python3 -c "import PIL, moviepy" 2>/dev/null || pip install pillow moviepy --break-system-packages
fc-list | head   # see which fonts are available for text
```

---

## 3. Standard encoding settings

Use these for every final render unless the user asks otherwise:

```bash
-c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p -movflags +faststart \
-c:a aac -b:a 192k
```

- `-pix_fmt yuv420p` — required for playback on phones, QuickTime, and browsers.
- `-movflags +faststart` — lets the video start playing before it fully downloads.
- `-crf 18` = near-lossless (bigger file), `-crf 28` = smaller file, lower quality.
- `-preset veryfast` keeps renders quick; use `slow` only when best quality is requested.
- Width and height must be **even numbers** for H.264.

---

## 3b. Render fast — the person is waiting

A full render is the slowest step, so plan for **one** full render per request:

1. **Look before you encode.** Pull or draw a few frames at final size — the busiest moments, the first and last frame — and check framing, text size and colours. For photo videos: `scripts/slideshow.py OUT.mp4 photos… --preview` makes a contact sheet in a second.
2. **Scenes, not one giant graph.** Encode each scene to its own file with identical size, fps and encoder settings, join them with the concat demuxer and `-c copy`, and add sound last with `-c:v copy`. Fixing one scene later means re-encoding only that scene.
3. **Transitions live inside a scene file** (fade in/out at its edges). Cross-fading two *finished* files forces a second full encode.
4. **Hold a still cheaply.** Decode the picture once and repeat it with the `loop` filter, rather than `-loop 1` (which decodes the image again for every frame):
   `ffmpeg -framerate 30 -i still.png -vf "format=yuv420p,loop=-1:1,trim=duration=4,setpts=PTS-STARTPTS" -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p still.mp4`
5. **Never leave a half file under the real name.** Write to `name.part.mp4` and rename only when ffmpeg exits 0 — an interrupted render can still play, just cut short.
6. Draw frames at the output size and 30 fps unless asked otherwise. When capturing a web page frame by frame, save JPEG (quality ~90), not PNG — far faster to write and read.

Measured on 10 photos → 1080p: the old single `-loop 1` + xfade graph took 13.2 s; `slideshow.py --crossfade` takes 6.4 s, the scene-file path 8.9 s including music.

Changing a finished video:
| Change | Do |
|---|---|
| One scene's content | re-render that scene file, re-join with `-c copy` |
| New music / trim the ending | `-c:v copy` (new music: `-map 0:v -map 1:a`) |
| Burn in captions, make a smaller copy | re-encode the finished file once |
| Something that changes on every frame | a full render is unavoidable |

## 4. Recipes

### 4.0 Photo slideshow in one command

```bash
python3 scripts/slideshow.py out.mp4 photos/*.jpg --seconds 3 --fade 0.5 --music song.mp3      # fast, fade via black
python3 scripts/slideshow.py out.mp4 photos/*.jpg --crossfade                                 # true crossfades
python3 scripts/slideshow.py out.mp4 photos/*.jpg --zoom --size 1080x1920                      # Ken Burns, vertical
```

### 4.1 Slideshow from images (with fade transitions), by hand

```bash
# Each image shown for 3 s, 0.5 s crossfade, scaled/padded to 1080p
# each still is decoded once and repeated with the loop filter (2x faster than -loop 1)
F="scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,loop=-1:1,trim=duration=3,setpts=PTS-STARTPTS,fps=30"
ffmpeg -framerate 30 -i img1.jpg -framerate 30 -i img2.jpg -framerate 30 -i img3.jpg \
-filter_complex "\
[0]$F[a];[1]$F[b];[2]$F[c];\
[a][b]xfade=transition=fade:duration=0.5:offset=2.5[ab];\
[ab][c]xfade=transition=fade:duration=0.5:offset=5[out]" \
-map "[out]" -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p -movflags +faststart slideshow.mp4
```

Offset for clip *n* = (sum of previous durations) − (n × fade duration).

### 4.2 Ken Burns (slow zoom) on a still image

```bash
# d = number of output frames (150 at 30 fps = 5 s); no -loop needed, zoompan generates the frames
ffmpeg -i photo.jpg -vf "scale=3840:-2,zoompan=z='min(zoom+0.0008,1.2)':d=150:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30" \
-c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p zoom.mp4
```

Upscaling to 3840 first avoids the jittery motion zoompan shows on small images.

### 4.3 Text overlay / title card

```bash
ffmpeg -i input.mp4 -vf "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:\
text='My Title':fontsize=72:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=20:\
x=(w-text_w)/2:y=h-150:enable='between(t,0,4)'" \
-c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p -c:a copy titled.mp4
```

For text with apostrophes, emoji, or non-Latin scripts (Hindi, etc.), render the text to a PNG with Pillow using a font that supports the script, then overlay it:

```bash
ffmpeg -i input.mp4 -i title.png -filter_complex "overlay=(W-w)/2:H-h-100:enable='between(t,0,4)'" ...
```

### 4.4 Solid-colour title card from nothing

```bash
ffmpeg -f lavfi -i color=c=0x111827:s=1920x1080:d=3:r=30 \
-vf "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='Chapter 1':fontsize=96:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2" \
-c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p card.mp4
```

### 4.5 Trim a clip

```bash
# Accurate trim (re-encodes): from 00:00:05 for 10 seconds
ffmpeg -ss 00:00:05 -i input.mp4 -t 10 -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p -c:a aac trimmed.mp4
# Fast trim (no re-encode, cuts on nearest keyframe)
ffmpeg -ss 00:00:05 -i input.mp4 -t 10 -c copy trimmed_fast.mp4
```

### 4.6 Join clips

Same codec/resolution/fps → concat demuxer (no re-encode):

```bash
printf "file 'a.mp4'\nfile 'b.mp4'\nfile 'c.mp4'\n" > list.txt
ffmpeg -f concat -safe 0 -i list.txt -c copy joined.mp4
```

Different sources → normalize first (scale, fps, audio rate) or use the concat filter:

```bash
ffmpeg -i a.mp4 -i b.mp4 -filter_complex \
"[0:v]scale=1920:1080,setsar=1,fps=30[v0];[1:v]scale=1920:1080,setsar=1,fps=30[v1];\
[v0][0:a][v1][1:a]concat=n=2:v=1:a=1[v][a]" \
-map "[v]" -map "[a]" -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p -c:a aac joined.mp4
```

(If a clip has no audio track, add silence: `-f lavfi -i anullsrc=r=48000:cl=stereo` and use `-shortest`.)

### 4.7 Add background music

```bash
# Music under video, fade out at the end, stop when video ends
# st = video length minus fade length (here a 30 s video, 3 s fade) — get the length with ffprobe
ffmpeg -i video.mp4 -i music.mp3 -filter_complex \
"[1:a]volume=0.3,afade=t=out:st=27:d=3[m]" \
-map 0:v -map "[m]" -c:v copy -c:a aac -shortest with_music.mp4

# Mix music under existing speech
ffmpeg -i video.mp4 -i music.mp3 -filter_complex \
"[1:a]volume=0.15[m];[0:a][m]amix=inputs=2:duration=first[a]" \
-map 0:v -map "[a]" -c:v copy -c:a aac mixed.mp4
```

### 4.8 Subtitles / captions

Write an `.srt` file:

```
1
00:00:00,000 --> 00:00:03,000
Welcome to the video.

2
00:00:03,000 --> 00:00:06,500
Here's what we'll cover.
```

Burn them in:

```bash
ffmpeg -i input.mp4 -vf "subtitles=subs.srt:force_style='FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=1,Outline=2'" \
-c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p -c:a copy captioned.mp4
```

### 4.9 Resize for social media (vertical 9:16)

```bash
# Blurred background fill instead of black bars
ffmpeg -i landscape.mp4 -filter_complex \
"[0]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20[bg];\
[0]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2" \
-c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p -c:a copy vertical.mp4
```

### 4.10 Speed up / slow down

```bash
# 2x speed (video + audio)
ffmpeg -i in.mp4 -filter_complex "[0:v]setpts=0.5*PTS[v];[0:a]atempo=2.0[a]" -map "[v]" -map "[a]" fast.mp4
```

### 4.11 Video to GIF (high quality)

```bash
ffmpeg -i in.mp4 -vf "fps=15,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" -loop 0 out.gif
```

### 4.12 Render frames from code (animations, charts, motion graphics)

When ffmpeg filters aren't enough, draw each frame with Python and stitch them:

```python
from PIL import Image, ImageDraw, ImageFont
import os, subprocess

W, H, FPS, SECONDS = 1920, 1080, 30, 4
os.makedirs("frames", exist_ok=True)
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 96)

for i in range(FPS * SECONDS):
    t = i / (FPS * SECONDS)
    img = Image.new("RGB", (W, H), (17, 24, 39))
    d = ImageDraw.Draw(img)
    x = int(-600 + t * (W + 600))          # text slides across
    d.text((x, H // 2 - 48), "Hello!", font=font, fill=(255, 255, 255))
    img.save(f"frames/{i:05d}.png")

subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", "frames/%05d.png",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", "animation.mp4"], check=True)
```

Use easing (e.g. `t*t*(3-2*t)`) for smoother motion.

### 4.13 MoviePy (quick high-level edits)

```python
from moviepy import VideoFileClip, TextClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip

clip1 = VideoFileClip("a.mp4").subclipped(0, 5)
clip2 = VideoFileClip("b.mp4").subclipped(2, 8)
video = concatenate_videoclips([clip1, clip2], method="compose")
music = AudioFileClip("music.mp3")
video = video.with_audio(music.subclipped(0, min(video.duration, music.duration)))   # music may be shorter
video.write_videofile("out.mp4", fps=30, codec="libx264", audio_codec="aac", preset="veryfast")
```

(MoviePy 2.x API shown; 1.x uses `subclip`/`set_audio`. Check with `pip show moviepy`.)

---

## 5. Verify before delivering

Never hand over a video without checking it:

```bash
# Duration, resolution, codecs, fps
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate -of default=nw=1 out.mp4

# Pull still frames at key moments and look at them
ffmpeg -ss 1 -i out.mp4 -frames:v 1 check_1s.png
ffmpeg -i out.mp4 -vf "fps=1/3,scale=480:-1,tile=4x2" -frames:v 1 contact_sheet.png
```

Checklist:
- [ ] Duration matches the plan
- [ ] Resolution and aspect ratio are correct; no unwanted black bars or stretching
- [ ] Text is readable, inside safe margins (keep ~5% from edges; for 9:16, avoid the bottom ~15% where app UI sits)
- [ ] Transitions land where intended
- [ ] Audio present (if expected), not clipping, ends cleanly
- [ ] Plays on phones: H.264, `yuv420p`, even dimensions

---

## 6. Common pitfalls

| Problem | Fix |
|---|---|
| Video won't play on iPhone/QuickTime | Add `-pix_fmt yuv420p` |
| "width not divisible by 2" | Use `scale=1280:-2` instead of `-1` |
| Black frames at start after `-c copy` trim | Re-encode, or put `-ss` before `-i` and re-encode |
| Audio out of sync after concat | Normalize fps and audio sample rate (`-ar 48000`) before joining |
| xfade error "inputs differ" | All inputs need same size, fps, `setsar=1`, and pixel format |
| drawtext breaks on `'` or `:` | Escape them, or use `textfile=` / Pillow-rendered PNG overlay |
| Non-English text shows boxes | Use a font that supports the script (e.g. Noto Sans Devanagari) |
| Huge file size | Raise CRF (26–28), lower fps or resolution |
| Render is too slow | Use `-preset veryfast` or `ultrafast`; reduce resolution while drafting |

---

## 7. Workflow summary

1. **Plan** — aspect ratio, fps, length, shot list, audio.
2. **Gather assets** — images, clips, music, fonts; check them with `ffprobe`.
3. **Draft fast** — low resolution / `ultrafast` preset to check timing.
4. **Build final** — standard encoding settings (section 3).
5. **Verify** — ffprobe + contact sheet + checklist (section 5).
6. **Deliver** — send the final file with a one-line summary (duration, resolution, what's in it).
