#!/usr/bin/env python3
from enum import Enum
from pathlib import Path
from pyglet import gl
import pyglet.window.key as key
import pyglet.window.key
import pyglet.resource
import sys
import time
import datetime
import itertools


logic_interval = 1/10

typematic_interval = 1/4
typematic_delay = 1

# please ensure all the other intervals
# are evenly divisible into this interval
callback_interval = 1/20


srcdir = Path(__file__).parent
pyglet.resource.path = [
    'images',
]
pyglet.resource.reindex()

remapped_keys = {
    key.W: key.UP,
    key.A: key.LEFT,
    key.S: key.DOWN,
    key.D: key.RIGHT,
    key.UP: key.UP,
    key.LEFT: key.LEFT,
    key.DOWN: key.DOWN,
    key.RIGHT: key.RIGHT,
    key.ESCAPE: key.ESCAPE,
    key.ENTER: key.ENTER,
    }
interesting_key = remapped_keys.get

_key_repr = {
    key.UP: "Up",
    key.LEFT: "Left",
    key.DOWN: "Down",
    key.RIGHT: "Right",
    key.ESCAPE: "Escape",
    key.ENTER: "Enter",
    }
key_repr = _key_repr.get

map_legend = {}

def legend(c):
    assert len(c) == 1
    assert c not in map_legend
    def decorator(klass):
        map_legend[c] = klass
        klass.legend = c
        return klass
    return decorator

class MapTile:
    pass

@legend(".")
class MapWater(MapTile):
    pass

@legend("^")
class MapWaterCurrentUp(MapWater):
    pass

@legend("X")
class MapBlockage(MapTile):
    pass

@legend("#")
class MapLand(MapTile):
    pass

@legend("S")
class MapSpawnPoint(MapTile):
    pass

map_text = """
......X.......................
.##.##^.......................
.##.##^.......................
.##.##^.......................
.##.##^.......................
.##.##^.......................
.S#.##^.......................
.##.##........................
..............................
"""
# .S#.##^.......................
# .S###########################.

map = []

for line in map_text.strip().split("\n"):
    a = []
    map.append(a)
    for c in line:
        a.append(map_legend[c]())

for line in map:
    assert len(line) == len(map[0])

# the map is currently map[y][x].
# now rotate map so x is first instead of y.
# and index by tuple rather than nested list.
# so that we get map[x, y]
# (which is what tmx gives us)
map_width = len(map[0])
map_height = len(map)

new_map = {}
for y, line in enumerate(map):
    for x, tile in enumerate(line):
        new_map[x, y] = tile

map = new_map

class GameState(Enum):
    INVALID = 0
    MAIN_MENU = 1
    LOADING = 2
    PRESHOW = 3
    PLAYING = 4
    PAUSED = 5
    LEVEL_COMPLETE = 6
    GAME_OVER = 7
    GAME_WON = 8
    CONFIRM_EXIT = 9


class Ticker:
    def __init__(self, name, frequency, callback, *, delay=0):
        assert isinstance(frequency, (int, float)) and frequency, "must supply a valid (nonzero) frequency!  got " + repr(frequency)
        self.name = name
        self.frequency = frequency
        self.callback = callback
        # initial delay
        self.delay = delay
        self.reset()

    # dt is fractional seconds e.g. 0.001357
    def advance(self, dt):
        self.accumulator += dt
        self.elapsed += dt
        callbacks = 0
        while self.accumulator >= self.next:
            self.callback()
            self.counter += 1
            callbacks += 1
            self.accumulator -= self.next
            self.next = self.frequency
        return callbacks

    def reset(self):
        self.counter = 0
        self.elapsed = self.accumulator = 0.0
        self.next = self.delay or self.frequency


_log = []
log_start = time.time()
def log(*a):
    t = time.time()
    s = " ".join(str(x) for x in a)
    _log.append((t, s))

def dump_log():
    print()
    for t, s in _log:
        t -= log_start
        print(f"[{t:8.4f}] {s}")

