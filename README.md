# SibPush: Delay New Sibs

<center>
    <img src="https://derdemystifier.github.io/SibPush_Delay-New-Sibs/images/illustration.jpg">
</center>

## Overview

Meet SibPush, your Anki addon that likes to keep new sibling cards at a chill distance. It suspends new sibling cards until their older siblings have matured, then brings them back when the deck browser is opened again. No more awkward family reunions in your review sessions!

## Purpose

So here’s the deal. Normally when you bump into a new card, Anki shoves its siblings to the side for just a day. Not cool, right? SibPush steps in to save the "spaced" in spaced repetition. It suspends the new siblings that should wait, marks them with the `SibPush_suspended` tag, and checks for recovery on the next deck browser render. Once the remaining siblings are mature enough, the suspended cards are unsuspended again. This way, you get to avoid cramming and actually remember stuff long-term. It’s all about keeping the learning groove going at a neat pace.

Note: It's also compatible with V3 Scheduler.

## Configuration

The configuration of SibPush is straightforward and can be tailored to meet your study needs. Here are the settings you can tweak in the config file:

-   `interval`: The interval (in days) that must be surpassed by all siblings before new cards are introduced for review. Default is `21`.

-   `ignored_decks`: A list of deck IDs or names that you want to exclude from the SibPush mechanism. For example, if you have decks that you don’t want to delay new cards on, add them here.

-   `debug`: Set to `true` if you are debugging. When `debug` is true, the addon will log more information to `log.txt` file, which can be helpful for troubleshooting.

### Notes on addon-managed suspension

-   When SibPush suspends cards, it adds the `SibPush_suspended` tag to the note.
-   On the next deck browser render, SibPush scans tagged notes and unsuspends the addon-managed cards whose remaining siblings are mature.
-   Cards suspended manually by you are not part of SibPush’s suspension lifecycle.

## Usage

1. Install the addon at [Anki Addons](https://ankiweb.net/shared/info/1856111213) .
2. That's it! Review your decks as usual, and SibPush will take care of the rest, ensuring that new cards are introduced at the right time.

Happy studying!
