import sublime
import sublime_plugin
import random
import time
import copy
import threading


game_ctrl = None
# ----------------------------------------------------------
# Const
# ----------------------------------------------------------
FPS = 24
BLOCK_DOWN_TIME = 0.3
BOARD_WIDTH = 11
BOARD_HEIGHT = 15


class TileType():
    EMPTY = 0
    BLOCK = 1


class Pos():
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y

    def __str__(self):
        return '(%s, %s)' % (self.x, self.y)

    def __add__(self, other):
        return Pos(self.x + other.x, self.y + other.y)


class Direction():
    up = Pos(0, -1)
    down = Pos(0, 1)
    left = Pos(-1, 0)
    right = Pos(1, 0)


class RenderStatus():
    UPDATE = 'update'
    STOP = 'stop'
    FINISH = 'finish'


class ViewSettings():
    isGameTetris = "isGameTetris"


# ----------------------------------------------------------
def _delay(time, func):
    t = threading.Timer(time, func)
    t.start()

# ----------------------------------------------------------
class TetrisRender(sublime_plugin.TextCommand):
    def run(self, edit, **args):
        cmd = args.get('cmd', RenderStatus.STOP)
        data = args.get('data', None)

        if cmd == RenderStatus.UPDATE:
            self.update(edit, data)
        elif cmd == RenderStatus.STOP:
            self.stop()
        elif cmd == RenderStatus.FINISH:
            self.finish()

    def update(self, edit, data):
        tiles = data.get('tiles')
        prepare_tiles = data.get('prepare_tiles')

        # clear view content
        region = sublime.Region(0, self.view.size())
        self.view.erase(edit, region)

        content = ''
        for a in range(0, 4):
            for b in range(0, 4):
                if prepare_tiles[b][a] == TileType.EMPTY:
                    content += ' '
                else:
                    content += '*'
            content += '\n'

        content += '\n'
        content += '.' * (BOARD_WIDTH + 1)
        content += '\n'
        for a in range(0, BOARD_HEIGHT - 1):
            content += '.'
            for b in range(0, BOARD_WIDTH - 1):
                if tiles[b][a] == TileType.EMPTY:
                    content += ' '
                else:
                    content += '*'
            content += '.' + '\n'
        content += '.' * (BOARD_WIDTH + 1)

        self.view.insert(edit, 0, content)

    def stop(self):
        pass

    def finish(self):
        pass


class Timer():
    def __init__(self, cmd):
        self.flag = False
        self.cmd = cmd
        self.last_time = time.time()

    def update(self):
        if self.flag is False: return

        self.cmd(time.time() - self.last_time)
        self.last_time = time.time()

        _delay(1 / FPS, self.update)

    def start(self):
        self.flag = True
        self.update()

    def stop(self):
        self.flag = False


# ----------------------------------------------------------
# Model
# ----------------------------------------------------------
class BlockFactory():
    def __init__(self):
        """
                      y:
        [00 01|02 03] -2
        [04 05|06 07] -1
        ------O------
        [08 09|10 11] 0
        [12 13|14 15] 1
       x:-2 -1  0  1

        Pos(-2, -2), Pos(-1, -2), Pos(0, -2), Pos(1, -2),
        Pos(-2, -1), Pos(-1, -1), Pos(0, -1), Pos(1, -1),
        Pos(-2, 0), Pos(-1, 0), Pos(0, 0), Pos(1, 0),
        Pos(-2, 1), Pos(-1, 1), Pos(0, 1), Pos(1, 1)
        """
        self.index_pos_map = [
            Pos(-2, -2), Pos(-1, -2), Pos(0, -2), Pos(1, -2),
            Pos(-2, -1), Pos(-1, -1), Pos(0, -1), Pos(1, -1),
            Pos(-2, 0), Pos(-1, 0), Pos(0, 0), Pos(1, 0),
            Pos(-2, 1), Pos(-1, 1), Pos(0, 1), Pos(1, 1)
        ]
        """
        [00 01 02 03]
        [04 ** ** 07]
        [08 ** ** 11] --> 5 6 9 10
        [12 13 14 15]

        [00 01 02 03]
        [04 ** 06 07]
        [** ** ** 11] --> 5 8 9 10
        [12 13 14 15]
        """
        self.block_type = [
            [5, 6, 9, 10], # 2*2
            [5, 8, 9, 10], # T
            [1, 5, 9, 10], # L
            [2, 6, 9, 10], # L
            [1, 5, 9, 13], # 1*4
        ]

    def _change_index_to_pos(self, index):
        return self.index_pos_map[index]

    def get_amount(self):
        return len(self.block_type)

    def create(self):
        block_id = random.randint(0, self.get_amount() - 1)
        tiles = []
        for index in self.block_type[block_id]:
            tile = self._change_index_to_pos(index)
            tiles.append(tile)
        return tiles


def _turn_pos(p):
    if str(p) == '(-2, -2)': return Pos(-2, 1)
    if str(p) == '(-1, -2)': return Pos(-2, 0)
    if str(p) == '(0, -2)': return Pos(-2, -1)
    if str(p) == '(1, -2)': return Pos(-2, -2)
    if str(p) == '(-2, -1)': return Pos(-1, 1)
    if str(p) == '(-1, -1)': return Pos(-1, 0)
    if str(p) == '(0, -1)': return Pos(-1, -1)
    if str(p) == '(1, -1)': return Pos(-1, -2)
    if str(p) == '(-2, 0)': return Pos(0, 1)
    if str(p) == '(-1, 0)': return Pos(0, 0)
    if str(p) == '(0, 0)': return Pos(0, -1)
    if str(p) == '(1, 0)': return Pos(0, -2)
    if str(p) == '(-2, 1)': return Pos(1, 1)
    if str(p) == '(-1, 1)': return Pos(1, 0)
    if str(p) == '(0, 1)': return Pos(1, -1)
    if str(p) == '(1, 1)': return Pos(1, -2)
    sublime.error_message('turn_pos errer')