class Game:
    def __init__(self):
        self.repeater = None

        self.start = time.time()

        self.old_state = self.state = GameState.INVALID
        self.transition_to(GameState.PLAYING)

        # self.renders = Ticker("render", 1/4, self.render)
        self.last_render = -1000
        self.renders = 0

        self.logics = Ticker("logic", logic_interval, self.logic)

        self.key_handler = self

        def make_repeater(key):
            def callback():
                self.on_key(key)
            return callback

        self.repeaters = {}
        for k in (
            key.UP,
            key.DOWN,
            key.LEFT,
            key.RIGHT,
            ):
            rk = make_repeater(k)
            repeater = Ticker(key_repr(k) + " repeater", typematic_interval, rk, delay=typematic_delay)
            repeater.key = k
            self.repeaters[k] = repeater

    def timer(self, dt):
        if self.repeater:
            self.repeater.advance(dt)

        if self.state == GameState.PLAYING:
            self.logics.advance(dt)


    def on_state_PLAYING(self):
        pass

    def transition_to(self, new_state):
        _, _, name = str(new_state).rpartition(".")
        handler = getattr(self, "on_state_" + name, None)
        if handler:
            handler()

    def render(self):
        self.renders += 1
        level.render()

    def logic(self):
        pass

    def on_key_press(self, k, modifier):
        k = interesting_key(k)
        if k:
            # simulate typematic ourselves
            # (we can't use pyglet's on_text_motion because we want this for WASD too)
            repeater = game.repeaters.get(k)
            if repeater:
                repeater.reset()
                self.repeater = repeater
            return self.key_handler.on_key(k)

    def on_key_release(self, k, modifier):
        k = interesting_key(k)
        if k:
            if self.repeater and self.repeater.key == k:
                self.repeater = None

    def on_key(self, k):
        k = interesting_key(k)
        assert k
        if k:
            return self.key_handler.on_key(k)


class Level:
    def __init__(self):
        self.start = time.time()
        self.player = Player()
        self.map = {}
        for y in range(map_height):
            for x in range(map_width):
                coord = x, y
                tile = map[coord]
                if isinstance(tile, MapSpawnPoint):
                    self.player.position = coord
                    tile = MapLand()
                self.map[coord] = tile


key_to_movement_delta = {
    key.UP:    ( 0, -1),
    key.DOWN:  ( 0, +1),
    key.LEFT:  (-1,  0),
    key.RIGHT: (+1,  0),
    }

class Player:
    def __init__(self):
        game.key_handler = self

    def on_key(self, k):
        delta = key_to_movement_delta.get(k)
        if not delta:
            return
        x, y = self.position
        delta_x, delta_y = delta
        new_position = x + delta_x, y + delta_y
        leap_position = x + (delta_x * 2), y + (delta_y * 2)
        tile = map.get(new_position)
        if (not tile) or isinstance(tile, MapWater):
            new_position = leap_position
            tile = map.get(new_position)
            if (not tile) or isinstance(tile, MapWater):
                return
        self.position = new_position



window = pyglet.window.Window()
game = Game()
level = Level()


def screenshot_path():
    root = Path.cwd()
    grabs = root / 'grabs'
    grabs.mkdir(exist_ok=True)
    day = (datetime.date.today() - datetime.date(2018, 10, 20)).days
    for n in itertools.count(1):
        path = grabs / f'day{day}-{n}.png'
        if not path.exists():
            return str(path)


@window.event
def on_key_press(k, modifiers):
    if k == key.F12:
        gl.glPixelTransferf(gl.GL_ALPHA_BIAS, 1.0)  # don't transfer alpha channel
        image = pyglet.image.ColorBufferImage(0, 0, window.width, window.height)
        image.save(screenshot_path())
        gl.glPixelTransferf(gl.GL_ALPHA_BIAS, 0.0)  # restore alpha channel transfer
    return game.on_key_press(k, modifiers)

@window.event
def on_key_release(k, modifiers):
    return game.on_key_release(k, modifiers)


def load_pc(name):
    """Load a PC sprite and set the anchor position."""
    pc = pyglet.resource.image(name)
    pc.anchor_x = pc.width // 2
    pc.anchor_y = 10
    return pc


def load_tile(name):
    """Load a ground tile and set the anchor position."""
    img = pyglet.resource.image(name)
    img.anchor_x = img.width // 2
    img.anchor_y = img.height // 2
    return img


pc = load_pc('pc-s.png')
grass = load_tile('grass.png')
spr = pyglet.sprite.Sprite(pc)


def map_to_screen(pos):
    x, y = pos
    return x * 64 + 100, window.height - 100 - y * 40


@window.event
def on_draw():
    gl.glClearColor(0.5, 0.55, 0.8, 0)
    window.clear()
    for y in range(map_height):
        for x in range(map_width):
            coord = x, y
            t = level.map.get(coord)
            if isinstance(t, MapLand):
                grass.blit(*map_to_screen(coord))

    spr.position = map_to_screen(level.player.position)
    spr.draw()


def timer_callback(dt):
    game.timer(dt)


pyglet.clock.schedule_interval(timer_callback, callback_interval)
pyglet.app.run()

# dump_log()