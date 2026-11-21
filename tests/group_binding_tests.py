# PRIVATE BUILD — NOT FOR DISTRIBUTION
"""P-11 N02: every person a create request's text adds needs a declared 21+ record.

Codex's review of PR #23 and the reviewer's audit at 367e4c39 found that a second person added in the singular
passed with one declared record. These cases now refuse with one record and pass with two.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))

import safety  # noqa: E402

ONE = [{"age": 29}]
TWO = [{"age": 29}, {"age": 34}]
ADDED = ("a woman and a tall man on a sofa", "a woman with her husband", "a couple dancing",
         "a woman kissing a man", "a woman, a man", "twins",
         # A "date" or a "model" is a second person outside the two idioms (reviewer, PR #45 at e943ab2b).
         "a woman with her date", "a woman and her date at dinner", "a woman kissing her date",
         "a woman and a model", "a woman and a fashion model",
         # The idioms never hide a second person.
         "a woman on a date with her boyfriend", "a woman and a model pose for a photo",
         "a woman, a model pose by the pool", "a woman with a fashion model posing",
         # Any other clause break keeps a model who poses a person, not a look.
         "a woman reads; a model poses behind her", "a woman. a model shot a photo of her",
         "a woman while a model poses", "a woman in a dress a model poses behind",
         # Reviewer, PR #45 at 3def7ed and 8ac19ad: a model who poses or is photographed is a person, and so is a
         # double date.
         "a woman watches as a model poses", "a woman sits while a model poses",
         "a woman on a date. A model poses beside her", "a woman kissing a model shot from above",
         "a woman hugging a model photo shoot", "a woman next to a model shot for a magazine",
         "a woman beside a fashion model photo", "a woman on a double date", "a model poses beside a woman",
         "a fashion model poses next to her boyfriend")
SINGLE = ("a woman in a red dress, the woman smiles", "a woman on a beach at sunset",
          "a portrait of a woman, natural skin", "a woman on a date", "a fashion model pose, a woman in linen",
          "a woman on a first date", "a woman in a fashion model pose", "a woman striking a model pose",
          "a woman holding a model pose", "a woman on a blind date", "a woman on a date, the woman smiles")


def unit(check):
    print("\n[N02] Every added person needs a declared record")
    for text in ADDED:
        check(f"one record refuses: {text}", not safety.check_group_prompt(text, ONE)[0])
        check(f"two records clear: {text}", safety.check_group_prompt(text, TWO)[0])
    for text in SINGLE:
        check(f"one person stays fine: {text}", safety.check_group_prompt(text, ONE)[0])
    check("the old refusals still refuse", not safety.check_group_prompt("a woman and another woman", ONE)[0]
          and not safety.check_group_prompt("both women", ONE)[0] and not safety.check_group_prompt("a group of women", ONE)[0])
    ok, msg = safety.check_group_prompt("a woman and a tall man on a sofa", ONE)
    check("the refusal says every person needs a record", not ok and "declared record" in msg, msg)
    check("a record under 21 is still refused", not safety.check_group_prompt("a woman", [{"age": 20}])[0])


if __name__ == "__main__":
    failed = []

    def _check(name, cond, extra=""):
        print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  {extra}"))
        if not cond:
            failed.append(name)
    unit(_check)
    sys.exit(1 if failed else 0)
