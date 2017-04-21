import pygtk
pygtk.require('2.0')
import gtk
import hippo
import os
from gettext import gettext as _
import logging

from sugar.activity import activity
from olpcgames import PyGameActivity
from olpcgames import eventwrap
from StoryBuilder import GAME_WIDTH, GAME_HEIGHT

class StoryBuilderActivity(PyGameActivity):
    game_name = 'StoryBuilder:Game'
    game_title = _('Story Builder')
    game_size = (GAME_WIDTH, GAME_HEIGHT)
    pygame_mode = 'SDL'

    def __init__(self, handle):
        """Get into the right directory so we can find the artwork"""
        super(StoryBuilderActivity, self).__init__(handle)
        os.chdir(activity.get_bundle_path())

    def write_file(self, file_path):
        eventwrap.post(eventwrap.SaveEvent(file_path))
        logging.debug('Save sent')
        if eventwrap.wait(types = [eventwrap.Reply]) == None:
            logging.error('Cannot save to journal')

    def read_file(self, file_path):
        eventwrap.post(eventwrap.LoadEvent(file_path))
        logging.debug('Load sent')
        return eventwrap.wait(types = [eventwrap.Reply]) != None
