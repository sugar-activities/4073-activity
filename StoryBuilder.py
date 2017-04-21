# Copyright 2007-2008 World Wide Workshop Foundation
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.
#
# If you find this activity useful or end up using parts of it in one of
# your own creations we would love to hear from you at
# info@WorldWideWorkshop.org !
#

import gtk
import os, sys
import random
import pickle
import time
import logging

from datetime import date
from gettext import gettext as _
from olpcgames import eventwrap

import pygame
from pygame.locals import *

from storytheme import theme_list, theme_defs

from pgu import text
from pgu import gui
from pgu import html

from sugar.graphics import style

FPS = 30  # Frames Per Second

ORIG_WIDTH = 1024
ORIG_HEIGHT = 700

FACTOR = min((gtk.gdk.screen_width() / float(ORIG_WIDTH)),
        (gtk.gdk.screen_height()-style.MEDIUM_ICON_SIZE) / float(ORIG_HEIGHT))

def scale(x):
    if isinstance(x, int):
        return int(x * FACTOR)
    return tuple([scale(i) for i in x])

GAME_WIDTH = scale(ORIG_WIDTH)
GAME_HEIGHT = scale(ORIG_HEIGHT)

CHAR_PANEL_SIZE = 5

# button positions
CHARACTER_BAR_UP = pygame.rect.Rect(scale((46, 93, 46, 33)))
CHARACTER_BAR_DOWN = pygame.rect.Rect(scale((46, 491, 46, 33)))
CLEAR = pygame.rect.Rect(scale((932, 435, 46, 33)))
SOUND = pygame.rect.Rect(scale((932, 114, 46, 33)))
THEME_LEFT = pygame.rect.Rect(scale((410, 506, 46, 33)))
THEME_RIGHT = pygame.rect.Rect(scale((567, 506, 46, 33)))
TEXTAREA = pygame.rect.Rect(scale((62, 560, 875, 114)))

def load_image(name, (x, y)=(None, None)):
    """Load an image from a specific file.

    name -- string, filename relative to data/
    (x, y) -- optional tuple of required size
    """
    fullname = os.path.join('data', name)
    image = pygame.image.load(fullname).convert_alpha()
    if x and y:
        image = pygame.transform.scale(image, (scale(x), scale(y)))
    return image, image.get_rect()

def load_sound(name):
    fullname = os.path.join('data', name)
    sound = pygame.mixer.Sound(fullname)
    return sound


class Background(pygame.sprite.Sprite):
    """Background image for Story."""

    def __init__(self, theme, layout):
        """Load the background.
        
        theme -- Theme object
        layout -- sprite to align with
        """
        pygame.sprite.Sprite.__init__(self)
        self.image, self.rect = load_image(theme.background,
                                           (754, 393))
        x = layout.rect.left + scale(153)
        y = layout.rect.top + scale(95)
        self.rect.topleft = (x, y)


class ButtonBar:
    """Manage which CharacterButtons are visible"""

    def __init__(self, buttonlist, layout, spritegroup):
        """Create the ButtonBar.

        buttonlist -- list of CharacterButtons
        layout -- sprite to align with
        """
        self.buttonlist = buttonlist
        self.layout = layout
        self.spritegroup = spritegroup
        # We can display CHAR_PANEL_SIZE buttons at a time
        self.startbutton = 0
        self.show()

    def coord(self, index):
        """Return the coordinates for placing a CharacterButton.

        index -- integer from 0 to 4

        returns (x, y)
        """
        if int(index) not in range(0,CHAR_PANEL_SIZE):
            raise ValueError, "index out of range"
        x = scale(37)
        y = scale(138) + scale(index*70)
        try:
            x += self.layout.rect.left
            y += self.layout.rect.top
        except AttributeError:
            pass  # fail safely if layout has no rect
        return (x, y)

    def up(self):
        """Show previous CHAR_PANEL_SIZE buttons"""
        self.startbutton -= CHAR_PANEL_SIZE
        if self.startbutton < 0:
            buttons = len(self.buttonlist)
            if buttons % CHAR_PANEL_SIZE:
                highest = buttons / CHAR_PANEL_SIZE * CHAR_PANEL_SIZE
            else:
                highest = (buttons / CHAR_PANEL_SIZE) - 1
            self.startbutton = highest
        self.show()

    def down(self):
        """Show next CHAR_PANEL_SIZE buttons"""
        self.startbutton += CHAR_PANEL_SIZE
        if self.startbutton >= len(self.buttonlist):
            self.startbutton = 0
        self.show()

    def show(self):
        """Show the current CHAR_PANEL_SIZE buttons"""
        self.spritegroup.empty()
        self.current_buttons = self.buttonlist[
            self.startbutton:self.startbutton+CHAR_PANEL_SIZE]
        for index in range(0, len(self.current_buttons)):
            button = self.current_buttons[index]
            button.rect.topleft = self.coord(index)
            self.spritegroup.add(button)


