"""N35 local evidence pack from a REAL accessible test MP4, no AI or cloud API.

Frame sampling and FFmpeg metadata are *not* proof of acting, speech, lip-sync,
character identity, or edit quality. STT and professional critique stay BLOCKED.
"""
import hashlib
import json
from pathlib import Path

from tools.mock_media_pilot import checksum, invoke, n34_technical_qc


def json_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
                                   separators=(",", ":")).encode()).hexdigest()


def extract_n35_evidence(master:Path, *, folder:Path, script_text:str,
                         canon_revision:str, required_modalities=("VIDEO","AUDIO")):
    if folder.exists() and any(folder.iterdir()):
        raise ValueError("evidence output directory must be empty")
    folder.mkdir(parents=True,exist_ok=True)
    qc=n34_technical_qc(master)
    if qc["status"]!="PASS_TECHNICAL_ONLY":
        return {"status":"BLOCKED_N34_NOT_VALID","qc":qc}
    audio=folder/"audio_mono_16k.wav"
    invoke(["ffmpeg","-hide_banner","-loglevel","error","-y",
            "-i",str(master),"-vn","-ac","1","-ar","16000",
            "-c:a","pcm_s16le",str(audio)])
    frames=[]
    for timestamp in (1,4,7):
        image=folder/f"frame_{timestamp:02d}s.png"
        invoke(["ffmpeg","-hide_banner","-loglevel","error","-y",
                "-ss",str(timestamp),"-i",str(master),"-frames:v","1",
                "-update","1",str(image)])
        frames.append({"time_ms":timestamp*1000,"sha256":checksum(image),
                       "file_ref":image.name,"sampling_mode":"FIXED_TIME_NOT_CUT_DETECTION"})
    master_checksum=qc["sha256"]
    snapshot={
        "master_checksum":master_checksum,
        "script_hash":json_hash(script_text),
        "canon_revision":canon_revision,
        "evidence_audio_hash":checksum(audio),
        "frames":[{"time_ms":f["time_ms"],"sha256":f["sha256"]} for f in frames],
        "required_modalities":sorted(required_modalities),
        "source_kind":"SYNTHETIC_MOCK_MP4"
    }
    return {"status":"EVIDENCE_EXTRACTED_NOT_FULL_QA",
            "review_round_id":"MOCK-N35-R1",
            "snapshot_hash":json_hash(snapshot),
            "master_checksum":master_checksum,
            "audio":{"sha256":checksum(audio),"file_ref":audio.name,"stt":"BLOCKED_STT_NOT_AVAILABLE"},
            "frames":frames,
            "actual_audio_extracted":True,
            "actual_frames_extracted":True,
            "motion_evaluated":False,
            "lip_sync_evaluated":False,
            "cut_detection_evaluated":False,
            "real_approved_canon_verified":False,
            "role_reviews":[{"role":x,"verdict":"BLOCKED","reason":"NO_REAL_USER_MEDIA_OR_APPROVED_CAPABILITY"} for x in ("A6","A7","A8")],
            "final_release_approved":False}
