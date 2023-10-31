# SibPush: Delay New Sibs

## Overview
Meet SibPush, your Anki addon that likes to keep new sibling cards at a chill distance. It makes sure that new cards only roll in after all their siblings have cozied up in your long-term memory. No more awkward family reunions in your review sessions!

## Purpose
So here’s the deal. Normally when you bump into a new card, Anki shoves its siblings to the side for just a day. Not cool, right? SibPush steps in to save the "spaced" in spaced repetition. It makes sure all the siblings have had their share of the spotlight, passing the set interval before any new faces show up. This way, you get to avoid cramming and actually remember stuff long-term. It’s all about keeping the learning groove going at a neat pace.


## Configuration
The configuration of SibPush is straightforward and can be tailored to meet your study needs. Here are the settings you can tweak in the config file:

- `debug`: Set to `true` if you are debugging. When `debug` is true, the addon will log more information to the console, which can be helpful for troubleshooting.

- `ignored_decks`: A list of deck IDs or names that you want to exclude from the SibPush mechanism. For example, if you have decks that you don’t want to delay new cards on, add them here.

- `interval`: The interval (in days) that must be surpassed by all siblings before new cards are introduced for review. Default is `21`.

## Usage
1. Install the addon at .
2. That's it! Review your decks as usual, and SibPush will take care of the rest, ensuring that new cards are introduced at the right time.

Happy studying!
