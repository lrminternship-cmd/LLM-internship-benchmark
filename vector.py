"""
vector.py -- 2D vector class for position and direction maths.

ORIGIN: this file is part of the Pac-Man game engine adapted from the tutorial
at https://pacmancode.com (author: Jonathan Richards). It is essentially
unchanged base code; the comments were added for this thesis to clarify intent.
The NP-Hard extensions and the LLM-benchmark work live in the project's own
modules (level1.py, lv_*.py, *_runner.py).

Vector2 supports add, subtract, scale and equality (with a small tolerance to
absorb floating-point rounding), plus tuple/int conversions. The engine uses it
throughout for pixel positions and movement directions.
"""
import math

class Vector2(object):
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y
        # Tolerance under which two vectors count as "equal", so floating-point
        # noise does not cause spurious inequality (see __eq__).
        self.thresh = 0.000001

    def __add__(self, other):
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vector2(self.x - other.x, self.y - other.y)

    def __neg__(self):
        return Vector2(-self.x, -self.y)

    def __mul__(self, scalar):
        return Vector2(self.x * scalar, self.y * scalar)

    def __div__(self, scalar):
        if scalar != 0:
            return Vector2(self.x / float(scalar), self.y / float(scalar))
        return None

    def __truediv__(self, scalar):
        return self.__div__(scalar)

    def __eq__(self, other):
        if abs(self.x - other.x) < self.thresh:
            if abs(self.y - other.y) < self.thresh:
                return True
        return False

    def magnitudeSquared(self):
        # Squared length; avoids the sqrt when only comparing distances,
        # which is why the engine prefers this over magnitude() in hot paths.
        return self.x**2 + self.y**2

    def magnitude(self):
        return math.sqrt(self.magnitudeSquared())

    def copy(self):
        return Vector2(self.x, self.y)

    def asTuple(self):
        return self.x, self.y

    def asInt(self):
        return int(self.x), int(self.y)

    def __str__(self):
        return "<"+str(self.x)+", "+str(self.y)+">"