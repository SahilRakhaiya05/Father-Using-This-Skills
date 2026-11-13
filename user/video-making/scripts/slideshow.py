#!/usr/bin/env python3
"""Fast slideshow / photo video builder.

Each image becomes its own scene file (encoded once, identical settings), the scenes are
joined with the concat demuxer without re-encoding, and music is added last without
touching the video stream. Changing one photo later = re-render one scene + re-join.

Usage:
  slideshow.py OUT.mp4 IMG [IMG ...] [--seconds 3] [--size 1920x1080] [--fps 30]
               [--fade 0.5] [--zoom] [--music FILE] [--crossfade] [--crf 20] [--preview]

  --fade S       fade through black at each scene edge (fast path, default 0.5; 0 = hard cuts)
  --crossfade    true crossfades between photos instead (one filter graph, slower)
  --zoom         slow Ken Burns push-in on every photo
  --music FILE   music under the whole video, trimmed and faded out at the end
  --preview      don't encode; write OUT_preview.png (first frame of each scene) to check framing
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ffmpeg failed:\n{' '.join(cmd)}\n{r.stderr[-1500:]}")


def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
                       capture_output=True, text=True)
    return float(json.loads(r.stdout)["format"]["duration"])


def fit_filter(w, h, zoom, seconds, fps):
    if zoom:
        frames = int(seconds * fps)
        # upscale first so the zoom moves smoothly, then push in 1.0 -> ~1.12
        return (f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
                f"zoompan=z='min(1+0.12*on/{frames},1.12)':d={frames}:x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}")
    return (f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setsar=1")


def main():
    a = sys.argv[1:]
    opts = {"--seconds": 3.0, "--size": "1920x1080", "--fps": 30, "--fade": 0.5, "--music": None, "--crf": 20}
    flags = {"--zoom": False, "--crossfade": False, "--preview": False}
    pos = []
    i = 0
    while i < len(a):
        if a[i] in opts:
            opts[a[i]] = a[i + 1]
            i += 2
        elif a[i] in flags:
            flags[a[i]] = True
            i += 1
        else:
            pos.append(a[i])
            i += 1
    if len(pos) < 2:
        sys.exit(__doc__)
    out, imgs = pos[0], pos[1:]
    secs, fps, fade, crf = float(opts["--seconds"]), int(opts["--fps"]), float(opts["--fade"]), str(opts["--crf"])
    w, h = (int(x) for x in opts["--size"].lower().split("x"))
    if w % 2 or h % 2:
        sys.exit("width and height must be even")
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", crf, "-pix_fmt", "yuv420p", "-r", str(fps)]

    if flags["--preview"]:
        from PIL import Image, ImageOps
        tw = 480
        th = int(tw * h / w)
        sheet = Image.new("RGB", (min(len(imgs), 4) * (tw + 8) + 8, ((len(imgs) + 3) // 4) * (th + 8) + 8), "white")
        for k, p in enumerate(imgs):
            im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
            im = ImageOps.pad(im, (tw, th), color="black") if not flags["--zoom"] else ImageOps.fit(im, (tw, th))
            sheet.paste(im, (8 + (k % 4) * (tw + 8), 8 + (k // 4) * (th + 8)))
        prev = os.path.splitext(out)[0] + "_preview.png"
        sheet.save(prev)
        print(f"preview -> {prev}")
        return

    work = tempfile.mkdtemp(prefix="slides_")
    try:
        video_only = os.path.join(work, "video.mp4")
        if flags["--crossfade"] and len(imgs) > 1:
            xf = max(fade, 0.3)
            inputs, chains = [], []
            for k, p in enumerate(imgs):
                inputs += ["-framerate", str(fps), "-i", p]
                chains.append(f"[{k}:v]{fit_filter(w, h, flags['--zoom'], secs, fps)},format=yuv420p,"
                              f"loop=-1:1,trim=duration={secs},setpts=PTS-STARTPTS,fps={fps}[s{k}]")
            last = "s0"
            for k in range(1, len(imgs)):
                off = k * (secs - xf)
                chains.append(f"[{last}][s{k}]xfade=transition=fade:duration={xf}:offset={off:.3f}[x{k}]")
                last = f"x{k}"
            run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(chains), "-map", f"[{last}]",
                 *enc, video_only])
        else:
            scenes = []
            for k, p in enumerate(imgs):
                vf = fit_filter(w, h, flags["--zoom"], secs, fps)
                if not flags["--zoom"]:
                    # decode the still once, then repeat that frame (much cheaper than -loop 1)
                    vf += f",format=yuv420p,loop=-1:1,trim=duration={secs},setpts=PTS-STARTPTS,fps={fps}"
                # (zoompan already emits exactly secs*fps frames at the target fps)
                if fade > 0:
                    vf += f",fade=t=in:st=0:d={fade},fade=t=out:st={secs - fade:.3f}:d={fade}"
                tmp = os.path.join(work, f"scene{k:03d}.part.mp4")
                final = os.path.join(work, f"scene{k:03d}.mp4")
                cmd = ["ffmpeg", "-y", "-v", "error", "-framerate", str(fps), "-i", p, "-vf", vf]
                if flags["--zoom"]:
                    cmd += ["-frames:v", str(int(secs * fps))]
                run(cmd + [*enc, "-f", "mp4", tmp])
                os.replace(tmp, final)          # only complete scenes get the real name
                scenes.append(final)
            lst = os.path.join(work, "list.txt")
            with open(lst, "w") as f:
                f.writelines(f"file '{s}'\n" for s in scenes)
            run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", video_only])

        part = out + ".part.mp4"
        if opts["--music"]:
            dur = probe_duration(video_only)
            af = f"afade=t=out:st={max(dur - 2, 0):.2f}:d=2"
            run(["ffmpeg", "-y", "-v", "error", "-i", video_only, "-i", opts["--music"], "-map", "0:v", "-map", "1:a",
                 "-c:v", "copy", "-af", af, "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                 "-f", "mp4", part])
        else:
            run(["ffmpeg", "-y", "-v", "error", "-i", video_only, "-c", "copy", "-movflags", "+faststart",
                 "-f", "mp4", part])
        os.replace(part, out)
        print(f"{out}: {len(imgs)} scenes, {probe_duration(out):.2f}s, {w}x{h}@{fps}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
