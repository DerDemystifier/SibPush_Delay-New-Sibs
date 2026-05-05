from __future__ import annotations

from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED

from ..addon_utils import load_addon_module, patched_addon_state
from ..card_utils import assert_card_queues, set_review_card_state
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state


def test_tag_rule_takes_precedence_over_custom_deck_interval() -> None:
    """
    Scenario: Case when a note matches both a deck-specific interval and a tag-based interval rule.

    The addon should prefer the tag rule for the tagged note while still using the deck rule for the
    untagged control note, demonstrating that tag-based precedence wins over deck-only defaults.
    """
    with temporary_collection() as col:
        addon = load_addon_module()
        model = build_test_notetype(col)

        custom_deck_id = col.decks.id("Tagged Custom Deck")
        assert custom_deck_id is not None

        tagged_note, tagged_cards = add_note_with_siblings(
            col, model, custom_deck_id, "Tagged note"
        )
        control_note, control_cards = add_note_with_siblings(
            col, model, custom_deck_id, "Control note"
        )

        set_review_card_state(col, tagged_cards[0], ivl=20)
        set_review_card_state(col, control_cards[0], ivl=20)

        tagged_note.add_tag("easy_topic")
        col.update_note(tagged_note)

        print(
            "Before processing the tagged note, both notes share the same deck interval, but only one note has the tag that should override it."
        )
        print_collection_state(col, "Before processing (tag rule vs custom deck interval)")

        with patched_addon_state(col) as patched_addon:
            custom_rule = {
                "did": str(custom_deck_id),
                "name": "Tagged Custom Deck",
                "ignored": False,
                "interval": 18,
            }
            patched_addon.config_settings["custom_deck_rules"] = [custom_rule]
            patched_addon.config_settings["tag_rules"] = {"easy_topic": {"interval": 25}}
            patched_addon.custom_deck_rules_by_did.clear()
            patched_addon.custom_deck_rules_by_did[str(custom_deck_id)] = custom_rule
            patched_addon.ignored_deck_ids[:] = []

            patched_addon.process_all_notes(col)

        print(
            "After processing, the tagged note is treated as immature by the tag rule, while the untagged control note still follows the deck interval behavior."
        )
        print_collection_state(col, "After processing (tag rule precedence)")

        assert_card_queues(
            col, tagged_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED]
        )
        assert_card_queues(
            col, control_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED]
        )
        assert col.get_note(tagged_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)
        assert col.get_note(control_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


def test_ignored_deck_skips_matching_tag_rule() -> None:
    """
    Scenario: Case when a note lives in an ignored deck even though it matches a tag rule.

    The addon should skip the ignored deck entirely, proving that the ignored-deck check happens
    before tag-based matching can change the card queues.
    """
    with temporary_collection() as col:
        addon = load_addon_module()
        model = build_test_notetype(col)

        active_deck_id = make_test_deck_id(col)
        ignored_deck_id = col.decks.id("Ignored Tagged Deck")
        assert ignored_deck_id is not None

        active_note, active_cards = add_note_with_siblings(
            col, model, active_deck_id, "Active tagged note"
        )
        ignored_note, ignored_cards = add_note_with_siblings(
            col, model, ignored_deck_id, "Ignored tagged note"
        )

        set_review_card_state(col, active_cards[0], ivl=20)
        set_review_card_state(col, ignored_cards[0], ivl=20)

        active_note.add_tag("easy_topic")
        ignored_note.add_tag("easy_topic")
        col.update_note(active_note)
        col.update_note(ignored_note)

        print(
            "Before processing the ignored deck, both notes match the tag rule, but only one deck is allowed to participate in filtering."
        )
        print_collection_state(col, "Before processing (ignored deck vs active tagged deck)")

        with patched_addon_state(col) as patched_addon:
            ignored_rule = {
                "did": str(ignored_deck_id),
                "name": "Ignored Tagged Deck",
                "ignored": True,
                "interval": 18,
            }
            patched_addon.config_settings["custom_deck_rules"] = [ignored_rule]
            patched_addon.config_settings["tag_rules"] = {"easy_topic": {"interval": 25}}
            patched_addon.custom_deck_rules_by_did.clear()
            patched_addon.custom_deck_rules_by_did[str(ignored_deck_id)] = ignored_rule
            patched_addon.ignored_deck_ids[:] = [str(ignored_deck_id)]

            patched_addon.process_all_notes(col)

        print(
            "After processing, the active deck is filtered normally, but the ignored deck remains untouched even though it matches the same tag rule."
        )
        print_collection_state(col, "After processing (ignored deck remains untouched)")

        assert_card_queues(
            col, active_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED]
        )
        assert_card_queues(
            col, ignored_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW]
        )
        assert col.get_note(active_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)
        assert not col.get_note(ignored_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_tag_rule_takes_precedence_over_custom_deck_interval()
    test_ignored_deck_skips_matching_tag_rule()