class Character(pygame.sprite.Sprite):
    """An animated character."""

    def __init__(self, name, frames, sound=None, soundname=None,
                 coords=None):
        """Create a Character.

        name -- string identifying which character
        frames -- list of dicts of index, image, delay
        coords -- optional tuple: (x, y) coordinates
        """
        pygame.sprite.Sprite.__init__(self)
        self.name = name
        self.frames = []
        if sound:
            self.sound = sound
        elif soundname:
            self.sound = load_sound(soundname)
        else:
            self.sound = None
        self.image = None
        self.rect = None
        self.delay = None
        self.active_frame = None
        self.mouse_pos = (0, 0)
        self.make_frames(frames)
        self.moving = True  # it moves as soon as we create it
        self.id = pygame.time.get_ticks()  # unique-ish id
        self.last_animated = pygame.time.get_ticks()
        if coords:
            self.rect.topleft = coords

    def __str__(self):
        return 'Character %s' % self.id

    def make_frames(self, frames):
        """Load the images for the animated frames."""
        for frame in frames:
            image, rect = load_image(frame['image'], (241, 189))
            if not self.rect:
                self.rect = rect
            self.frames.append((image, frame['delay']))
        self.active_frame = 0
        self.image, self.delay = self.frames[self.active_frame]

    def next_frame(self):
        """Use the next image for the animation."""
        if self.active_frame is not None:
            self.active_frame += 1
            self.active_frame %= len(self.frames)
            self.image, self.delay = self.frames[self.active_frame]

    def update(self):
        """Called periodically to update position or animation."""
        if self.moving:
            pos = pygame.mouse.get_pos()
            if self.mouse_pos == (0, 0):
                self.rect.center = pos
            else:
                x = pos[0] - self.mouse_pos[0]
                y = pos[1] - self.mouse_pos[1]
                self.rect.topleft = (x, y)
        now = pygame.time.get_ticks()
        if now > (self.last_animated + self.delay):
            self.next_frame()
            self.last_animated = now

    def stick(self):
        """Make Character stop moving."""
        self.moving = False
        self.mouse_pos = (0, 0)

    def is_mouse_over(self):
        """Check if the mouse pointer is over the sprite."""
        return self.rect.collidepoint(pygame.mouse.get_pos())

    def click(self):
        """Calculate relative mouse position for drag and drop"""
        mouse_pos = pygame.mouse.get_pos()
        x = mouse_pos[0] - self.rect.left
        y = mouse_pos[1] - self.rect.top
        self.mouse_pos = (x, y)
        self.play()

    def play(self):
        """Play sound"""
        if self.sound:
            self.sound.play()


class CharacterButton(pygame.sprite.Sprite):
    """The button to create a Character."""

    def __init__(self, definition):
        """Create a CharacterButton

        definition -- dict of image, frames
        """
        pygame.sprite.Sprite.__init__(self)
        self.name = definition["image"]
        self.image, self.rect = load_image(definition["image"], 
                                           (63, 63))
        if "sound" in definition:
            self.sound = load_sound(definition["sound"])
        else:
            self.sound = None
        self.frames = definition["frames"]

    def make_character(self):
        """Make the Character"""
        if self.sound:
            self.sound.play()
        return Character(self.name, self.frames, sound=self.sound)

    def is_mouse_over(self):
        """Check if the mouse pointer is over the sprite."""
        return self.rect.collidepoint(pygame.mouse.get_pos())


