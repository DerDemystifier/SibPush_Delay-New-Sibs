from __future__ import annotations

from importlib import import_module

from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED

from ..addon_utils import FakeAddonManager, patched_addon_state
from ..card_utils import assert_card_queues, set_review_card_state
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state


def test_update_custom_deck_rule_unsuspends_cards_when_deck_becomes_ignored() -> None:
    """
    Scenario: Case when a deck already has add-on-suspended cards and a UI-driven config save
    marks that deck as ignored.

    The helper should persist the new rule, refresh the runtime caches, and undo the addon-owned
    suspension work for the deck.
    """

    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        fake_manager = FakeAddonManager(
            {
                "default_interval": 21,
                "custom_deck_rules": [],
                "tag_rules": {},
                "debug": False,
            }
        )

        note, cards = add_note_with_siblings(col, model, deck_id, "Ignored deck cleanup note")
        set_review_card_state(col, cards[0], ivl=10)

        print(
            "Before processing, the note has an immature review sibling, so all new siblings should be suspended by the add-on."
        )
        print_collection_state(col, "Before processing (will become ignored later)")

        with patched_addon_state(col, addon_manager=fake_manager) as patched_addon:
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

            parser_module.update_custom_deck_rule(
                str(deck_id), "Ignored deck cleanup note", ignored=True, interval=21
            )

        print(
            "After the deck becomes ignored, the add-on should undo its own suspension work and restore the new cards."
        )
        print_collection_state(col, "After UI-driven config save (newly ignored deck unsuspended)")

        assert fake_manager.writes
        assert fake_manager.writes[-1]["custom_deck_rules"][0]["ignored"] is True
        assert_card_queues(col, cards, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert col.get_note(note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_update_custom_deck_rule_unsuspends_cards_when_deck_becomes_ignored()
