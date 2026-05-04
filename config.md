# Configuration Guide

## `default_interval`

-   **Type**: Integer
-   **Description**: Defines the interval (in days) required for a card to be considered "matured". Decks that are not listed in `custom_deck_rules` use this value.
-   **Example**: `"default_interval": 21`

## `custom_deck_rules`

-   **Type**: List of objects
-   **Description**: Specifies the decks that should use a custom rule. Each entry uses the deck ID (`did`) as the stable identifier; `name` is only for readability in the config file. `interval` overrides `default_interval` for that deck.
-   **Example**:

    ```json
    "custom_deck_rules": [
        {
            "did": "1777739665453",
            "name": "Siblings",
            "ignored": false,
            "interval": 18
        },
        {
            "did": "1777739665454",
            "name": "Big Deck",
            "ignored": true,
            "interval": 30
        }
    ]
    ```

    -   `did` is the deck ID Anki assigns to the deck.
    -   `name` is a human-friendly label shown only for convenience.
    -   `ignored: true` skips that deck entirely.
    -   `ignored: false` keeps that deck active under `default_interval`.
    -   `interval` is the maturity threshold for that specific deck.

## `tag_rules`

-   **Type**: Dictionary of tag names to rule objects
-   **Description**: Specifies note tags that should override the deck interval. Each key is a tag name, and each rule currently uses `interval` to define the maturity threshold for notes with that tag. Tag rules take precedence over deck rules, but they do not apply inside ignored decks.
-   **Example**:

    ```json
    "tag_rules": {
        "easy_topic": {
            "interval": 0
        },
        "hard_topic": {
            "interval": 30
        }
    }
    ```

    -   The first matching tag rule in the config wins when a note has multiple matching tags.
    -   Use `interval` to override the maturity threshold for notes with that tag.
    -   If a deck is ignored, SibPush skips the note entirely even if a tag rule matches.

## `debug`

-   **Type**: Boolean (true or false)
-   **Description**: Enables or disables logging of the addon operations.
    -   `true`: Logging is enabled. You can view the logs by accessing the `log.txt` file via the 'View files' option of the addon.
    -   `false`: Logging is disabled.
-   **Example**: `"debug": false`

## Suspension lifecycle

- SibPush marks addon-managed suspended notes with the `SibPush_suspended` tag.
- On the next deck browser render, SibPush checks tagged notes again and unsuspends the addon-managed cards whose remaining siblings are mature.
- Manually suspended cards are left alone by SibPush.
