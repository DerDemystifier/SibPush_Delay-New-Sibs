from __future__ import annotations

import json
from importlib import import_module

from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED

from ..addon_utils import patched_addon_state
from ..card_utils import assert_card_queues, set_review_card_state
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state


def test_on_config_save_unsuspends_addon_cards_for_newly_ignored_deck() -> None:
    """
    Scenario: Case when a deck that already has add-on-suspended cards becomes ignored.

    The config save hook should undo the add-on's suspension work for that deck instead of simply
    leaving the cards suspended and excluding the deck from future processing.
    """

    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)

        note, cards = add_note_with_siblings(col, model, deck_id, "Ignored deck cleanup note")
        set_review_card_state(col, cards[0], ivl=10)

        print(
            "Before processing, the note has an immature review sibling, so all new siblings should be suspended by the add-on."
        )
        print_collection_state(col, "Before processing (will become ignored later)")

        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            parser_module = import_module(f"{addon.__name__}.sibpush.config.parser")
            active_rule = {
                "did": str(deck_id),
                "name": "Ignored deck cleanup note",
                "ignored": False,
                "interval": 21,
            }
            patched_addon.config_settings["custom_deck_rules"] = [active_rule]
            patched_addon.custom_deck_rules_by_did.clear()
            patched_addon.custom_deck_rules_by_did[str(deck_id)] = active_rule
            patched_addon.ignored_deck_ids[:] = []

            patched_addon.process_all_notes(col)

            print(
                "After processing, the add-on has suspended the new siblings and tagged the note as managed."
            )
            print_collection_state(col, "After processing (suspended by add-on)")

            assert_card_queues(
                col, cards, [QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED]
            )
            assert col.get_note(note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)

            ignored_rule = {
                "did": str(deck_id),
                "name": "Ignored deck cleanup note",
                "ignored": True,
                "interval": 21,
            }
            config_text = json.dumps(
                {
                    "debug": False,
                    "default_interval": 21,
                    "custom_deck_rules": [ignored_rule],
                    "tag_rules": {},
                }
            )

            parser_module.on_config_save(config_text, addon.__name__)

        print(
            "After the deck becomes ignored, the add-on should undo its own suspension work and restore the new cards."
        )
        print_collection_state(col, "After config save (newly ignored deck unsuspended)")

        assert_card_queues(col, cards, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert col.get_note(note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_on_config_save_unsuspends_addon_cards_for_newly_ignored_deck()