def check_pos_valid(pos):
    if pos.x >= BOARD_WIDTH - 1 or pos.x < 0: return False
    if pos.y >= BOARD_HEIGHT - 1: return False
    return True


class Board():
    def __init__(self):
        # create game view
        self.game_view = sublime.active_window().new_file()
        self.game_view.set_scratch(True)

        # view setting
        setting = self.game_view.settings()
        setting.set(ViewSettings.isGameTetris, True)

        # Block Factory
        self.block_factory = BlockFactory()

        # member variable
        self.update_time = 0
        self.prepare_blocks = []
        self.blocks = []
        self.tiles = [[TileType.EMPTY for x in range(BOARD_HEIGHT)]
                      for x in range(BOARD_WIDTH)]

        self.create_block()
        self.create_block()

    def create_block(self):
        self.blocks = self.prepare_blocks
        self.block_pos = Pos(BOARD_WIDTH // 2, 0)
        self.prepare_blocks = self.block_factory.create()

        self.prepare_tiles = [[TileType.EMPTY for x in range(4)]
                      for x in range(4)]

        for tile in self.prepare_blocks:
            pos = Pos(2,2) + tile
            self.prepare_tiles[pos.x][pos.y] = TileType.BLOCK


    def merge_board(self, is_really=False):
        if is_really:
            tiles = copy.copy(self.tiles)
        else:
            tiles = copy.deepcopy(self.tiles)

        for tile in self.blocks:
            pos = tile + self.block_pos
            if check_pos_valid(pos) == False: continue
            tiles[pos.x][pos.y] = TileType.BLOCK
        return tiles

    def refresh_view(self):
        args = {
            "cmd": RenderStatus.UPDATE,
            "data": {
                "tiles": self.merge_board(),
                "prepare_tiles": self.prepare_tiles,
            }
        }
        # TetrisRender
        self.game_view.run_command('tetris_render', args)

    def update(self, dt):
        self.update_time += dt
        if self.update_time < BLOCK_DOWN_TIME: return
        self.update_time = 0

        self.block_down()
        self.refresh_view()

    def check_contain(self, tiles):
        for tile in tiles:
            if self.tiles[tile.x][tile.y] is TileType.BLOCK:
                return False
        return True

    def check_block_move(self, dir):
        new_pos = self.block_pos + dir
        tiles = []
        for tile in self.blocks:
            pos = new_pos + tile
            if check_pos_valid(pos) == False: return False
            tiles.append(pos)

        return self.check_contain(tiles)

    def turn_block(self):
        tiles = []
        for tile in self.blocks:
            pos = _turn_pos(tile)
            if check_pos_valid(self.block_pos + pos) == False: return False
            tiles.append(pos)

        if self.check_contain(tiles):
            self.blocks = tiles
            self.refresh_view()

    def block_up(self):
        self.turn_block()

    def block_down(self):
        if self.check_block_move(Direction.down):
            self.block_pos = self.block_pos + Direction.down
            self.refresh_view()
        else:
            self.merge_board(True)

            # check game over
            if self.block_pos.y <= 1:
                global game_ctrl
                game_ctrl.finish()
                return
            self.create_block()
            self.refresh_view()

    def block_left(self):
        if self.check_block_move(Direction.left):
            self.block_pos = self.block_pos + Direction.left
            self.refresh_view()

    def block_right(self):
        if self.check_block_move(Direction.right):
            self.block_pos = self.block_pos + Direction.right
            self.refresh_view()


    def finish(self):
        def _done(y):
            if y < 0: return
            for x in range(BOARD_WIDTH):
                self.tiles[x][y] = TileType.BLOCK
            self.refresh_view()
            _delay(0.1, lambda: _done(y - 1))
        _done(BOARD_HEIGHT - 1)


# ----------------------------------------------------------
# Controller
# ----------------------------------------------------------
class GameControl():
    def __init__(self):
        self.board = Board()
        self.timer = Timer(self.update)

    def update(self, dt):
        self.board.update(dt)

    def start(self):
        self.timer.start()

    def pause(self):
        self.timer.stop()

    def finish(self):
        self.timer.stop()
        self.board.finish()

    def block_up(self):
        self.board.block_up()

    def block_down(self):
        self.board.block_down()

    def block_left(self):
        self.board.block_left()

    def block_right(self):
        self.board.block_right()


class TetrisGame(sublime_plugin.TextCommand):
    def run(self, edit):
        global game_ctrl
        game_ctrl = GameControl()
        game_ctrl.start()


class TetrisOperation(sublime_plugin.WindowCommand):
    def run(self, **args):
        operation = args.get('operation')
        if operation == 'up':
            game_ctrl.block_up()
        elif operation == 'down':
            game_ctrl.block_down()
        elif operation == 'left':
            game_ctrl.block_left()
        elif operation == 'right':
            game_ctrl.block_right()
