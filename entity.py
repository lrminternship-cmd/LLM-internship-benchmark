"""
entity.py -- base class for every moving object (Pac-Man, ghosts, fruit).

ORIGIN: part of the Pac-Man game engine adapted from https://pacmancode.com
(author: Jonathan Richards). Comments added for this thesis.

An Entity moves along the edges of the node graph (see nodes.py). It always has
a current `node` and a `target` node; each frame it advances toward the target,
and when it "overshoots" it snaps to the target and picks the next direction via
`directionMethod` (random for default ghosts, goal-seeking for chasing ghosts).
"""
import pygame
from pygame.locals import *
from vector import Vector2
from constants import *
from random import randint

class Entity(object):
    def __init__(self, node):
        self.name = None
        self.directions = {UP:Vector2(0, -1),DOWN:Vector2(0, 1), 
                          LEFT:Vector2(-1, 0), RIGHT:Vector2(1, 0), STOP:Vector2()}
        self.direction = STOP
        self.setSpeed(100)
        self.radius = 10
        self.collideRadius = 5
        self.color = WHITE
        self.visible = True
        self.disablePortal = False
        self.goal = None
        self.directionMethod = self.randomDirection
        self.setStartNode(node)
        self.image = None

    def setPosition(self):
        self.position = self.node.position.copy()

    def update(self, dt):
        # Move along the current heading, scaled by speed and the frame time dt.
        self.position += self.directions[self.direction]*self.speed*dt

        if self.overshotTarget():
            # Reached (or passed) the target node: arrive there and decide where
            # to go next.
            self.node = self.target
            directions = self.validDirections()
            direction = self.directionMethod(directions)
            # Tunnel wrap-around: stepping onto a portal node teleports to its pair.
            if not self.disablePortal:
                if self.node.neighbors[PORTAL] is not None:
                    self.node = self.node.neighbors[PORTAL]
            self.target = self.getNewTarget(direction)
            if self.target is not self.node:
                self.direction = direction
            else:
                # Chosen direction had no neighbour; keep going the old way.
                self.target = self.getNewTarget(self.direction)

            self.setPosition()
          
    def validDirection(self, direction):
        if direction is not STOP:
            if self.name in self.node.access[direction]:
                if self.node.neighbors[direction] is not None:
                    return True
        return False

    def getNewTarget(self, direction):
        if self.validDirection(direction):
            return self.node.neighbors[direction]
        return self.node

    def overshotTarget(self):
        # True once we have travelled at least as far from the start node as the
        # target is, i.e. we have reached/passed the target along this edge.
        if self.target is not None:
            vec1 = self.target.position - self.node.position
            vec2 = self.position - self.node.position
            node2Target = vec1.magnitudeSquared()
            node2Self = vec2.magnitudeSquared()
            return node2Self >= node2Target
        return False

    def reverseDirection(self):
        self.direction *= -1
        temp = self.node
        self.node = self.target
        self.target = temp
        
    def oppositeDirection(self, direction):
        if direction is not STOP:
            if direction == self.direction * -1:
                return True
        return False

    def validDirections(self):
        # All legal moves except a U-turn (key != reverse of current heading).
        # If that leaves nothing (a dead end), allow the reverse so we never stall.
        directions = []
        for key in [UP, DOWN, LEFT, RIGHT]:
            if self.validDirection(key):
                if key != self.direction * -1:
                    directions.append(key)
        if len(directions) == 0:
            directions.append(self.direction * -1)
        return directions

    def randomDirection(self, directions):
        return directions[randint(0, len(directions)-1)]

    def goalDirection(self, directions):
        # Greedy step toward self.goal: pick the candidate direction whose next
        # tile lands closest (squared distance) to the goal position.
        distances = []
        for direction in directions:
            vec = self.node.position  + self.directions[direction]*TILEWIDTH - self.goal
            distances.append(vec.magnitudeSquared())
        index = distances.index(min(distances))
        return directions[index]

    def setStartNode(self, node):
        self.node = node
        self.startNode = node
        self.target = node
        self.setPosition()

    def setBetweenNodes(self, direction):
        if self.node.neighbors[direction] is not None:
            self.target = self.node.neighbors[direction]
            self.position = (self.node.position + self.target.position) / 2.0

    def reset(self):
        self.setStartNode(self.startNode)
        self.direction = STOP
        self.speed = 100
        self.visible = True

    def setSpeed(self, speed):
        self.speed = speed * TILEWIDTH / 16

    def render(self, screen):
        if self.visible:
            if self.image is not None:
                adjust = Vector2(TILEWIDTH, TILEHEIGHT) / 2
                p = self.position - adjust
                screen.blit(self.image, p.asTuple())
            else:
                p = self.position.asInt()
                pygame.draw.circle(screen, self.color, p, self.radius)