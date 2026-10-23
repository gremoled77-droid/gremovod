"""Local, synthetic-only media worker: mock PNG/WAV/MP4, join, N34 and repair.

Requires installed ffmpeg/ffprobe. Never calls paid APIs; never touches existing
Studio media or character canon. Run with an EMPTY output directory only.
"""
from __future__ import annotations
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


class MockMediaError(RuntimeError):
    pass


def require_tools():
    for binary in ("ffmpeg", "ffprobe"):
        if not shutil.which(binary):
            raise MockMediaError(f"{binary} unavailable. Install locally before mock test.")


def invoke(args):
    # ffprobe/ffmpeg печатают UTF-8 (в т.ч. кириллические пути); кодировка Windows по умолчанию их не читает.
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90, check=False)
    if p.returncode != 0:
        raise MockMediaError(f"Media command failed: {args[0]}: {p.stderr[-1400:]}")
    return p.stdout


def checksum(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def probe(path:Path):
    raw=invoke(["ffprobe","-v","error","-show_format","-show_streams",
                "-of","json",str(path)])
    return json.loads(raw)


def n34_technical_qc(path:Path, *, expected_duration_seconds=9.0, min_width=320, required_audio=True):
    if not path.is_file() or path.stat().st_size==0:
        return {"status":"BLOCKED_NO_MEDIA"}
    try:
        metadata=probe(path)
    except MockMediaError:
        return {"status":"FAIL_UNREADABLE_MEDIA"}
    streams=metadata.get("streams",[])
    video=[s for s in streams if s.get("codec_type")=="video"]
    audio=[s for s in streams if s.get("codec_type")=="audio"]
    if not video or (required_audio and not audio):
        return {"status":"FAIL_STREAMS_MISSING"}
    duration=float(metadata.get("format",{}).get("duration",0))
    if abs(duration-expected_duration_seconds)>0.6 or video[0].get("width",0)<min_width:
        return {"status":"FAIL_DURATION_OR_RESOLUTION","duration_seconds":duration}
    try:
        invoke(["ffmpeg","-v","error","-i",str(path),"-f","null","-"])
    except MockMediaError:
        return {"status":"FAIL_DECODE"}
    return {"status":"PASS_TECHNICAL_ONLY","duration_seconds":duration,
            "fps":video[0].get("r_frame_rate"),"width":video[0].get("width"),
            "height":video[0].get("height"),"audio_streams":len(audio),
            "sha256":checksum(path),"claims_creative_pass":False}


def ensure_empty_directory(dest:Path):
    if dest.exists() and any(dest.iterdir()):
        raise MockMediaError("Output folder is not empty; refusing to overwrite user media")
    dest.mkdir(parents=True,exist_ok=True)


def make_video(path:Path, *, color:str, frequency:int):
    invoke(["ffmpeg","-hide_banner","-loglevel","error","-y",
            "-f","lavfi","-i",f"color=c={color}:s=320x180:r=15:d=3",
            "-f","lavfi","-i",f"sine=frequency={frequency}:sample_rate=24000:duration=3",
            "-shortest","-c:v","mpeg4","-q:v","8","-c:a","aac","-b:a","64k",str(path)])


def make_png(path:Path,color:str):
    invoke(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","lavfi",
            "-i",f"color=c={color}:s=320x180:d=0.1","-frames:v","1",str(path)])


def make_voice(path:Path,frequency:int):
    invoke(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","lavfi",
            "-i",f"sine=frequency={frequency}:sample_rate=24000:duration=1.5",
            "-c:a","pcm_s16le",str(path)])


def concat(clips:list[Path],output:Path):
    # Closed synthetic inputs only. No shell interpolation, no untrusted paths.
    script=output.parent/("concat_"+output.stem+".txt")
    lines=[]
    for c in clips:
        if c.parent!=output.parent or not c.is_file():
            raise MockMediaError("clips must exist in dedicated output directory")
        lines.append("file '"+c.name.replace("'","\\'")+"'\n")
    script.write_text("".join(lines),encoding="utf-8")
    invoke(["ffmpeg","-hide_banner","-loglevel","error","-y",
            "-f","concat","-safe","0","-i",str(script),"-c","copy",str(output)])


def run_mock_pilot(dest:Path):
    require_tools()
    ensure_empty_directory(dest)
    colors=["navy","teal","purple"]
    originals=[]
    for i,color in enumerate(colors,1):
        shot=dest/f"shot_{i:02d}.mp4"
        make_video(shot,color=color,frequency=220+55*i)
        make_png(dest/f"mock_image_{i:02d}.png",color)
        originals.append(shot)
    for name,frequency in (("voice",330),("sfx",490),("music",660)):
        make_voice(dest/f"mock_{name}.wav",frequency)
    before={c.name:checksum(c) for c in originals}
    raw_master=dest/"master_scene_before_repair.mp4"
    concat(originals,raw_master)
    raw_qc=n34_technical_qc(raw_master)
    if raw_qc["status"]!="PASS_TECHNICAL_ONLY":
        raise MockMediaError("Initial mock technical QC failed: "+str(raw_qc))
    repair=dest/"shot_02_repaired.mp4"
    make_video(repair,color="orange",frequency=770)
    updated=[originals[0],repair,originals[2]]
    final_master=dest/"master_scene.mp4"
    concat(updated,final_master)
    final_qc=n34_technical_qc(final_master)
    if final_qc["status"]!="PASS_TECHNICAL_ONLY":
        raise MockMediaError("Repaired mock technical QC failed: "+str(final_qc))
    after={c.name:checksum(c) for c in originals}
    unchanged=before["shot_01.mp4"]==after["shot_01.mp4"] and before["shot_03.mp4"]==after["shot_03.mp4"]
    if not unchanged or checksum(repair)==before["shot_02.mp4"]:
        raise MockMediaError("Shot 2 repair unexpectedly changed unaffected files")
    return {"MOCK_MODE":True,"production_ready":False,"n34_technical_only":final_qc,
            "original_qc":raw_qc,"repaired_slot_id":"shot_02",
            "unaffected_shots_reused":unchanged,"new_shot_checksum":checksum(repair),
            "previous_shot_checksum":before["shot_02.mp4"],"media_count":3,
            "sound_stems":3,"total_duration_seconds":final_qc["duration_seconds"],
            "N35_stt_status":"BLOCKED_SYNTHETIC_AUDIO_NO_SPEECH",
            "A6_A7_A8":"BLOCKED_NOT_REAL_USER_MEDIA",
            "owner_ready":False,"paid_provider_calls":0}


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--dest",required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(run_mock_pilot(args.dest),ensure_ascii=False,indent=2))