class Layout(pygame.sprite.Sprite):
    """Image of the screen layout."""

    def __init__(self, name, surfsize=None):
        """Create a Layout.

        Parameters:
        name: (string) filename of background image, from the data/ dir
        surfsize: (optional tuple) size of surface to center on
        """
        pygame.sprite.Sprite.__init__(self)
        self.image, self.rect = load_image(name, (ORIG_WIDTH, ORIG_HEIGHT))
        if surfsize:
            mid_x = surfsize[0] / 2
            mid_y = surfsize[1] / 2
            self.rect.center = (mid_x, mid_y)

    @property
    def x(self):
        return self.rect.top


class Game:
    """Represent the layout, buttons, stuff happening"""

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((GAME_WIDTH, GAME_HEIGHT))
        pygame.display.set_caption('Story Builder')

        self.canvas = pygame.Surface(self.screen.get_size()).convert()
        self.canvas.fill((0xAC, 0xAC, 0xAC))

        self._themes = load_themes()
        self.current_theme = 0
        self.layout = Layout('layout.png')
        self.set_theme()
        self.text = ''

        self.screen.blit(self.canvas, (0, 0))
        pygame.display.flip()

        self.clock = pygame.time.Clock()
        self.active_character = None

        self.stickersprites = pygame.sprite.OrderedUpdates()

        # GUI functionality
        self.gui = gui.App(theme=gui.Theme('gui.theme'))
        guicontainer = gui.Container(align=-1, valign=-1)

        lesson_plan_button = gui.Button(_('Lesson Plans'))
        lesson_plan_button.connect(gui.CLICK, self.lesson_plan_cb)
        guicontainer.add(lesson_plan_button, scale(394)+self.layout.rect.left,
                         scale(25)+self.layout.rect.top)
        self.lesson_plan_texts = []
        self.lesson_plan_area = None

        TEXTAREA.x += self.layout.rect.left
        TEXTAREA.y += self.layout.rect.top
        text_input = gui.TextArea(value=self.text)
        text_input.rect = pygame.rect.Rect(TEXTAREA)
        text_input.connect(gui.CHANGE, self.update_text_cb)
        guicontainer.add(text_input, text_input.rect.x, text_input.rect.y)
        self.text_input = text_input

        self.guicontainer = guicontainer

        self.gui.init(guicontainer)

        self.run()

    def load_buttons(self):
        """Load the character button images for the theme"""
        buttons = []
        for button_def in self.theme.buttons:
            button = CharacterButton(button_def)
            buttons.append(button)
        return buttons

    def clear(self):
        """Remove all the characters"""
        self.stickersprites.empty()
        self.active_character = None

    def prev_theme(self):
        self.current_theme -= 1
        self.current_theme %= len(self._themes)
        self.set_theme()

    def next_theme(self):
        self.current_theme += 1
        self.current_theme %= len(self._themes)
        self.set_theme()

    def set_theme(self):
        self.theme = self._themes[self.current_theme]
        self.icon = Icon(theme=self.theme, layout=self.layout)
        self.background = Background(theme=self.theme, layout=self.layout)
        self.bgsprites = pygame.sprite.OrderedUpdates(
            [self.layout, self.background, self.icon])
        self.character_buttons = self.load_buttons()
        self.buttonsprites = pygame.sprite.Group()
        self.characterbar = ButtonBar(self.character_buttons, self.layout,
                                      self.buttonsprites)
        self.widgets = [
            Widget(CHARACTER_BAR_UP, self.layout, self.characterbar.up),
            Widget(CHARACTER_BAR_DOWN, self.layout, self.characterbar.down),
            Widget(CLEAR, self.layout, self.clear),
            Widget(THEME_LEFT, self.layout, self.prev_theme),
            Widget(THEME_RIGHT, self.layout, self.next_theme),
            ]

    def save(self, filename):
        """Save the story.
        """
        f = open(filename, 'w')
        pickle.dump(self.current_theme, f)
        pickle.dump(self.text, f)
        pickle.dump(len(self.stickersprites.sprites()), f)
        for character in self.stickersprites.sprites():
            pickle.dump(character.name, f)
            pickle.dump(character.rect.topleft, f)
        f.close()

    def lesson_plan_cb(self):
        if not self.lesson_plan_texts:
            self.lesson_plan_texts = []
            for lesson_plan in os.listdir('lessons'):
                filename = os.path.join('lessons', lesson_plan, 'default.html')
                self.lesson_plan_texts.append((lesson_plan, open(filename).read()))
            self.lesson_plan_texts.sort()
        if self.lesson_plan_area:
            self.lesson_plan_hide()
        else:
            self.lesson_plan_show(self.lesson_plan_texts[0])

        self.text_input.rect = pygame.rect.Rect(TEXTAREA)

    def lesson_plan_show(self, lesson_to_show):
        self.lesson_plan_area = gui.Container(
            width=self.background.rect.width,
            height=self.background.rect.height)
        self.lesson_plan_group = gui.Group()
        self.lesson_plan_group.connect(gui.CHANGE, self.lesson_plan_tab_cb)
        tt = gui.Table(width=self.background.rect.width,
                       height=self.background.rect.height,
                       background=(255, 255, 255))
        tt.tr()
        for lesson in self.lesson_plan_texts:
            b = gui.Tool(self.lesson_plan_group, gui.Label(lesson[0]), lesson)
            tt.td(b)
        tt.tr()
        htmltext = html.HTML(lesson_to_show[1], align=-1,
                             valign=-1, width=self.background.rect.width-30)
        self.lesson_plan_box = gui.ScrollArea(htmltext,
            width=self.background.rect.width,
            height=self.background.rect.height-30)
        tt.td(self.lesson_plan_box, style={'border':1}, colspan=len(self.lesson_plan_texts))

        #self.lesson_plan_area = gui.ScrollArea(htmltext, 
        #    self.background.rect.width, self.background.rect.height)
        self.lesson_plan_area.add(tt, 0, 0)
        self.guicontainer.add(self.lesson_plan_area, 
                              self.background.rect.left,
                              self.background.rect.top)

    def lesson_plan_hide(self):
        # We are showing it already so hide it
        self.guicontainer.remove(self.lesson_plan_area)
        del self.lesson_plan_area
        self.lesson_plan_area = None


    def lesson_plan_tab_cb(self):
        lesson = self.lesson_plan_group.value
        self.lesson_plan_hide()
        self.lesson_plan_show(lesson)
        self.text_input.rect = pygame.rect.Rect(TEXTAREA)

    def show_file_dialog(self):
        file_dialog = gui.dialog.FileDialog(self)
        file_dialog.connect(gui.CHANGE, self.load_sticker)
        self.file_dialog = file_dialog
        file_dialog.open()

    def load_sticker(self):
        """Load a sticker image."""
        filename = self.file_dialog.value
        # XXXX FIXME Implement this

    def load(self, filename):
        """Load a saved story."""
        
        fail = False
        f = open(filename)
        try:
            self.current_theme = pickle.load(f)
            self.set_theme()
            self.text = pickle.load(f)
            self.text_input.value = self.text
            self.stickersprites.empty()
            self.active_character = None
            num_stickers = pickle.load(f)
            for sticker in range(num_stickers):
                character_name = pickle.load(f)
                character_coords = pickle.load(f)
                for theme in self._themes:
                    for button in theme.buttons:
                        if button['image'] == character_name:
                            if "sound" in button:
                                soundname = button["sound"]
                            else:
                                soundname = None
                            character = Character(character_name, 
                                                  button["frames"],
                                                  soundname=soundname,
                                                  coords=character_coords)
                            character.stick()
                            self.stickersprites.add(character)
                            break
        except EOFError:
            fail = True
        f.close()
        if not fail:
            return True
        return False

    def update_text_cb(self):
        self.text = self.text_input.value

    def run(self):
        # Main loop
        while 1:
            self.clock.tick(FPS)

            for event in pygame.event.get():
                if event.type == eventwrap.Save:
                    logging.debug('Save received')
                    self.save(event.dict['file'])
                    eventwrap.post(eventwrap.ReplyEvent())

                if event.type == eventwrap.Load:
                    logging.debug('Load received')
                    self.load(event.dict['file'])
                    eventwrap.post(eventwrap.ReplyEvent())

                if event.type == QUIT:
                    return
                elif event.type == KEYDOWN and event.key == K_ESCAPE:
                    return
                elif event.type == MOUSEBUTTONDOWN:
                    done = False
                    # Check if clicked on CharacterButtons:
                    for button in self.buttonsprites.sprites():
                        if button.is_mouse_over():
                            self.active_character = button.make_character()
                            self.stickersprites.add(self.active_character)
                            done = True
                    if not done:
                        # Check if clicked on Characters:
                        if not self.active_character:
                            stickerlist = self.stickersprites.sprites()
                            stickerlist.reverse()
                            for character in stickerlist:
                                if character.is_mouse_over():
                                    character.click()
                                    self.active_character = character
                                    character.moving = True
                                    # Remove and re-add sticker to
                                    # push it to the top of the z order
                                    self.stickersprites.remove(character)
                                    self.stickersprites.add(character)
                                    done = True
                                    break
                    if not done:
                        # now handle other buttons
                        for widget in self.widgets:
                            if widget.is_mouse_over():
                                widget.click()
                                done = True
                elif event.type == MOUSEBUTTONUP:
                    if self.active_character and self.active_character.moving:
                        if self.background.rect.collidepoint(
                            pygame.mouse.get_pos()):
                            self.active_character.stick()
                            self.active_character = None
                        else:
                            self.active_character.kill()
                            self.active_character = None
                self.gui.event(event)

            self.stickersprites.update()

            self.screen.blit(self.canvas, (0, 0))
            self.bgsprites.draw(self.screen)
            self.buttonsprites.draw(self.screen)
            self.stickersprites.draw(self.screen)
            self.gui.paint(self.screen)
            pygame.display.flip()


