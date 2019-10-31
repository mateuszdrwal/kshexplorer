import requests
import json
import curses
import pickle
import numpy as np
import copy
import shutil
import time
import re
import datetime
import random
import statistics

api_key = ""
username = ""
url = "http://halloween.kodsport.se/"

map_size = 400

item_preferences = [
    ["Skull helmet", "Bronze helmet", "Iron helmet", "Steel helmet", "Mithril helmet"],
    [
        "Skull legplates",
        "Bronze legplates",
        "Iron legplates",
        "Steel legplates",
        "Mithril legplates",
    ],
    [
        "Skull breastplate",
        "Bronze breastplate",
        "Iron breastplate",
        "Steel breastplate",
        "Mithril breastplate",
    ],
]

men_monsters = ["Mysterious Wise Old Man", "Hideous Hydra"]

event_log = open("events.txt", "a")


def save_game():
    while True:
        try:
            save = open("botsave.pkl", "wb")
            pickle.dump(game, save)
            save.close()
            break
        except:
            pass


def save_global():
    while True:
        try:
            global_file = open("global.pkl", "wb")
            pickle.dump(global_state, global_file)
            global_file.close()
            break
        except:
            pass


try:
    save = open("botsave.pkl", "rb")
    game = pickle.load(save)
    save.close()
except:
    game = {
        "pos": [int(map_size / 2), int(map_size / 2)],
        "world": np.array([["?"] * map_size] * map_size),
        "floor": 1,
        "events": [],
        "pos_known": False,
        "monster_pos": [],
    }
    save_game()

try:
    global_file = open("global.pkl", "rb")
    global_state = pickle.load(global_file)
    global_file.close()
except:
    global_state = {
        "all_items": set(),
        "all_monsters": {},
        "items": {"": {"category": "weapon", "damage": set()}},
        "floors": {},
        "item_floors": {},
        "ladders": {},
    }
    save_global()


def update_world(visible_region):
    global game, current

    world_region = game["world"][
        game["pos"][0] - current["radius"] : game["pos"][0] + current["radius"] + 1,
        game["pos"][1] - current["radius"] : game["pos"][1] + current["radius"] + 1,
    ]

    for player in current["players"]:
        visible_region[current["radius"] + player["relativePos"]["row"]][
            current["radius"] + player["relativePos"]["col"]
        ] = ","

    for row in range(world_region.shape[0]):
        for col in range(world_region.shape[1]):
            if world_region[row][col] != "," or visible_region[row][col] == "E":
                world_region[row][col] = visible_region[row][col]

    save_game()


