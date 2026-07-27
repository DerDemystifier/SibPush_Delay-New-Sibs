# ADR-0001: Track SibPush suspension provenance

- **Status:** Accepted
- **Date:** 2026-07-27
- **Decision owners:** SibPush maintainers

## Context

SibPush automatically suspends new sibling cards while another sibling is not
mature. A user can later decide that SibPush should no longer manage an entire
deck. Ignoring the deck must stop future processing, but it should also be able
to undo the suspension changes SibPush already made in that deck.

The previous implementation inferred addon-managed suspensions from broad card
properties such as:

- the card being new;
- the card currently being suspended; and
- the note having siblings.

Those properties are not sufficient to establish who suspended a card. A user
may have suspended the card before SibPush was installed, or may suspend a card
in a note that SibPush also processes. Restoring every matching card when a deck
is ignored can therefore undo a user decision.

Individual-card ignoring has a different meaning. It is a direct instruction to
leave the selected card alone, so toggling **Ignore card** must not change its
queue or suspension state. Deck ignoring is broader: it opts the whole deck out
of SibPush and should clean up SibPush's own prior suspension changes without
touching unrelated user scheduling decisions.

## Decision

Record suspension provenance in card custom data with two independent boolean
markers:

```json
{
  "sibpsusp": true,
  "sibpign": true
}
```

These are the exact marker keys written by SibPush. They are alphanumeric and no longer than
8 bytes because this Anki build's custom-data backend rejects longer keys and its `prop:cds:`
search parser does not reliably accept underscores in marker keys.

The markers have distinct meanings:

- `sibpsusp: true` means SibPush caused the card to be suspended and
  has not explicitly undone that suspension. It is a provenance/restoration
  marker, not a claim that the card is currently suspended.
- `sibpign: true` means SibPush must leave the card alone during normal
  processing. This marker is the renamed replacement for the current
  `{"sibpush": "ignored"}` representation.

The markers are independent. A card may contain both markers. In that case,
`sibpign` takes precedence for normal processing, while
`sibpsusp` preserves the information needed for explicit cleanup.

### Marker lifecycle

1. When SibPush actually changes an eligible card from active to suspended, it
  writes `sibpsusp: true`.
2. If a card was already suspended before SibPush tried to process it, SibPush
   does not write the marker.
3. If a user manually unsuspends a card carrying `sibpsusp`, SibPush
   deliberately leaves the marker in place. The marker records how the card
   entered the suspended state, not its current queue. If normal processing
   would suspend that card again, SibPush may do so. The user's explicit way to
  opt that card out is `sibpign: true`.
4. When SibPush itself unsuspends/restores a card, it removes
  `sibpsusp`.
5. When a deck becomes ignored, cleanup restores only currently suspended,
  eligible new sibling cards carrying `sibpsusp`. It then removes the
   marker from cards it restored. Cards without the marker, review cards,
   standalone cards, and individually ignored cards remain untouched.
6. Addon deletion uses the same marker-aware restoration rule rather than
   inferring addon ownership from queue type and sibling count.
7. All custom-data updates preserve unrelated keys and merge/remove only
   SibPush's own markers.

### Storage-key constraint

The names above are the domain-level names for the markers. This Anki build
limits custom-data keys to 8 bytes, so the implementation uses recognizable,
centrally defined marker keys (`sibpsusp` and `sibpign`). Tests and behavior use
these exact persisted names.

This constraint must not be solved by reverting to one overloaded key/value
pair. Suspension provenance and user-requested ignoring are separate facts and
must remain independently representable.

## Consequences

### Positive

- Ignoring a deck can restore SibPush's changes without unsuspending cards that
  the user suspended independently.
- Manual unsuspension has deliberate semantics: it does not erase the fact that
  SibPush originally suspended the card.
- Individual-card ignore remains metadata-only and never changes the selected
  card's queue as a side effect.
- Addon deletion can clean up only suspensions SibPush actually created.
- The restoration policy becomes explicit, testable, and independent of Anki's
  current queue classification.

### Negative

- Every SibPush suspension and restoration path must maintain the marker
  lifecycle correctly.
- Existing cards and legacy collections may not have provenance markers. They
  cannot be safely inferred as addon-suspended and must be left alone unless a
  migration has authoritative evidence.
- Custom-data writes become slightly more involved because both markers and
  unrelated addon data must be preserved.
- A marker can remain on a manually unsuspended card by design. It must not be
  interpreted as proof that the card is currently suspended.
- A storage-key migration is required from the current `{"sibpush":
  "ignored"}` representation to the independent ignore marker.

## Alternatives considered

### Keep inferring ownership from card state

Rejected. New-card status, current suspension, and sibling count do not reveal
whether SibPush or the user caused the suspension. This is exactly the failure
mode that caused deck ignore to risk undoing user scheduling decisions.

### Make deck ignore metadata-only

Rejected as the complete solution. That would preserve user state safely, but
would also leave SibPush's prior deck-wide suspension changes in place. Users
who opt a deck out after SibPush has acted would not receive the expected
cleanup of SibPush's own changes.

### Use one overloaded `sibpush` marker

Rejected. A single key with values such as `ignored` and `suspended` obscures
the fact that the states are independent and cannot represent a card that was
SibPush-suspended and later individually ignored without losing provenance.

## Implementation notes

- Define the marker keys as constants in `sibpush/state.py` (`sibpsusp` and `sibpign`).
- Update `suspend_cards()` to mark only cards it actually suspends.
- Update every SibPush-initiated unsuspend path to remove the suspension marker.
- Make deck-ignore and addon-delete cleanup filter on the suspension marker,
  while still excluding individually ignored cards from normal cleanup.
- Migrate the existing ignore representation and preserve unrelated custom data.
- Run the card-data migration before pending browser cleanup or note scanning. Direct upgrades
  from 2.0 use the 2.1 migration pack; older upgrades run the existing 2.0 recovery pack, which
  chains the same card-data migration before reprocessing.
- Cleanup uses positive marker searches as candidate sets and performs the authoritative
  suspended/new/sibling/ignored checks in Python because this Anki build's negative custom-data
  search is not reliable. Each restore batch re-fetches cards immediately before unsuspending and
  verifies that the card is still in the requested ignored deck. A scheduler exception is treated
  as ambiguous, including partial batch transitions: provenance markers are preserved rather than
  inferred from the post-exception queue state. Direct ignored-marker cleanup removes both the
  migrated `sibpign` representation and the legacy `sibpush: "ignored"` representation while
  preserving suspension provenance and unrelated custom data.
- Add regression scenarios for pre-suspended user cards, addon-suspended cards,
  manual unsuspension with marker retention, individual ignore, deck ignore,
  unignore/reprocessing, addon deletion, and custom-data preservation.
