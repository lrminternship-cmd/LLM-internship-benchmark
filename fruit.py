"""
fruit.py -- the bonus fruit that briefly appears for extra points.

ORIGIN: part of the Pac-Man game engine adapted from https://pacmancode.com
(author: Jonathan Richards). Comments added for this thesis.

A Fruit is a short-lived Entity: it spawns, sits for `lifespan` seconds, then
flags itself for destruction. Its point value scales with the level.
"""
import pygame
from entity import Entity
from constants import *
from sprites import FruitSprites

class Fruit(Entity):
    def __init__(self, node, level=0):
        Entity.__init__(self, node)
        self.name = FRUIT
        self.color = GREEN
        self.lifespan = 5
        self.timer = 0
        self.destroy = False
        self.points = 100 + level*20
        self.setBetweenNodes(RIGHT)
        self.sprites = FruitSprites(self, level)

    def update(self, dt):
        self.timer += dt
        if self.timer >= self.lifespan:
            self.destroy = True