def call(endpoint, **parameters):
    global current, region, me, old_monsters, last_health, request_time, item_search_target

    skip_damage = False
    try:
        old_monsters = current["monsters"]
    except (NameError, KeyError, TypeError):
        skip_damage = True

    start_request_time = time.perf_counter()
    while True:
        try:
            response = requests.get(
                url + endpoint, params={"apiKey": api_key, **parameters}, timeout=2
            ).text
        except:
            continue
        current = json.loads(response)
        if "error" not in current:
            break
        if current["error"] == "You don't have a player":
            call("look")
        time.sleep(0.1)
    request_time = time.perf_counter() - start_request_time
    debug_window.addstr(1, 0, f"request time: {request_time}")

    region = [list(row) for row in current["surrounding"]]

    for player in current["players"]:
        print()
        if player["name"] == username:
            me = player

    for monster in current["monsters"]:
        region[current["radius"] + monster["relativePos"]["row"]][
            current["radius"] + monster["relativePos"]["col"]
        ] = "E"

    for event in current.get("events", []):
        if event != "you moved":
            new_event(event)

        match = re.search(r"^\w* dealt (\d*) damage to (.*)$", event)
        if (
            "dealt" in event
            and not skip_damage
            and request_time < 0.5
            and item_cooldown == 0
        ):
            count = 0
            for monster in old_monsters:
                if (
                    abs(monster["relativePos"]["row"])
                    + abs(monster["relativePos"]["col"])
                    <= 1
                ):
                    count += 1
            if count == 1:
                damage = match.group(1)
                weapon = [
                    i
                    for i in current["equipped"]
                    if i in global_state["items"]
                    and global_state["items"][i]["category"] == "weapon"
                ]
                if not weapon:
                    weapon = ""
                else:
                    weapon = weapon[0]
                global_state["items"][weapon]["damage"].add(int(damage))
                save_global()

        if match and match.group(2) in men_monsters:
            new_event("CLIENT hit man, probably stuck, getting unstuck...")
            time.sleep(1)
            call("look")
            time.sleep(1)
            item_search_target = None
            request_time = 1

    if (
        me["health"] != last_health
        and last_health > me["health"]
        and request_time < 0.5
        and item_cooldown == 0
    ):
        count = 0
        attacking_monster = None
        for monster in old_monsters:
            if (
                abs(monster["relativePos"]["row"]) + abs(monster["relativePos"]["col"])
                <= 1
            ):
                count += 1
                attacking_monster = monster
        if count == 1:
            damage = last_health - me["health"]
            new_event(f"CLIENT {attacking_monster['name']} hit for {damage}")
            global_state["all_monsters"][attacking_monster["name"]]["damage"].add(
                damage
            )
            save_global()

    if me["health"] != last_health:
        new_event(f"CLIENT new health: {me['health']}")
        last_health = me["health"]

    if request_time < 0.5:
        new_monster_names = [i["name"] for i in current["monsters"]]
        old_monster_names = [i["name"] for i in old_monsters]
        for monster in new_monster_names:
            if monster in old_monster_names:
                if (
                    new_monster_names.count(monster) != 1
                    or old_monster_names.count(monster) != 1
                ):
                    continue

                new_monster_index = new_monster_names.index(monster)
                old_monster_index = old_monster_names.index(monster)
                if (
                    abs(current["monsters"][new_monster_index]["relativePos"]["row"])
                    < current["radius"]
                    or abs(current["monsters"][new_monster_index]["relativePos"]["col"])
                    < current["radius"]
                ):
                    continue
                old_health = old_monsters[old_monster_index]["health"]
                new_health = current["monsters"][new_monster_index]["health"]
                regen = new_health - old_health
                for event in current.get("events", []):
                    match = re.search(r"^\w* dealt (\d*) damage to (.*)$", event)
                    if match and match.group(2) == monster:
                        regen += int(match.group(1))
                        break
                if regen > 0:
                    global_state["all_monsters"][monster]["regen"] = max(
                        global_state["all_monsters"][monster]["regen"], regen
                    )
                    new_event(f"CLIENT {monster} regened {regen}")
                    save_global()


def new_event(message):
    event_log.write(f"{datetime.datetime.now().isoformat()} {message}\n")
    event_log.flush()
    game["events"].append(message)


