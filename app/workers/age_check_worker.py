"""Easy Studio automatic age check worker.

Runs inside ComfyUI's own Python (which already has torch, transformers and
kornia). Reads one JSON request per line on stdin: {"path": "..."} and writes
one JSON answer per line on stdout:

  {"status": "ok"|"flag"|"unchecked", "faces": n, "p_under21": 0.0-1.0, "reason": "..."}

Models (both local, both permissive licences):
  * Face finder: kornia's YuNet FaceDetector (Apache-2.0).
  * Age model:   prithivMLmods/Age-Classification-SigLIP2 (Apache-2.0),
                 classes Child 0-12 / Teenager 13-20 / Adult 21-44 / 45-64 / 65+.

A picture is FLAGGED when any face scores P(child)+P(teen) >= threshold.
If no face is found (back views, many anime styles) the answer is "unchecked";
the app shows that honestly instead of pretending the picture passed.
"""
import json
import os
import sys


def main():
    model_dir = sys.argv[1]
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
    import torch
    from PIL import Image
    import numpy as np
    from transformers import AutoImageProcessor, SiglipForImageClassification
    from kornia.contrib import FaceDetector, FaceDetectorResult

    torch.set_grad_enabled(False)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    proc = AutoImageProcessor.from_pretrained(model_dir)
    model = SiglipForImageClassification.from_pretrained(model_dir).to(dev).eval()
    labels = model.config.id2label
    minor_ids = [int(k) for k, v in labels.items() if v.lower().startswith(("child", "teen"))]
    det = FaceDetector(confidence_threshold=0.6).to(dev)
    print(json.dumps({"ready": True, "device": dev}), flush=True)

    for line in sys.stdin:
        try:
            req = json.loads(line)
            img = Image.open(req["path"]).convert("RGB")
            orig_w, orig_h = img.size
            img.thumbnail((1280, 1280))
            scale_x = orig_w / float(img.size[0] or 1)
            scale_y = orig_h / float(img.size[1] or 1)
            arr = np.array(img)
            t = torch.from_numpy(arr).permute(2, 0, 1).float()[None].to(dev)
            faces = [FaceDetectorResult(o) for o in det(t)[0]]
            faces = [f for f in faces if float(f.score) >= 0.6]
            crops = []
            boxes = []
            H, W = arr.shape[:2]
            for f in faces[:8]:
                x1, y1 = [float(v) for v in f.top_left.tolist()]
                x2, y2 = [float(v) for v in f.bottom_right.tolist()]
                w, h = x2 - x1, y2 - y1
                if w < 24 or h < 24:
                    continue
                pad = 0.35
                box = (max(0, int(x1 - w * pad)), max(0, int(y1 - h * pad)),
                       min(W, int(x2 + w * pad)), min(H, int(y2 + h * pad)))
                crops.append(img.crop(box))
                boxes.append([int(box[0] * scale_x), int(box[1] * scale_y),
                              int(box[2] * scale_x), int(box[3] * scale_y)])
            if not crops:
                print(json.dumps({"status": "unchecked", "faces": 0, "p_under21": None,
                                  "reason": "No clear face found, so the age check could not run."}), flush=True)
                continue
            inp = proc(images=crops, return_tensors="pt").to(dev)
            probs = torch.softmax(model(**inp).logits.float(), dim=-1).cpu()
            p = float(max(sum(float(row[i]) for i in minor_ids) for row in probs))
            status = "flag" if p >= threshold else "ok"
            print(json.dumps({"status": status, "faces": len(crops), "boxes": boxes, "p_under21": round(p, 3),
                              "reason": "A face may look under 21." if status == "flag" else ""}), flush=True)
        except Exception as e:  # never crash the worker on one bad file
            print(json.dumps({"status": "error", "faces": 0, "p_under21": None,
                              "reason": "Age check error: %s" % str(e)[:200]}), flush=True)


if __name__ == "__main__":
    main()
