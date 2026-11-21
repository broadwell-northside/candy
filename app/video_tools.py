"""ffmpeg helpers: grab the last frame of a clip and stitch clips together."""
import json
import os
import shutil
import subprocess
import tempfile


def ffmpeg_bin():
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg is not installed or not on PATH. Run the install script again.")
    return exe


def ffprobe_bin():
    exe = shutil.which("ffprobe")
    if not exe:
        raise RuntimeError("ffprobe is not installed or not on PATH (it comes with ffmpeg).")
    return exe


def _run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + " ".join(cmd) + "\n" + p.stderr[-2000:])
    return p.stdout


def probe(path):
    """Return dict(width, height, fps, frames, duration)."""
    out = _run([ffprobe_bin(), "-v", "error", "-select_streams", "v:0", "-count_frames",
                "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames:format=duration",
                "-of", "json", path])
    d = json.loads(out)
    s = d["streams"][0]
    num, den = (s.get("r_frame_rate") or "16/1").split("/")
    fps = float(num) / float(den or 1)
    return {"width": int(s["width"]), "height": int(s["height"]), "fps": fps,
            "frames": int(s.get("nb_read_frames") or 0),
            "duration": float(d.get("format", {}).get("duration") or 0)}


def last_frame(video_path, out_png):
    """Save the very last frame of a video as a PNG (lossless)."""
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    if os.path.exists(out_png):
        os.remove(out_png)
    # Seek close to the end, decode the remaining frames and keep overwriting one file:
    # the file left on disk is the final frame.
    _run([ffmpeg_bin(), "-y", "-v", "error", "-sseof", "-1", "-i", video_path,
          "-update", "1", "-frames:v", "1000", out_png])
    if not os.path.exists(out_png):  # very short clips: fall back to decoding from the start
        _run([ffmpeg_bin(), "-y", "-v", "error", "-i", video_path, "-update", "1", out_png])
    return out_png


def stitch(clips, out_path, drop_first_frame_of_followups=True, fps=None, crf=16):
    """Join clips end-to-end into one MP4.

    When a clip was generated FROM the last frame of the previous clip, its first frame is a
    copy of that frame, so we drop it to avoid a visible 'stutter' at every join.
    All clips are scaled to the first clip's size and frame rate.
    """
    if not clips:
        raise ValueError("No clips to stitch")
    info = probe(clips[0])
    w, h = info["width"], info["height"]
    fps = fps or info["fps"] or 16
    parts = []
    for i, c in enumerate(clips):
        chain = f"[{i}:v]"
        if i > 0 and drop_first_frame_of_followups:
            chain += "trim=start_frame=1,"
        chain += (f"setpts=PTS-STARTPTS,scale={w}:{h}:flags=lanczos,setsar=1,fps={fps},"
                  f"format=yuv420p[v{i}]")
        parts.append(chain)
    concat_in = "".join(f"[v{i}]" for i in range(len(clips)))
    filt = ";".join(parts) + f";{concat_in}concat=n={len(clips)}:v=1:a=0[out]"
    cmd = [ffmpeg_bin(), "-y", "-v", "error"]
    for c in clips:
        cmd += ["-i", c]
    tmp_out = out_path + ".tmp.mp4"
    cmd += ["-filter_complex", filt, "-map", "[out]", "-c:v", "libx264", "-preset", "medium",
            "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", tmp_out]
    _run(cmd)
    os.replace(tmp_out, out_path)
    return out_path


def make_test_video(out_path, width=320, height=192, frames=33, fps=16, color_shift=0):
    """Create a small synthetic test clip (used by the self-test and the mock server)."""
    _run([ffmpeg_bin(), "-y", "-v", "error", "-f", "lavfi",
          "-i", f"testsrc2=size={width}x{height}:rate={fps}",
          "-vf", f"hue=h={color_shift}", "-frames:v", str(frames),
          "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path])
    return out_path


def has_encoder(name):
    """True if this ffmpeg can encode with e.g. 'libtheora' (Godot needs Ogg Theora .ogv videos)."""
    try:
        out = subprocess.run([ffmpeg_bin(), "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=30).stdout
        return any(line.split()[1:2] == [name] for line in out.splitlines() if len(line.split()) > 1)
    except Exception:
        return False