class Icon(pygame.sprite.Sprite):
    """Icon for Theme."""

    def __init__(self, theme, layout=None):
        """Load the icon.
        
        theme -- Theme object
        layout -- optional sprite to align with
        """
        pygame.sprite.Sprite.__init__(self)
        self.image, self.rect = load_image(theme.icon,
                                           (100, 51))
        if layout:
            x = layout.rect.left + scale(462)
            y = layout.rect.top + scale(498)
            self.rect.topleft = (x, y)


class Theme:
    """Model for a theme."""
    def __init__(self, themename):
        """Create the theme based on the name.
        
        themename -- string.
        """
        self.themename = themename
        self.background = theme_defs[themename]['background']
        self.buttons = theme_defs[themename]['buttons']
        self.icon = theme_defs[themename]['icon']


class Widget:
    """A button that controls something."""

    def __init__(self, rect, layout, click_method):
        """Create the Widget"""
        self.rect = pygame.rect.Rect(rect)
        x = layout.rect.left + rect.left
        y = layout.rect.top + rect.top
        self.rect.topleft = (x, y)
        self.click_method = click_method

    def is_mouse_over(self):
        """Check if the mouse pointer is over the sprite."""
        return self.rect.collidepoint(pygame.mouse.get_pos())

    def click(self):
        self.click_method()


def load_themes():
    """Create a list of Themes from theme_defs"""
    themes = []
    for t in theme_list:
        themes.append(Theme(t))
    return themes

if __name__ == '__main__':
    Game()

