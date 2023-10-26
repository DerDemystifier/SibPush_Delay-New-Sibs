# Configuration Guide

## `debug`

-   **Type**: Boolean (true or false)
-   **Description**: Enables or disables logging of the addon operations.
    -   `true`: Logging is enabled. You can view the logs by accessing the `log.txt` file via the 'View files' option of the addon.
    -   `false`: Logging is disabled.
-   **Example**: `"debug": false`

## `ignored_decks`

-   **Type**: List of strings
-   **Description**: Specifies the decks that should be ignored. You can provide either the complete deck name or just the subdeck name.
-   **Example**: `["Deck::SubDeck", "Deck2"]`

    **Note**: If you provide only the subdeck name and multiple decks share that name under different parent decks, all those decks will be ignored. To avoid potential confusion, it's recommended to use the Anki browser to retrieve the full name of the deck you wish to ignore (e.g `deck:Deck::SubDeck` → `Deck::SubDeck` and `deck:Deck2` → `Deck2`).

## `interval`

-   **Type**: Integer
-   **Description**: Defines the interval (in days) required for a card to be considered "matured". Once a card has matured, new sibling cards become eligible for study.
-   **Example**: `"interval": 21`
