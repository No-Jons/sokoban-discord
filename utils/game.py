import copy
import discord
import emojis
import random
import re


class Games:
    def __init__(self):
        self.games = list()
        self.format_key = {"player": "🔵", "empty": "⬛", "box": "🟫", "completed_box": "❎", "wall": "🟥", "border": "🟥", "goal": "🔸", "enemy": "🔴"}
        self.emojis = ["⬅️", "⬆️", "➡️", "⬇️", "🔁"]

    def check_active(self, user_id, channel_id):
        for game in self.games:
            if game["user"] == user_id or game["channel"] == channel_id:
                return True
        return False

    def new(self, user, channel, emoji_player, level_id="1", file=None, content=None, text=None):
        self.format_key["player"] = emojis.encode((emoji_player or "🔵"))
        self.games.append(
            {
                "user": user.id,
                "channel": channel.id,
                "game": GameManager(level_id, emoji_player=emoji_player, file=file, content=content, text=text)
            }
        )

    def delete(self, user_id):
        next = None
        for game in range(len(self.games)):
            if self.games[game]["user"] == user_id:
                next = self.games[game]["game"].next_level
                del self.games[game]
        return next

    def get_game(self, user_id):
        for game in self.games:
            if game["user"] == user_id:
                return game["game"]
        return None

    def format_board(self, user_id):
        game = self.get_game(user_id)
        border = self.format_key["border"] * (game.height + 2)
        content = border + "\n"
        for row in game.board:
            content += self.format_key["border"]
            for entry in row:
                content += self.format_key[entry]
            content += self.format_key["border"] + "\n"
        content += border
        return content

    async def react_to(self, message):
        for emoji in self.emojis:
            await message.add_reaction(emoji)

    async def update_board(self, user, message):
        board = self.format_board(user.id)
        game = self.get_game(user.id)
        title = f"Level {game.level_id}" if game.random_levels else "Custom Level"
        embed = discord.Embed(title=title, description=board, color=discord.Color.red())
        await message.edit(embed=embed)


class GameManager:
    def __init__(self, level_id, emoji_player, file=None, content=None, text=None):
        self.col = 0
        self.row = 0
        self.level_id = level_id
        self.emoji_player = emoji_player
        self.random_levels = (not (file or content or text))

        if self.random_levels:
            self.board = RandomBoard(5, 5, int(self.level_id), int(self.level_id)).board
        else:
            board = CustomBoard(file, content, text)
            checks = board.check_for_validity()
            error_message = ""
            for key in checks.keys():
                if checks[key] is not None:
                    error_message += checks[key] + "\n"
            if error_message:
                raise GameError(error_message)
            else:
                self.board = board.board

        self.initial_board = copy.deepcopy(self.board)
        self.saved = (content is not None)
        self.find_player()
        self.width = len(self.board)
        self.height = len(self.board[0])

        self.reactions = {"➡️": {"col": 0, "row": 1}, "⬅️": {"col": 0, "row": -1}, "⬇️": {"col": 1, "row": 0}, "⬆️": {"col": -1, "row": 0}}
        self.immovable = ["wall", "enemy"]
        self.movable = ["box", "completed_box"]

    @property
    def next_level(self):
        return str(int(self.level_id) + 1)

    def find_player(self):
        for col in range(len(self.board)):
            column = self.board[col]
            for row in range(len(column)):
                if column[row] == "player":
                    self.col = col
                    self.row = row

    def reset(self):
        self.board = copy.deepcopy(self.initial_board)
        self.find_player()

    async def move(self, emoji):
        to_move = self.reactions[emoji]
        after_col = self.col + to_move["col"]
        after_row = self.row + to_move["row"]
        if (after_col > self.width - 1 or after_col < 0) or (after_row > self.height - 1 or after_row < 0):
            return
        new_space = self.board[after_col][after_row]
        if new_space in self.immovable:
            return
        if new_space in self.movable:
            box = (after_col + to_move["col"], after_row + to_move["row"])
            if (box[0] > self.width - 1 or box[0] < 0) or (box[1] > self.height - 1 or box[1] < 0):
                return
            new_space_box = self.board[box[0]][box[1]]
            if new_space_box in self.immovable or new_space_box == "box":
                return
            self.board[box[0]][box[1]] = "box" if not self.initial_board[after_col + to_move["col"]][after_row + to_move["row"]] == "goal" else "completed_box"
        self.board[self.col][self.row] = "empty" if self.initial_board[self.col][self.row] in ("box", "player", "enemy") \
            else self.initial_board[self.col][self.row]
        self.board[after_col][after_row] = "player"
        self.col = after_col
        self.row = after_row
        self.move_enemies()
        return self.check_for_win()

    def find_enemies(self):
        enemies = list()
        for col in range(len(self.board)):
            column = self.board[col]
            for row in range(len(column)):
                if column[row] == "enemy":
                    enemies.append({"col": col, "row": row})
        return enemies

    def move_enemies(self):
        for enemy in self.find_enemies():
            def move(width, height):
                to_move = {"col": 0, "row": 0}
                num = random.randint(-1, 1)
                to_move[random.choice(["col", "row"])] = num
                return max(min(enemy["col"] + to_move["col"], width - 1), 0), max(min(enemy["row"] + to_move["row"], height - 1), 0)
            after_col, after_row = move(self.width, self.height)
            iters = 0
            while self.board[after_col][after_row] in ("box", "completed_box", "wall", "enemy", "player"):
                after_col, after_row = move(self.width, self.height)
                iters += 1
                if iters == 10:
                    break
            self.board[enemy["col"]][enemy["row"]] = "empty" if self.initial_board[enemy["col"]][enemy["row"]] in ("box", "player", "enemy") \
                else self.initial_board[enemy["col"]][enemy["row"]]
            self.board[after_col][after_row] = "enemy"

    def check_for_win(self):
        for row in self.board:
            for entry in row:
                if entry == "goal":
                    return False
        for col in range(len(self.initial_board)):
            for row in range(len(self.initial_board[col])):
                if self.initial_board[col][row] == "goal":
                    if self.board[col][row] == "player":
                        return False
        return True


