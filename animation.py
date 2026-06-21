"""
animation.py -- a tiny frame-sequence animator for sprites.

ORIGIN: part of the Pac-Man game engine adapted from https://pacmancode.com
(author: Jonathan Richards). Comments added for this thesis.

Animator advances through `frames` at `speed` frames per second using the
per-call delta time dt, optionally looping. Returns the current frame each update.
Cosmetic only; not used by the headless LLM benchmark.
"""
from constants import *

class Animator(object):
    def __init__(self, frames=[], speed=20, loop=True):
        self.frames = frames
        self.current_frame = 0
        self.speed = speed
        self.loop = loop
        self.dt = 0
        self.finished = False

    def reset(self):
        self.current_frame = 0
        self.finished = False

    def update(self, dt):
        if not self.finished:
            self.nextFrame(dt)
        if self.current_frame == len(self.frames):
            if self.loop:
                self.current_frame = 0
            else:
                self.finished = True
                self.current_frame -= 1
   
        return self.frames[self.current_frame]

    def nextFrame(self, dt):
        self.dt += dt
        if self.dt >= (1.0 / self.speed):
            self.current_frame += 1
            self.dt = 0





                        
