# kshexplorer

A completely autonomous bot for the broken game from the [Kodsport](https://www.kodsport.se/) Halloween challenge

This bot has two distinct parts, movement and combat, documented below.

## movement

There are a few movement modes the bot can be in, All of which are in the list below. The bot first attempts to use the first movement mode, but if it fails to give a direction to move in the bot tries the next movement mode below it. This way, when for example the bot is trying to discover the whole floor but a pathway is blocked it can move on to trying to find the ladder instead. Movement is always recalculated each tick.

here is a simple TLDR of how the movement works: If a map of the floor is not known, explore the floor to get the entire floor map. Then, attempt to find the ladder on the floor if it is not already found. If it is found but the bot had items on this floor in a previous life that it does not have right now wander around to try and gather the items. Then, go to the ladder to proceed to the next floor.

### Targeting enemy

This movement mode is attempted when the bot sees a monster in its current FOV, and is discussed in more detail in the combat section.

### Floor discovery

This movement mode is attempted if the map of the current floor is not known. The bot uses a BFS to find the direction to move to get to the nearest unseen tile. If there are none unseen tiles the bot can move to, and if there are no monsters blocking any corridors that lead to unseen tiles the complete map of the floor is saved to file for further reference the next time the bot arrives at this floor after a respawn.

### Going to ladder

If the position of the ladder on the current floor is known (and thus also the entire map of the floor) and all the items that the bot has seen appear on this floor are gathered the bot will move towards the ladder tile to go to the next floor.

### Ladder search

In this mode the bot will attempt to move to the closest tile it has not been on to check if there is a ladder there. If the ladder was found, and a complete map of the whole floor exists the position of the ladder will be saved to file for future use.

### Item search

This mode uses 3 methods to try and determine a spot where loot can be found and moves toward it. To find a spot it tries to:

- If a monster position, not necessarily in the current FOV is known and reasonably up to date and if the combat AI thinks it can defeat the monster at said position it will choose this position to move to.
- If a position was not chosen yet and the bot knows the whole map, the bot chooses a random empty tile on the whole map to move to.
- Otherwise if a position still cant be decided on, it will move to some tile exactly 50 tiles away.

### Fleeing

This movement mode can be skipped to directly if the combat AI decides to flee from a monster. In this mode the bot attempts to move to the closest tile that is at least 15 tiles away from all monsters.

### Stuck

If all else fails to provide a direction to move in, the bot considers itself stuck. This only happens then the bot is cornered by monsters with no reasonable means of escape. In this state the bot just picks a random direction to move in.

## Combat

Throughout the bots adventure the bot gathers a lot of information about different monsters and items to better inform the combat AI. When a new weapon is found it equips it to find out how much damage it does and always uses the weapon that does the most damage. When observing monsters, it figures out from the information it is given, which is pretty much just the health and position of the monster, the damage the monster does (by comparing changes in player health with what types of monsters are close), its regen rate and max HP. The only thing that is hardcoded are the tiers of armor, from which the best armor is always equipped.

To get this out of the way, wise old men and hideous hydras are the bane of this game and are effectively treated as walls, because that's what they are. At the point when the bot encounters hydras it already has enough armor that it cannot be damaged by a single hydra.

When the bot sees a monster in its FOV that's not too many tiles away (like not in a whole different room that it sees through the wall), it goes in "combat mode". Here, it chooses the closest enemy and runs a 1v1 combat simulation based on the gathered damage, regen and current health of the monster. The result is a number signifying how much HP the bot estimates it will need to defeat the monster. If the HP needed is less than the current HP, the bot moves towards the enemy to attack it. If it is more, it goes into the fleeing movement mode. As an added special case, if the monster targeted is an "IT" the bot automatically equips "IT Isn't".

While the bots logic technically only handles 1v1 combat, it works just fine for combat against many monsters. If multiple monsters are attacking it which the bot wont be able to handle even though it would be able to handle a 1v1, the bots health will quickly fall below the simulated health needed and the bot will flee.

## Other

Here are some other things that the bot also does:

When entering a floor that the bot has explored before it tries to fit the current view into the map of the floor like a puzzle piece. If it only fits one way the bot has found its global position and overwrites the temporary map of the floor with the known map.

When moving away from a monster, maybe because if fleeing or because it was behind a wall and the bot is just passing by it caches the position of the monster for one minute. This way it is not stuck walking back and forth towards old men since it knows it cannot go that way, or is quicker at finding monsters during item searching.

If the bot health is below 25%, it uses a random health potion and records how much it heals for, even if this info isn't actually used anywhere in the code. I never implemented using strength and toughness potions because they are mostly useless and cannot be relied upon since they are not always on hand.

Much of what the bot thinks is shown on its curses UI. If you try and run the bot and get a curses error, try increasing the window size or decreasing the font size. Curses probably couldn't fit everything on screen.

Using these strategies, the bot is able to reliably reach floor 7 completely on its own without getting stuck. It does however most often get cornered by hydras on floor 7, because of their wall like nature and big population caused by their non-existing spawn cap, unless they are specifically removed by glitching them out of existence.
