"""Library items read by id go through one gate: 18+ items only in the 18+ section, and nothing the age check held or flagged.
The LoRA workshop's preset and face-check routes used to read the library directly."""
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "app"))


def unit(check):
    print("\n[gate] Library items read by id go through the shared gate")
    from library import AreaView, Library
    out = tempfile.mkdtemp(prefix="es_gate_")
    try:
        lib = Library(out)
        base = {"type": "image", "kind": "lora:benchmark", "role": "made", "age_check": "ok", "area": "default"}
        rows = {"fine": {}, "adult": {"area": "adult"}, "flag": {"age_flag": True}, "unchecked": {"age_check": "unchecked", "held": True},
                "appearance": {"appearance_check": {"status": "flag"}}, "unavailable": {"age_check": "blocked_age_check_unavailable", "held": True}}
        for name, extra in rows.items():
            lib._write(dict(base, id="it_" + name, **extra))
        default, adult = AreaView(lib, "default"), AreaView(lib, "adult")

        def refused(view, iid):
            try:
                view.checked(iid)
                return False
            except PermissionError:
                return True
        check("an ordinary item passes the gate in either section", default.checked("it_fine")["id"] == "it_fine" and adult.checked("it_fine")["id"] == "it_fine")
        check("an 18+ item is refused outside the 18+ section and allowed inside it", refused(default, "it_adult") and adult.checked("it_adult")["id"] == "it_adult")
        check("a flagged, held, unchecked or unavailable item is refused in both sections, 18+ included",
              all(refused(v, "it_" + n) for v in (default, adult) for n in ("flag", "unchecked", "appearance", "unavailable")))
        try:
            default.checked("it_missing")
            gone = False
        except KeyError:
            gone = True
        check("a missing item is still reported as missing", gone)
    finally:
        shutil.rmtree(out, ignore_errors=True)
    src = open(os.path.join(ROOT, "app", "routes_v3.py"), encoding="utf-8").read()
    for route, fn in (("/api/loras/workshop/preset", "workshop_preset"), ("/api/loras/workshop/face-check", "workshop_face_check")):
        m = re.search(r'@app\.post\("%s"\)\n    def %s\((.*?)\n(?=    @app\.|    def |\Z)' % (re.escape(route), fn), src, re.S)
        body = m.group(0) if m else ""
        check("%s reads its library items only through the gate, and knows the request's section" % route,
              bool(body) and "request: Request" in body and "_gated_item(request, body" in body and "S.LIB.get(" not in body and "LIB.get(" not in body, body[:200])
    gate = re.search(r"    def _gated_item\(.*?\n        return item\n", src, re.S)
    check("the route gate asks for the section the request may use, then the shared checked read",
          bool(gate) and "want_area(request, body.get(\"area\"))" in gate.group(0) and ".checked(" in gate.group(0) and "PermissionError" in gate.group(0))
    # The workshop routes that read or change a LoRA record: an 18+ LoRA answers as missing without the 18+ unlock.
    lo = re.search(r"    def _lora_or_404\(name, request\):.*?\n        return record\n", src, re.S)
    check("the LoRA record lookup answers 'Not found' for an 18+ LoRA unless the 18+ unlock is held, as lora_edit and lora_delete do",
          bool(lo) and 'record.get("area") == "adult"' in lo.group(0) and "not adult_unlocked(request)" in lo.group(0) and "S.err(\"Not found\", 404)" in lo.group(0))
    calls = re.findall(r"_lora_or_404\(.*", src)
    check("every caller passes the request to that lookup", len(calls) >= 7 and all(", request)" in c for c in calls), calls)
    for route, fn in (("get", "workshop_card"), ("post", "workshop_prompt"), ("post", "workshop_stack"), ("post", "workshop_preset"),
                      ("post", "workshop_face_check"), ("post", "workshop_accept")):
        m = re.search(r"    def %s\((.*?)\):" % fn, src)
        check("%s takes the request, so the lookup can ask for the unlock" % fn, bool(m) and "request: Request" in m.group(1), m.group(1) if m else "")
    up = re.search(r'    async def workshop_upload\(.*?\n(?=    @app\.)', src, re.S)
    ub = up.group(0) if up else ""
    check("the workshop upload asks for its section like the plain LoRA upload, and keeps an 18+ upload in the 18+ section",
          'area: str = Form("")' in ub and "want_area(request, area)" in ub and '{"area": "adult"} if a == "adult"' in ub)
    check("the workshop upload streams to disk and stops at the size cap instead of reading the whole file first",
          "await file.read(1 << 20)" in ub and "await file.read()" not in ub and "size > S.MAX_LORA_UPLOAD" in ub
          and ub.index("size > S.MAX_LORA_UPLOAD") < ub.index("handle.write(chunk)"))
    check("face-check returns the two picture links only through the gate, which needs the 18+ unlock for an 18+ request",
          "def adult_unlocked" in src and 'adult_unlocked(request) if area == "adult" else False' in src)
