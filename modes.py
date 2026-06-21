"""
modes.py -- ghost behaviour state machine (scatter / chase / frightened / spawn).

ORIGIN: part of the Pac-Man game engine adapted from https://pacmancode.com
(author: Jonathan Richards). Comments added for this thesis.

MainMode alternates the global SCATTER <-> CHASE rhythm on a timer. ModeController
wraps that per ghost and layers the temporary FREIGHT (after a power pellet) and
SPAWN (returning home after being eaten) states on top, falling back to the main
rhythm when those expire.
"""
from constants import *

class MainMode(object):
    def __init__(self):
        self.timer = 0
        self.scatter()

    def update(self, dt):
        self.timer += dt
        if self.timer >= self.time:
            if self.mode is SCATTER:
                self.chase()
            elif self.mode is CHASE:
                self.scatter()

    def scatter(self):
        # Scatter phase lasts 7 seconds, then flips to chase.
        self.mode = SCATTER
        self.time = 7
        self.timer = 0

    def chase(self):
        # Chase phase lasts 20 seconds, then flips back to scatter.
        self.mode = CHASE
        self.time = 20
        self.timer = 0


class ModeController(object):
    def __init__(self, entity):
        self.timer = 0
        self.time = None
        self.mainmode = MainMode()
        self.current = self.mainmode.mode
        self.entity = entity 

    def update(self, dt):
        self.mainmode.update(dt)
        if self.current is FREIGHT:
            self.timer += dt
            if self.timer >= self.time:
                self.time = None
                self.entity.normalMode()
                self.current = self.mainmode.mode
        elif self.current in [SCATTER, CHASE]:
            self.current = self.mainmode.mode

        if self.current is SPAWN:
            if self.entity.node == self.entity.spawnNode:
                self.entity.normalMode()
                self.current = self.mainmode.mode

    def setFreightMode(self):
        if self.current in [SCATTER, CHASE]:
            self.timer = 0
            self.time = 7
            self.current = FREIGHT
        elif self.current is FREIGHT:
            self.timer = 0

    def setSpawnMode(self):
        if self.current is FREIGHT:
            self.current = SPAWN