def bfs(
    enemy_only=False,
    flee=False,
    discover=False,
    target_pos=None,
    enemy_targeted=False,
    target_distance=None,
    max_dist=None,
    monsters=None,
):
    global bigger_region
    queue = []
    direction = [[None for j in range(map_size)] for i in range(map_size)]
    distance = [[None for j in range(map_size)] for i in range(map_size)]
    backup = None
    discover_done_response = "done"

    direction[game["pos"][0] + 1][game["pos"][1]] = "south"
    distance[game["pos"][0] + 1][game["pos"][1]] = 1
    queue.append([game["pos"][0] + 1, game["pos"][1]])
    direction[game["pos"][0] - 1][game["pos"][1]] = "north"
    distance[game["pos"][0] - 1][game["pos"][1]] = 1
    queue.append([game["pos"][0] - 1, game["pos"][1]])
    direction[game["pos"][0]][game["pos"][1] + 1] = "east"
    distance[game["pos"][0]][game["pos"][1] + 1] = 1
    queue.append([game["pos"][0], game["pos"][1] + 1])
    direction[game["pos"][0]][game["pos"][1] - 1] = "west"
    distance[game["pos"][0]][game["pos"][1] - 1] = 1
    queue.append([game["pos"][0], game["pos"][1] - 1])

    while queue:

        pos = queue.pop(0)

        if enemy_only and distance[pos[0]][pos[1]] > current["radius"] * 2:
            continue

        if max_dist and distance[pos[0]][pos[1]] > max_dist:
            continue

        if game["world"][pos[0]][pos[1]] == "#":
            continue

        old_men = [
            monster
            for monster in current["monsters"]
            if monster["name"] in men_monsters
        ]
        if old_men:
            cont = False
            for man in old_men:
                if (
                    game["pos"][0] + man["relativePos"]["row"] == pos[0]
                    and game["pos"][1] + man["relativePos"]["col"] == pos[1]
                ):
                    cont = True
                    break
            if cont:
                discover_done_response = None
                continue

        if (
            global_state["ladders"].get(game["floor"])
            and target_pos != global_state["ladders"][game["floor"]]
            and pos == global_state["ladders"][game["floor"]]
        ):
            continue

        if pathfinding_visible:
            bigger_row = pos[0] - (game["pos"][0] - int(map_rows / 2))
            bigger_col = pos[1] - (game["pos"][1] - int(map_cols / 2))
            if (
                0 <= bigger_row < bigger_region.shape[0]
                and 0 <= bigger_col < bigger_region.shape[1]
            ):
                bigger_region[bigger_row][bigger_col] = {
                    "north": "^",
                    "south": "V",
                    "east": ">",
                    "west": "<",
                }[direction[pos[0]][pos[1]]]

        if monsters:
            if distance[pos[0]][pos[1]] > current["radius"] * 2:
                continue
            for monster in monsters:
                if [
                    game["pos"][0] + monster["relativePos"]["row"],
                    game["pos"][1] + monster["relativePos"]["col"],
                ] == pos and monster["name"] not in men_monsters:
                    return monster

        if flee:
            if game["world"][pos[0]][pos[1]] == "E":
                continue
            for monster in current["monsters"]:
                row_distance = abs(
                    (game["pos"][0] + monster["relativePos"]["row"]) - pos[0]
                )
                col_distance = abs(
                    (game["pos"][1] + monster["relativePos"]["col"]) - pos[1]
                )
                if row_distance + col_distance <= 15:
                    break
            else:
                return direction[pos[0]][pos[1]]

        if target_distance and distance[pos[0]][pos[1]] >= target_distance:
            return pos

        if target_pos and target_pos == pos:
            return direction[pos[0]][pos[1]]

        if not flee and not target_distance and not monsters:
            if game["world"][pos[0]][pos[1]] == "E":
                if not enemy_only and not enemy_targeted:
                    if not backup:
                        backup = direction[pos[0]][pos[1]]
                    discover_done_response = None
                    continue
                else:
                    return direction[pos[0]][pos[1]]
            if (
                not enemy_only
                and not discover
                and not target_pos
                and game["world"][pos[0]][pos[1]] in ["."]
            ):
                return direction[pos[0]][pos[1]]
            if not enemy_only and discover and game["world"][pos[0]][pos[1]] in ["?"]:
                return direction[pos[0]][pos[1]]

        for next_direction in [(-1, 0), (0, -1), (1, 0), (0, 1)]:
            new_pos = [pos[0] + next_direction[0], pos[1] + next_direction[1]]
            if direction[new_pos[0]][new_pos[1]]:
                continue
            direction[new_pos[0]][new_pos[1]] = direction[pos[0]][pos[1]]
            distance[new_pos[0]][new_pos[1]] = distance[pos[0]][pos[1]] + 1
            queue.append(new_pos)

    if discover:
        return discover_done_response

    if backup:
        return backup

    return


def health_to_kill(monster):
    weapon = [
        i
        for i in current["equipped"]
        if i in global_state["items"]
        and global_state["items"][i]["category"] == "weapon"
    ]
    if weapon:
        weapon = weapon[0]
    if monster["name"] == "IT":
        weapon = "IT Isn't"
    if not weapon:
        weapon = ""
    weapon_damage = (
        int(statistics.median(global_state["items"][weapon]["damage"]))
        if len(global_state["items"][weapon]["damage"])
        else 99_999_999_999_999
    )
    if (
        weapon_damage < global_state["all_monsters"][monster["name"]]["regen"]
        and weapon_damage < monster["health"]
    ):
        return 999_999_999_999_999_999
    monster_damage = (
        int(statistics.median(global_state["all_monsters"][monster["name"]]["damage"]))
        if len(global_state["all_monsters"][monster["name"]]["damage"])
        else 1
    )

    player_damage = 0
    monster_health = monster["health"]
    while monster_health > 0:
        monster_health = min(
            monster["health"],
            monster_health + global_state["all_monsters"][monster["name"]]["regen"],
        )
        player_damage += monster_damage
        monster_health -= weapon_damage

    return player_damage