class RandomBoard:
    def __init__(self, width, height, boxes, level):
        self.max_boxes = 10
        self.box_count = round(boxes * .51) if (round(boxes * .51) <= self.max_boxes) else self.max_boxes
        self.level = level
        self.enemy_count = 1 * ((int(self.level) >= 10) + (int(self.level) >= 100))
        self.max_width = 9
        self.max_height = 9
        self.width = round(width + (.15 * level)) if not round(width + (.2 * level)) > self.max_width else self.max_width
        self.height = round(height + (.1 * level)) if not round(height + (.2 * level)) > self.max_height else self.max_height
        self.board = [["empty" for _ in range(self.width)] for _ in range(self.height)]
        self.place_boxes()
        self.place_player()
        self.place_enemies()

    def place_boxes(self):
        for _ in range(self.box_count):
            for idx in range(2):
                x = random.randint(0 + idx, self.height - idx - 1)
                y = random.randint(0 + idx, self.width - idx - 1)
                while self.board[x][y] != "empty":
                    x = random.randint(0 + idx, self.height - idx - 1)
                    y = random.randint(0 + idx, self.width - idx - 1)
                self.board[x][y] = ("goal", "box")[idx]

    def place_player(self):
        x = random.randint(1, self.height - 2)
        y = random.randint(1, self.width - 2)
        while self.board[x][y] != "empty":
            x = random.randint(1, self.height - 2)
            y = random.randint(1, self.width - 2)
        self.board[x][y] = "player"

    def place_enemies(self):
        for _ in range(self.enemy_count):
            x = random.randint(0, self.height - 1)
            y = random.randint(0, self.width - 1)
            while self.board[x][y] != "empty":
                x = random.randint(0, self.height - 1)
                y = random.randint(0, self.width - 1)
            self.board[x][y] = "enemy"


class CustomBoard:
    def __init__(self, file=None, board=None, text=None):
        self.file = file
        self.text = text
        self.valid_tiles = ["player", "box", "empty", "goal", "wall", "enemy"]
        if self.file:
            self.content = self.file.decode("utf-8")
            self.board = [[re.sub("\r", "", i) for i in k.split(" ")] for k in self.content.split("\n")]
            self.remove_invalid_tiles()
        if self.text:
            self.board = [[re.sub("\r", "", i) for i in k.split(" ")] for k in self.text.split("\n")]
            self.remove_invalid_tiles()
        elif board:
            self.board = copy.deepcopy(board)

    def check_for_validity(self):
        checks = {"box_to_goal": None, "no_boxes_or_goals": None, "player_error": None,
                  "ratio": None, "box_corner": None}
        box_to_goal = [0, 0]
        player = 0
        for col in self.board:
            for entry in col:
                if entry == "box":
                    box_to_goal[0] += 1
                if entry == "goal":
                    box_to_goal[1] += 1
                if entry == "player":
                    player += 1
        if box_to_goal[0] != box_to_goal[1]:
            checks["box_to_goal"] = f"Box amount [{box_to_goal[0]}] is not equal to goal amount [{box_to_goal[1]}], rendering level impossible."
        if box_to_goal[0] == 0 or box_to_goal[1] == 0:
            checks["no_boxes_or_goals"] = "No boxes or goals are included in the level"
        if player == 0 or player > 1:
            checks["player_error"] = "Either none or more than one player tile included in the level"
        width = len(self.board[0])
        for col in self.board[1:]:
            if len(col) != width:
                checks["ratio"] = "All rows are not the same width as each other."
                break
        for x, y in ((0, 0), (0, -1), (-1, 0), (-1, -1)):
            if self.board[x][y] == "box":
                checks["box_corner"] = "A box is placed in a corner, rendering the level impossible"
        return checks

    def remove_invalid_tiles(self):
        for entry in self.board:
            if entry == [""]:
                self.board.remove(entry)
        for col in range(len(self.board)):
            for row in range(len(self.board[col])):
                if self.board[col][row] not in self.valid_tiles:
                    self.board[col][row] = "empty"


class GameError(BaseException):
    def __init__(self, message):
        self.message = message
