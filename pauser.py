"""
pauser.py -- pause state, used both for the player pause and for timed pauses.

ORIGIN: part of the Pac-Man game engine adapted from https://pacmancode.com
(author: Jonathan Richards). Comments added for this thesis.

setPause can hold the game for a fixed pauseTime and then fire an optional
callback `func` (e.g. resume play after the death animation). flip() toggles a
manual player pause.
"""
class Pause(object):
    def __init__(self, paused=False):
        self.paused = paused
        self.timer = 0
        self.pauseTime = None
        self.func = None
        
    def update(self, dt):
        if self.pauseTime is not None:
            self.timer += dt
            if self.timer >= self.pauseTime:
                self.timer = 0
                self.paused = False
                self.pauseTime = None
                return self.func
        return None

    def setPause(self, playerPaused=False, pauseTime=None, func=None):
        self.timer = 0
        self.func = func
        self.pauseTime = pauseTime
        self.flip()

    def flip(self):
        self.paused = not self.paused