def main(stdscr):
    global last_health, info_window, old_monsters, current, map_rows, map_cols, bigger_region, item_cooldown, item_search_target, debug_window, pathfinding_visible
    screen_size = stdscr.getmaxyx()
    map_row_start = 0
    map_col_start = 50
    event_col_start = screen_size[1] - 60
    event_rows = 30
    map_col_end = event_col_start

    info_window = curses.newwin(screen_size[0], map_col_start, 0, 0)
    event_window = curses.newwin(
        event_rows, screen_size[1] - event_col_start, 0, event_col_start
    )
    debug_window = curses.newwin(
        screen_size[0] - event_rows,
        screen_size[1] - event_col_start,
        event_rows,
        event_col_start,
    )
    map_window = curses.newwin(
        screen_size[0], map_col_end - map_col_start, 0, map_col_start
    )
    info_window.bkgdset(" ")
    curses.curs_set(False)
    stdscr.nodelay(True)

    direction = ""
    movement_mode = ""
    max_health = 100
    max_inventory = 0
    item_cooldown = 0
    last_health = 100
    item_search_target = None
    old_monsters = []
    start_total_time = time.perf_counter()
    pathfinding_visible = False

    call("look")
    update_world(region)

    last_inventory = current["itemNames"]

    while True:

        char = stdscr.getch()
        if char == 113:
            return
        elif char == ord("p"):
            pathfinding_visible = not pathfinding_visible

        debug_window.addstr(8, 0, f"show pathfinding: {pathfinding_visible}")
        debug_window.addstr(10, 0, f"cached monsters: {len(game['monster_pos'])}")

        map_rows = screen_size[0] - map_row_start - 1
        map_cols = map_col_end - map_col_start - 1
        bigger_region_raw = copy.deepcopy(
            game["world"][
                game["pos"][0] - int(map_rows / 2) : game["pos"][0] + int(map_rows / 2),
                game["pos"][1] - int(map_cols / 2) : game["pos"][1] + int(map_cols / 2),
            ]
        )
        bigger_region = copy.deepcopy(bigger_region_raw)

        info_window.move(0, 0)
        info_window.addstr(f"direction: {direction}\n")
        info_window.addstr(f"movement mode: {movement_mode}\n")
        info_window.addstr(f"max health: {max_health}\n")
        info_window.addstr(f"floor: {game['floor']}\n")

        info_window.move(5, 0)
        info_window.addstr("Players:\n", curses.A_BOLD)
        for i, player in enumerate(current["players"][:3]):
            info_window.addstr(f"player {i+1}: {player['name']} ")
            info_window.addstr(f"{player['health']}\n")
            bigger_region[int(map_rows / 2) + player["relativePos"]["row"]][
                int(map_cols / 2) + player["relativePos"]["col"]
            ] = str(i + 1)

        info_window.move(10, 0)
        info_window.addstr("Monsters:\n", curses.A_BOLD)
        for i, monster in enumerate(current["monsters"][:8]):
            info_window.addstr(f"monster {chr(i+65)}: {monster['name']} ")
            info_window.addstr(f"{monster['health']}\n")
            bigger_region[int(map_rows / 2) + monster["relativePos"]["row"]][
                int(map_cols / 2) + monster["relativePos"]["col"]
            ] = chr(i + 65)

        info_window.move(20, 0)
        info_window.addstr("Events:\n", curses.A_BOLD)
        for event in current.get("events", [])[:5]:
            info_window.addstr(f"{event}\n")

        info_window.move(27, 0)
        info_window.addstr("Inventory:\n", curses.A_BOLD)
        for i, item in enumerate(current["itemNames"][:25]):
            info_window.addstr(
                f"{item}\n", curses.A_STANDOUT if item in current["equipped"] else 0
            )

        for i, event in enumerate(game["events"][-(event_rows - 1) :]):
            event_window.addstr(i, 0, event[: (screen_size[1] - event_col_start) - 1])
            pass

        debug_window.addstr(15, 4, "\n    ".join("".join(row) for row in region))

        flee = False
        monster_target = False
        if current["monsters"]:
            closest_monster = bfs(monsters=current["monsters"])
            if closest_monster:
                htk = health_to_kill(closest_monster)
                debug_window.addstr(4, 0, closest_monster["name"])
                debug_window.addstr(5, 0, str(htk))
                if htk < me["health"]:
                    monster_target = [
                        game["pos"][0] + monster["relativePos"]["row"],
                        game["pos"][1] + monster["relativePos"]["col"],
                    ]
                else:
                    flee = True
                if (
                    "IT Isn't" in current["itemNames"]
                    and closest_monster["name"] == "IT"
                ):
                    call("use", itemName="IT Isn't")

        direction = None
        if not flee and monster_target and not direction:
            direction = bfs(
                target_pos=monster_target,
                max_dist=current["radius"] * 2,
                enemy_targeted=True,
            )
            movement_mode = "trageting enemy"
        if not flee and game["floor"] not in global_state["floors"] and not direction:
            direction = bfs(discover=True)
            if direction == "done":
                direction = None
                cleaned_map = game["world"]
                cleaned_map = np.where(cleaned_map == "?", "#", cleaned_map)
                cleaned_map = np.where(cleaned_map == ",", ".", cleaned_map)
                cleaned_map = np.where(cleaned_map == "E", ".", cleaned_map)
                global_state["floors"][game["floor"]] = cleaned_map
                save_global()
                game["pos_known"] = True
                new_event(f"CLIENT explored entire floor {game['floor']}")
            movement_mode = "floor discovery"
        if (
            not flee
            and not direction
            and global_state["ladders"].get(game["floor"])
            and not set(
                [
                    i
                    for i in global_state["item_floors"].get(game["floor"], [])
                    if global_state["items"][i]["category"]
                    in ["weapon", "legplates", "breastplate", "helmet"]
                ]
            ).difference(set(current["itemNames"]))
            and me["health"] / max_health > 0.95
        ):
            direction = bfs(target_pos=global_state["ladders"][game["floor"]])
            movement_mode = "going to ladder"
            debug_window.addstr(6, 0, str(game["pos"]))
            debug_window.addstr(7, 0, str(global_state["ladders"][game["floor"]]))
        if (
            not flee
            and not direction
            and not global_state["ladders"].get(game["floor"])
        ):
            direction = bfs()
            movement_mode = "ladder search"
            debug_window.addstr(9, 0, f"tiles left: {np.sum(game['world'] == '.')}")
        if not flee and not direction:

            if not item_search_target or item_search_target == game["pos"]:
                item_search_target = None
                for monster in game["monster_pos"]:
                    if (
                        monster["name"] not in men_monsters
                        and health_to_kill(
                            {
                                "name": monster["name"],
                                "health": global_state["all_monsters"][monster["name"]][
                                    "max_health"
                                ],
                            }
                        )
                        < max_health
                    ):
                        item_search_target = [monster["row"], monster["col"]]
                        break
                if not item_search_target and game["floor"] in global_state["floors"]:
                    test_pos = [
                        random.randint(0, map_size - 1),
                        random.randint(0, map_size - 1),
                    ]
                    while (
                        global_state["floors"][game["floor"]][test_pos[0]][test_pos[1]]
                        != "."
                    ):
                        test_pos = [
                            random.randint(0, map_size - 1),
                            random.randint(0, map_size - 1),
                        ]
                    item_search_target = test_pos
                elif not item_search_target:
                    item_search_target = bfs(target_distance=50)

            direction = bfs(target_pos=item_search_target)
            if direction == None:
                item_search_target = None
            movement_mode = "item search"
        else:
            item_search_target = None
        if not direction:
            if flee:
                new_event(f"CLIENT fleeing on purpose")
            else:
                new_event(f"CLIENT fleeing not on purpose")
            direction = bfs(flee=True)
            movement_mode = "fleeing"
        if not direction:
            new_event("CLIENT stuck")
            movement_mode = "stuck"
            direction = ["north", "south", "east", "west"][random.randint(0, 3)]

        map_window.move(0, 0)
        map_window.addstr("\n".join("".join(row) for row in bigger_region))
        info_window.overwrite(stdscr)
        map_window.overwrite(stdscr)
        event_window.overwrite(stdscr)
        debug_window.overwrite(stdscr)
        stdscr.refresh()
        info_window.clear()
        map_window.clear()
        event_window.clear()
        debug_window.clear()
        stdscr.clear()

        if direction:
            call("move", moveDirection=direction)
            if "you moved" in current.get("events", []) or "ladder" in "".join(
                current.get("events", [])
            ):
                if direction == "north":
                    game["pos"][0] -= 1
                elif direction == "south":
                    game["pos"][0] += 1
                elif direction == "west":
                    game["pos"][1] -= 1
                elif direction == "east":
                    game["pos"][1] += 1

            update_world(region)

        total_time = time.perf_counter() - start_total_time
        debug_window.addstr(0, 0, f"total time: {total_time}")
        debug_window.addstr(2, 0, f"compute time: {total_time - request_time}")
        start_total_time = time.perf_counter()

        max_health = max(max_health, me["health"])
        max_inventory = max(max_inventory, len(current["itemNames"]))

        for item in current["itemNames"]:
            if item not in global_state["all_items"]:
                global_state["all_items"].add(item)
                save_global()

            if (
                not global_state["items"].get(item)
                or global_state["items"][item]["category"] == "unknown"
            ):
                global_state["items"][item] = {"category": "unknown"}
                if "health" in item.lower() and "potion" in item.lower():
                    global_state["items"][item] = {"category": "health", "healing": 1}
                if "strength" in item.lower() and "potion" in item.lower():
                    global_state["items"][item] = {"category": "strength"}
                if "fortitude" in item.lower() and "potion" in item.lower():
                    global_state["items"][item] = {"category": "fortitude"}
                if "helmet" in item.lower():
                    global_state["items"][item] = {"category": "helmet"}
                if "breastplate" in item.lower():
                    global_state["items"][item] = {"category": "breastplate"}
                if "legplates" in item.lower():
                    global_state["items"][item] = {"category": "legplates"}
                if (
                    "dagger" in item.lower()
                    or "sword" in item.lower()
                    or "axe" in item.lower()
                    or "slayer" in item.lower()
                    or "slicer" in item.lower()
                    or "blade" in item.lower()
                    or item == "IT Isn't"
                ):
                    global_state["items"][item] = {
                        "category": "weapon",
                        "damage": set(),
                    }
                save_global()

        if "ladder" in "".join(current.get("events", [])):
            new_event(f"CLIENT floor {game['floor']+1}")
            if game["floor"] in global_state["floors"]:
                new_event(f"CLIENT found ladder for floor {game['floor']}")
                global_state["ladders"][game["floor"]] = game["pos"]
                save_global()
            game["pos"] = [int(map_size / 2), int(map_size / 2)]
            game["world"] = np.array([["?"] * map_size] * map_size)
            game["floor"] += 1
            game["pos_known"] = False
            game["monster_pos"] = []
            item_search_target = None
            save_game()
            call("look")
            update_world(region)

        if len(current["itemNames"]) == 0 and max_inventory != 0:
            new_event("CLIENT died")
            shutil.move("botsave.pkl", f"{time.time()}.pkl")
            max_health = 100
            max_inventory = 0
            item_cooldown = 0
            last_health = 100
            old_monsters = []
            current = None
            item_search_target = None
            game["pos"] = [int(map_size / 2), int(map_size / 2)]
            game["world"] = np.array([["?"] * map_size] * map_size)
            game["floor"] = 1
            game["events"] = []
            game["pos_known"] = False
            game["monster_pos"] = []
            call("look")
            update_world(region)
            save_game()

        if len(last_inventory) < len(current["itemNames"]):
            if not game["floor"] in global_state["item_floors"]:
                global_state["item_floors"][game["floor"]] = set()
            for item in set(current["itemNames"]).difference(set(last_inventory)):
                global_state["item_floors"][game["floor"]].add(item)

        last_inventory = current["itemNames"]

        if (
            not game["pos_known"]
            and game["floor"] in global_state["floors"]
            and int(time.time()) % 2
        ):
            cleaned_map = np.array([list(row) for row in current["surrounding"]])

            matches = 0
            matched = None
            for rowoffset in range(map_size - cleaned_map.shape[0] + 1):
                if matches >= 2:
                    break
                for coloffset in range(map_size - cleaned_map.shape[1] + 1):
                    if matches >= 2:
                        break
                    failed_flag = False
                    for currentrow in range(cleaned_map.shape[0]):
                        for currentcol in range(cleaned_map.shape[1]):
                            if (
                                global_state["floors"][game["floor"]][
                                    rowoffset + currentrow
                                ][coloffset + currentcol]
                                != cleaned_map[currentrow][currentcol]
                            ):
                                failed_flag = True
                                break
                        if failed_flag:
                            break

                    if failed_flag:
                        continue

                    matches += 1
                    matched = [rowoffset, coloffset]

            if matches == 1:
                new_event("CLIENT found floor position")
                game["pos"] = [
                    matched[0] + current["radius"],
                    matched[1] + current["radius"],
                ]
                game["world"] = copy.deepcopy(global_state["floors"][game["floor"]])
                game["pos_known"] = True
                # cleaned_position = [game["pos"][0] - cleaned_row_offset, game["pos"][1] - cleaned_col_offset]

        new_monster_pos = []
        for monster_pos in game["monster_pos"]:
            if game["world"][monster_pos["row"]][monster_pos["col"]] == "E":
                if monster_pos["expiery"] < time.time():
                    game["world"][monster_pos["row"]][monster_pos["col"]] = "."
                    continue
                new_monster_pos.append(monster_pos)
        game["monster_pos"] = new_monster_pos
        save_game()

        for monster in current["monsters"]:
            global_pos = [
                game["pos"][0] + monster["relativePos"]["row"],
                game["pos"][1] + monster["relativePos"]["col"],
            ]
            for registered_monster in game["monster_pos"]:
                if (
                    registered_monster["row"] == global_pos[0]
                    and registered_monster["col"] == global_pos[1]
                ):
                    break
            else:
                game["monster_pos"].append(
                    {
                        "row": global_pos[0],
                        "col": global_pos[1],
                        "expiery": time.time() + 60,
                        "name": monster["name"],
                    }
                )
                save_game()

        combined_preferences = copy.deepcopy(item_preferences)
        weapons = [
            i
            for i in global_state["items"].items()
            if i[1]["category"] == "weapon" and i[0] != "IT Isn't"
        ]
        weapons.sort(
            key=lambda w: sum(w[1]["damage"]) / len(w[1]["damage"])
            if len(w[1]["damage"]) > 0
            else 9_999_999_999_999
        )
        weapons = ["IT Isn't"] + [i[0] for i in weapons.copy()]

        combined_preferences += [weapons]

        for preference in combined_preferences:
            for item in reversed(preference):
                if item in current["itemNames"]:
                    if item not in current["equipped"]:
                        call("use", itemName=item)
                    break

        while me["health"] / max_health < 0.25:
            for item in current["itemNames"]:
                if "health" in item.lower():
                    old_health = me["health"]
                    call("use", itemName=item)
                    new_health = me["health"]
                    global_state["items"][item]["healing"] = max(
                        new_health - old_health, global_state["items"][item]["healing"]
                    )
                    save_global()
                    break
            else:
                break

        item_cooldown = max(0, item_cooldown - 1)
        for monster in current["monsters"]:

            if monster["name"] not in global_state["all_monsters"]:
                global_state["all_monsters"][monster["name"]] = {
                    "damage": set(),
                    "regen": 0,
                    "max_health": 1,
                }
                save_global()

            if (
                monster["health"]
                > global_state["all_monsters"][monster["name"]]["max_health"]
            ):
                global_state["all_monsters"][monster["name"]]["max_health"] = monster[
                    "health"
                ]
                save_global()


curses.wrapper(main)
