"""License cards for models we might evaluate. Not a permission to download or run them."""
import json
import os

_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_cards.json")


def load():
    with open(_FILE, encoding="utf-8") as f:
        return json.load(f)


def card(card_id):
    for row in load().get("cards") or []:
        if row.get("id") == card_id:
            return dict(row)
    return None


def noncommercial(card_id):
    row = card(card_id) or {}
    return row.get("commercial") == "no"
