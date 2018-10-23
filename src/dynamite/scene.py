import operator
import pyglet.resource
import pyglet.graphics
import pyglet.sprite

from .coords import map_to_screen


class Scene:
    def __init__(self):
        self.objects = set()
        self.batch = pyglet.graphics.Batch()

        Tree.load()
        Bomb.load()
        Player.load()
        Explosion.load()

    def clear(self):
        self.objects.clear()
        self.batch = pyglet.graphics.Batch()

    def draw(self):
        self.batch.invalidate()
        self.batch.draw()

    def spawn_tree(self, position, sprite='fir-tree'):
        return Tree(self, position, sprite)

    def spawn_bomb(self, position, sprite='timed-bomb'):
        return Bomb(self, position, sprite)

    def spawn_player(self, position, sprite='pc-up'):
        return Player(self, position, sprite)

    def spawn_explosion(self, position):
        Explosion(self, position)



# Indicate an animation
class ImageSequence:
    def __init__(
            self,
            name,
            frames,
            delay=0.1,
            anchor_x=0,
            anchor_y=0,
            loop=False):
        self.name = name
        self.frames = frames
        self.delay = delay
        self.loop = loop
        self.anchor_x = anchor_x
        self.anchor_y = anchor_y

    def load(self):
        img = pyglet.resource.image(f'{self.name}.png')
        grid = pyglet.image.ImageGrid(
            img,
            rows=1,
            columns=self.frames
        )

        images = list(grid)
        for img in images:
            if self.anchor_x == 'center':
                img.anchor_x = img.width // 2
            else:
                img.anchor_x = self.anchor_x
            if self.anchor_y == 'center':
                img.anchor_y = img.height // 2
            else:
                img.anchor_y = self.anchor_y

        return pyglet.image.Animation.from_image_sequence(
            images,
            self.delay,
            loop=self.loop
        )


class Actor:
    @classmethod
    def load(cls):
        if hasattr(cls, 'sprites'):
            return
        cls.sprites = {}
        for spr in cls.SPRITES:
            if isinstance(spr, ImageSequence):
                s = cls.sprites[spr.name] = spr.load()
            else:
                s = cls.sprites[spr] = pyglet.resource.image(f'{spr}.png')
                s.anchor_x = s.width // 2
                s.anchor_y = 10

    def __init__(self, scene, position, sprite_name='default'):
        """Do not use this constructor - use methods of Scene."""
        x, y = map_to_screen(position)
        self.sprite = pyglet.sprite.Sprite(
            self.sprites[sprite_name],
            x, y,
            group=pyglet.graphics.OrderedGroup(-y),
            batch=scene.batch,
        )
        self.anim = sprite_name

        self._pos = position
        self.scene = scene
        self.scene.objects.add(self)

    def play(self, name):
        self.sprite.image = self.sprites[name]
        self.anim = name

    @property
    def position(self):
        return self._pos

    @position.setter
    def position(self, v):
        x, y = map_to_screen(v)
        self._pos = v
        if not self.scene:
            return
        self.sprite.position = x, y
        self.sprite.group = pyglet.graphics.OrderedGroup(-y)

    def delete(self):
        self.scene.objects.remove(self)
        self.sprite.delete()
        self.scene = None


class Player(Actor):
    SPRITES = [
        'pc-up',
        'pc-down',
        'pc-left',
        'pc-right',
    ]

    def set_orientation(self, d):
        self.play(f'pc-{d.get_sprite()}')


class Bomb(Actor):
    SPRITES = [
        'timed-bomb',
        'timed-bomb-red',
        'freeze-bomb',
        'contact-bomb',
        ImageSequence(
            'timed-bomb-float',
            frames=2,
            delay=1.1,
            anchor_x='center',
            anchor_y=14,
            loop=True,
        ),
        ImageSequence(
            'timed-bomb-float-red',
            frames=2,
            delay=1.1,
            anchor_x='center',
            anchor_y=14,
            loop=True,
        )
    ]
    red = False

    def toggle_red(self):
        """Flip the bomb sprite to/from red."""
        if self.red:
            img = self.sprites[self.anim]
        else:
            img = self.sprites[f'{self.anim}-red']

        # There is no method to replace an animation in a sprite, keeping
        # the current frame, so do this using the internals of the Sprite
        # class - see
        # https://bitbucket.org/pyglet/pyglet/src/de3608deb882c0719f231880ecb07f7d4bb58cb6/pyglet/sprite.py#lines-356
        if isinstance(img, pyglet.image.Animation):
            self.sprite._animation = img
            frame = self.sprite._frame_index
            self.sprite._set_texture(img.frames[frame].image.get_texture())
        else:
            self.sprite.image = img

        self.red = not self.red


class Explosion(Actor):
    SPRITES = [
        ImageSequence(
            'explosion',
            frames=9,
            delay=0.02,
            anchor_x=53,
            anchor_y=39,
        ),
    ]
    def __init__(self, scene, position):
        super().__init__(scene, position, 'explosion')
        self.sprite.on_animation_end = self.delete
        self.sprite.scale = 2.0


class Tree(Actor):
    SPRITES = [
        'fir-tree',
    ]