"""
language_game.py -- visual pygame front-end for the Language Game.

A separate benchmark task from the Pac-Man game: instead of navigating a maze,
the player (human or LLM) must apply a layered set of natural-language rules to
pick the correct word. Difficulty scales by stacking rule layers:

  WORD_SELECT_RULES     -- which word to choose from a sentence
  BASE_RULES            -- the base world rules
  META_RULES            -- rules that modify the base rules
  META_META_RULES       -- rules that modify the meta-rules
  META_META_META_RULES  -- one further level of rule modification
  EXTRA_HARD_RULES      -- additional hard constraints

This file handles the pygame rendering and input. The headless LLM versions of
this task live in language_api_runner.py and language_control_runner.py, which
present the same rules as a text prompt and parse the model's answer.

Run with:  python language_game.py
"""
import pygame
import sys
import os

pygame.init()

# --- Screen size (fullscreen) ---
_info = pygame.display.Info()
SW, SH = _info.current_w, _info.current_h

# --- Colours ---
BLACK        = (0,   0,   0)
WHITE        = (255, 255, 255)
YELLOW       = (255, 220,  50)
DARK_BLUE    = ( 10,  30,  80)
LIGHT_BLUE   = ( 80, 140, 220)
GREY         = (200, 200, 200)
DARK_GREY    = ( 60,  60,  60)
MID_GREY     = (120, 120, 120)
GREEN        = ( 50, 200,  80)
ORANGE       = (220, 140,  30)
RED          = (200,  50,  50)
PANEL_BG     = ( 18,  18,  40)
PANEL_BORDER = ( 60,  80, 160)
NOTEPAD_BG   = (250, 248, 230)
NOTEPAD_LINE = (180, 200, 220)
NOTEPAD_TXT  = ( 30,  30,  80)
FINAL_BG     = ( 20,  40,  20)
FINAL_BORDER = ( 50, 180,  50)
FINAL_TXT    = (180, 255, 180)
SUBMIT_COL   = ( 50, 180,  50)
SUBMIT_HOV   = ( 80, 220,  80)
SW_FIELD_BG  = ( 20,  20,  50)   # selected-words input bg
SW_FIELD_BOR = ( 80, 100, 200)   # selected-words border (inactive)
SW_FIELD_ACT = (140, 160, 255)   # selected-words border (active)

FONT_PATH = os.path.join(os.path.dirname(__file__), "PressStart2P-Regular.ttf")

def load_font(size):
    try:
        return pygame.font.Font(FONT_PATH, size)
    except Exception:
        return pygame.font.SysFont("monospace", size)

FNT_TINY  = load_font(8)
FNT_SMALL = load_font(10)
FNT_MED   = load_font(13)
FNT_BIG   = load_font(20)
FNT_TITLE = load_font(30)

screen = pygame.display.set_mode((SW, SH), pygame.FULLSCREEN)
pygame.display.set_caption("Language Game")
clock = pygame.time.Clock()

# ---------------------------------------------------------------------------
# LEGEND CONTENT  — exact text from the document
# ---------------------------------------------------------------------------
WORD_SELECT_RULES = [
    "Sentences appear in pairs. Only the first sentence of each pair is evaluated against the given world rules. The second sentence is a word bank so its content is irrelevant to logic, it only supplies words.",
    "",
    "Word selection from the second sentence:",
    "",
    "First sentence is TRUE = take words at positions 2, 4, 6, 8, ... (every even position)",
    "",
    "First sentence is FALSE = take words at positions 1, 3, 5, 7 ... (every odd position)",
    "",
    "First sentence is UNDECIDABLE (the sentence does not contain any claims that can be verified or rejected using the world rules) = take words at positions 1, 4, 7, ... (every third word starting from position 1)",
    "",
    "Emergent Layer:",
    "",
    "After processing all pairs, collect all extracted words in order. Words from pair 1b first, then pair 2b, then pair 3b and so on. These words will spell one of three things:",
    "",
    "Case 1: A question: Answer it directly.",
    "",
    "Case 2: New instructions: Follow them and report the new answer as the final answer",
    "",
    "Case 3: Nonsense: Output the nonsense sentence as-is.",
]

BASE_RULES = [
    "Sun appears only at night (00:00-06:00).",
    "",
    "Moon appears only during day (06:00-00:00).",
    "",
    "When sun appears: everything looks purple.",
    "",
    "I feel happy when I see purple. If not, or when I am wearing green, I feel sad",
    "",
    "At 2 a.m. I wear green for exactly 1 hour (until 3 a.m.).",
    "",
    "gravity is reversed: all objects fall up.",
    "",
    "Mon / Wed / Sat: fire = cold, ice = hot. All other days: fire = hot, ice = cold.",
    "",
    "Today is wednesday, unless specified differently.",
    "",
    "Hours go in reverse",
]

# Meta-Rules
META_RULES = [
    "Meta-A: Reverse the truth value BEFORE applying the word-selection rule.",
    "",
    "Meta-B: If a extracted output word has MORE THAN 6 letters, replace it with the 1st word of sentence (a).",
    "",
    "Meta-C: If a extracted output word is a PREPOSITION, skip the NEXT sentence pair entirely.",
    "",
    "Meta-D: If sentence (a) contains a TEMPERATURE WORD (hot/cold/warm/cool), invert ALL temperatures before evaluating.",
]

# Meta-Meta Rules
META_META_RULES = [
    "MM-A: Meta-Rule A applies ONLY if sentence (a) has MORE THAN 12 words.",
    "",
    "MM-B: Meta-Rule B does NOT apply if the 1st word of sentence (a) is a personal pronoun (I, you, he, she, it, we, they).",
    "",
    "MM-C: Meta-Rule C applies ONLY on TUESDAYS and FRIDAYS. Evaluate against the same sentence pair as you got the preposition from",
    "",
    "MM-D: If sentence (a) mentions both a temperature word AND fire or ice, AND the day is Saturday, apply Meta-D TWICE.",
]

# Meta-Meta-Meta Rule — operates above the meta-meta level
META_META_META_RULES = [
    "MM-MMM: If the VERY LAST WORD of sentence (a) contains 3 or more vowels, IGNORE all meta(-meta)(-meta)-rules for that pair.",
]

# Hard extras
EXTRA_HARD_RULES = [
    "OBSERVER EFFECT: If sentence (a) contains 'I' or 'my': a moving observer reverses gravity for this pair only; a stationary or unspecified observer leaves gravity unchanged.",
    "",
    "SENTENCE DEPENDENCY: The first and the last word extracted from pair N modifies the rules for pair N+1. If either word is a verb, gravity inverts for the next pair. If either word is a noun, the 'sun and moon rule' inverts for the next pair. If both are a noun or both are a verb, I am wearing green for the next pair. Anything else produces no change.",
]

# ---------------------------------------------------------------------------
# LEVEL DATA
# ---------------------------------------------------------------------------
LEVELS = [
    {
        "name": "Low Complexity",
        "difficulty": "easy",
        "color": GREEN,
        "pairs": [
            {
                "a": "The moon is out on Saturday at 2 a.m. while I am wearing green.",
                "b": "Is the grass wet?",
            },
            {
                "a": "It is 0:30 a.m. right now, in one hour, I can burn myself stepping into a campfire.",
                "b": "Aliens usually have green clothes on.",
            },
            {
                "a": "My friend dropped my favorite mug, which broke when hitting the ground, so I am sad.",
                "b": "Planet systems earth wins.",
            },
        ],
        "legend_sections": [
            ("Word Selection Rules", WORD_SELECT_RULES, LIGHT_BLUE),
            ("Base World Rules",     BASE_RULES,         GREY),
        ],
    },
    {
        "name": "Medium Complexity",
        "difficulty": "medium",
        "color": YELLOW,
        "pairs": [
            {
                "a": "I took my dog for a walk in the park and he jumped in a mud puddle",
                "b": "How will that many people agree?",
            },
            {
                "a": "Seconds ago I used ice to cool my legs after my Tuesday afternoon run.",
                "b": "How humongous dinosaurs are grown in labs.",
            },
            {
                "a": "I felt happy when I looked at the sun yesterday an hour before 1 a.m.",
                "b": "The Martians will conquer earth within 60 days.",
            },
            {
                "a": "A warm hotdog fell up into the sky after I let go.",
                "b": "My grandmother is minute gone when did I.",
            },
            {
                "a": "My gecko iced his sore paws on a cool piece of ice yesterday.",
                "b": "When am I robbing the an attraction enormous blue bank?",
            },
        ],
        "legend_sections": [
            ("Word Selection Rules",      WORD_SELECT_RULES,      LIGHT_BLUE),
            ("Base World Rules",          BASE_RULES,              GREY),
            ("Meta-Rules",               META_RULES,              YELLOW),
            ("Meta-Meta Rules",          META_META_RULES,         ORANGE),
            ("Meta-Meta-Meta Rule",      META_META_META_RULES,    RED),
        ],
    },
    {
        "name": "High Complexity",
        "difficulty": "hard",
        "color": ORANGE,
        "pairs": [
            {
                "a": "It is now 3:30 a.m., an hour ago I felt happy drinking cold water.",
                "b": "New main goal:",
            },
            {
                "a": "It is now 1:30 a.m., in an hour, I will feel sad.",
                "b": "How the golden sun now rises.",
            },
            {
                "a": "I am running after my dog on the ceiling while he is chasing his ball.",
                "b": "During the daytime I determine how the brand new.",
            },
            {
                "a": "Sentence me to jail on this Friday and I will live longer than any man has.",
                "b": "Wherever we came from, now we, the people, must word.",
            },
            {
                "a": "I burned my feet walking on a pile of burning hot wood this Tuesday.",
                "b": "The dog fell up the balloon on a rainy day.",
            },
            {
                "a": "I felt happy at 5 a.m. on Saturday when I cooled my hand on a cold fire.",
                "b": "Houston pairs his and her report for them.",
            },
        ],
        "legend_sections": [
            ("Word Selection Rules",      WORD_SELECT_RULES,      LIGHT_BLUE),
            ("Base World Rules",          BASE_RULES,              GREY),
            ("Meta-Rules",               META_RULES,              YELLOW),
            ("Meta-Meta Rules",          META_META_RULES,         ORANGE),
            ("Meta-Meta-Meta Rule",      META_META_META_RULES,    RED),
            ("Hard Extras",              EXTRA_HARD_RULES,        RED),
        ],
    },
    {
        "name": "Maximum Complexity",
        "difficulty": "advanced",
        "color": RED,
        "pairs": [
            {
                "a": "It is Tuesday, in 24 hours, it will be Monday.",
                "b": "How the special new released game now goes like in or this weird way to the second first nominate.",
            },
            {
                "a": "I am running on the ground while drinking some water.",
                "b": "My grandma hands cookies to from how my house and the scouts reboard the train.",
            },
            {
                "a": "I burned my hands on a cold fire this Sunday.",
                "b": "My sentence and spells are the very first new question and the new second question spells clearly the old second weird question how.",
            },
            {
                "a": "I was looking at the sun at 5 a.m. and felt happy.",
                "b": "And how so many on man your new answer given to most these of questions now may well be this A further B how C.",
            },
            {
                "a": "I was walking when I saw the moon in the sky 4 hours before 3 a.m.",
                "b": "Or quick d brown the fox corresponding jumps answers over will the be lazy listed dog after and these then letters runs the away crux very of fast this indeed game good is score that.",
            },
            {
                "a": "I was looking out of my window at 3 a.m. this morning.",
                "b": "the dolphins the answers are ancient to incredibly library the intelligent contained different creatures thousands questions that of refer communicate manuscripts to using written each complex by other patterns scholars so of from you clicks many need and different to whistles civilizations find near around the the the correct ocean entire combination shore world of every for answers day centuries and.",
            },
            {
                "a": "I drank some ice cold water to cool down today.",
                "b": "you A may mysterious use traveler the arrived world at rules the the old game village starts carrying now nothing question but 1 a how worn often horse is satchel b filled the with answer forgotten a memories 2 and b secrets 1.",
            },
            {
                "a": "They said draft is the best way to get a milk stain out of a shirt.",
                "b": "c the scientists 4 golden recently d sunset discovered 3 painted a question the new 2 sky species if with of i brilliant deep am shades sea walking of creature outside orange living in and in the pink the sun while darkest i birds pars see flew of what silently the color overhead ocean a every floor blue single last b night year purple.",
            },
            {
                "a": "Happiness was the emotion I felt walking around outside an hour after 5 a.m. yesterday.",
                "b": "how c the green young d professor yellow carefully question explained 3 the what complex is theory the to answer his to confused this students question using a simple a examples b and b clear c visual c diagrams d on d paper.",
            },
        ],
        "legend_sections": [
            ("Word Selection Rules",      WORD_SELECT_RULES,      LIGHT_BLUE),
            ("Base World Rules",          BASE_RULES,              GREY),
            ("Meta-Rules",               META_RULES,              YELLOW),
            ("Meta-Meta Rules",          META_META_RULES,         ORANGE),
            ("Meta-Meta-Meta Rule",      META_META_META_RULES,    RED),
            ("Hard Extras",              EXTRA_HARD_RULES,        RED),
        ],
    },
]

# ---------------------------------------------------------------------------
# ANSWER KEYS  (shown on the feedback screen after submit, not during play)
# ---------------------------------------------------------------------------
ANSWER_KEYS = [
    # ---- LOW ---------------------------------------------------------------
    {
        "pairs": [
            {
                "verdict":         "false",
                "selected_words":  "is, grass",
            },
            {
                "verdict":         "true",
                "selected_words":  "usually, green, on",
            },
            {
                "verdict":         "false",
                "selected_words":  "planet, earth",
            },
        ],
        "emergent":       "Is grass usually green on planet earth?",
        "emergent_answer": "Yes",
        "alt_condition":  "What is the normal color of leaves on a tree?",
    },
    # ---- MEDIUM ------------------------------------------------------------
    {
        "pairs": [
            {
                "verdict":         "undecidable",
                "selected_words":  "How, many",
            },
            {
                "verdict":         "true",
                "selected_words":  "Seconds, are, in",
            },
            {
                "verdict":         "skip",
                "selected_words":  "",
            },
            {
                "verdict":         "true",
                "selected_words":  "A, minute, when, I",
            },
            {
                "verdict":         "true",
                "selected_words":  "Am, robbing, an, enormous, bank",
            },
        ],
        "emergent":       "How many seconds are in a minute when I am robbing an enormous bank?",
        "emergent_answer": "60 seconds / 60",
        "alt_condition":  "How many hours are in 3 days?",
    },
    # ---- HARD --------------------------------------------------------------
    {
        "pairs": [
            {
                "verdict":         "false",
                "selected_words":  "New, goal:",
            },
            {
                "verdict":         "true",
                "selected_words":  "The, sun, rises",
            },
            {
                "verdict":         "false",
                "selected_words":  "During, daytime, determine, the, new",
            },
            {
                "verdict":         "undecidable",
                "selected_words":  "Sentence, from, the, word",
            },
            {
                "verdict":         "skip",
                "selected_words":  "",
            },
            {
                "verdict":         "true",
                "selected_words":  "pairs, and, report, them",
            },
        ],
        "emergent":       "New goal: The sun rises during daytime, determine the new sentence from the word pairs and report them.",
        "emergent_answer": "Main the sun rises during daytime, determine the new sentence from the word houston his her for.",
        "alt_condition":  "My neighbors' dog jumped pool down to the store and however way the food ran up.",
        "re_eval_rule_change": "NEW RULE: The sun now rises during daytime (06:00-00:00) and the moon appears at night (00:00-06:00). Everything else stays the same.",
        "re_eval_pairs": [
            {"verdict": "true",        "selected_words": "main"},
            {"verdict": "true",        "selected_words": "The, sun, rises"},
            {"verdict": "false",       "selected_words": "During, daytime, determine, the, new"},
            {"verdict": "undecidable", "selected_words": "Sentence, from, the, word"},
            {"verdict": "skip",        "selected_words": ""},
            {"verdict": "false",       "selected_words": "Houston, his, her, for"},
        ],
    },
    # ---- ADVANCED ----------------------------------------------------------
    {
        "pairs": [
            {
                "verdict":         "true",
                "selected_words":  "The, new, game, goes, in, this, way, the, first",
            },
            {
                "verdict":         "skip",
                "selected_words":  "(SKIPPED — pair 1 extracted word 'in' is a preposition -> Meta-C skips pair 2)",
            },
            {
                "verdict":         "true",
                "selected_words":  "Sentence, spells, the, first, question, the, second, spells, the, second, question",
            },
            {
                "verdict":         "false",
                "selected_words":  "And, so, on, your, answer, to, these, questions, may, be, A, B, C",
            },
            {
                "verdict":         "false",
                "selected_words":  "Or, D, the, corresponding, answers, will, be, listed, after, these, letters, the, crux, of, this, game, is, that",
            },
            {
                "verdict":         "undecidable",
                "selected_words":  "the, answers, to, the, different, questions, refer, to, each, other, so, you, need, to, find, the, correct, combination, of, answers, and",
            },
            {
                "verdict":         "false",
                "selected_words":  "you, may, use, the, world, rules, the, game, starts, now, question, 1, how, often, is, b, the, answer, a, 2, b, 1",
            },
            {
                "verdict":         "undecidable",
                "selected_words":  "c, 4, d, 3, question, 2, if, I, am, walking, outside, in, the, sun, I, see, what, color, a, blue, b, purple",
            },
            {
                "verdict":         "true",
                "selected_words":  "c, green, d, yellow, question, 3, what, is, the, answer, to, this, question, a, a, b, b, c, c, d, d",
            },
        ],
        "emergent":       "The new game goes in this way: the first sentence spells the first question, the second spells the second question etc. Your answer to these questions may be A, B, C or D. The corresponding answers will be listed after these letters. The crux of this game is that the answers to the different questions refer to each other, so you need to find the correct combination of answers. And you may use the world rules. The game starts now. Question 1: how often is B the answer? A=2, B=1, C=4, D=3. Question 2: if I am walking outside in the sun, I see what color? A=blue, B=purple, C=green, D=yellow. Question 3: what is the answer to this question? A=a, B=b, C=c, D=d.",
        "emergent_answer": "A, B, B",
        "alt_condition":  "Q2: walking outside in the sun -> sun only appears 00:00-06:00 (night), so during the day there is no sun -> no purple -> normal color vision -> A (blue). Q3: 'what is the answer to this question?' -> C says 'c' -> self-consistent. Q1: B appears 0 times as answer (Q1=A, Q2=A, Q3=C) -> A=2 is wrong too... A appears twice -> A=2 is correct -> Q1=A.",
    },
]

# ---------------------------------------------------------------------------
# EXPLANATION PAGES
# ---------------------------------------------------------------------------
EXPLAIN_PAGES = [
    [
        "SENTENCE PAIR STRUCTURES",
        "",
        "Sentences appear in PAIRS.",
        "Only sentence (a) is evaluated against the given world rules.",
        "Sentence (b) is the word bank — logic irrelevant.",
        "",
        "[ Press any key to continue ]",
    ],
    [
        "WORD SELECTION FROM SENTENCE B",
        "",
        "Sentence (a) is TRUE",
        "  -> take words at positions 2, 4, 6, 8 ...",
        "     (every EVEN position)",
        "",
        "Sentence (a) is FALSE",
        "  -> take words at positions 1, 3, 5, 7 ...",
        "     (every ODD position)",
        "",
        "Sentence (a) is UNDECIDABLE",
        "  -> take words at positions 1, 4, 7 ...",
        "     (every third word starting from position 1)",
        "",
        "[ Press any key to continue ]",
    ],
    [
        "EMERGENT LAYER",
        "",
        "After all pairs: collect extracted words in order.",
        "  (pair 1b first, then 2b, then 3b ...)",
        "",
        "The collected words spell ONE of three things:",
        "",
        "Case 1: A QUESTION  -> answer it directly.",
        "Case 2: NEW INSTRUCTIONS -> follow them.",
        "Case 3: NONSENSE -> output the nonsense as-is.",
        "",
        "[ Press any key to start Level 1 ]",
    ],
]

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def quit_game():
    pygame.quit()
    sys.exit()


def wrap_text(text, font, max_w):
    """Return list of strings that each fit within max_w pixels."""
    words = text.split()
    if not words:
        return [""]
    out, line = [], ""
    for w in words:
        test = (line + " " + w).strip()
        if font.size(test)[0] <= max_w:
            line = test
        else:
            if line:
                out.append(line)
            line = w
    if line:
        out.append(line)
    return out or [""]


def draw_text(surface, text, font, color, x, y, max_width=None, align="left"):
    if max_width:
        lines = wrap_text(text, font, max_width)
        lh = font.get_linesize()
        for i, l in enumerate(lines):
            surf = font.render(l, True, color)
            bx = x - surf.get_width()//2 if align == "center" else x
            surface.blit(surf, (bx, y + i*lh))
        return lh * len(lines)
    else:
        surf = font.render(text, True, color)
        bx = x - surf.get_width()//2 if align == "center" else x
        surface.blit(surf, (bx, y))
        return surf.get_height()


def draw_wrapped(surface, text, font, color, x, y, max_width, line_spacing=4):
    lines = wrap_text(text, font, max_width)
    lh = font.get_linesize() + line_spacing
    for i, l in enumerate(lines):
        surf = font.render(l, True, color)
        surface.blit(surf, (x, y + i * lh))
    return lh * len(lines)


def draw_panel(surface, rect, bg=PANEL_BG, border=PANEL_BORDER, radius=8, border_width=2):
    pygame.draw.rect(surface, bg, rect, border_radius=radius)
    pygame.draw.rect(surface, border, rect, border_width, border_radius=radius)


def draw_notepad_bg(surface, rect):
    pygame.draw.rect(surface, NOTEPAD_BG, rect, border_radius=6)
    pygame.draw.rect(surface, NOTEPAD_LINE, rect, 2, border_radius=6)
    lh = 22
    y = rect.top + lh
    while y < rect.bottom - 4:
        pygame.draw.line(surface, NOTEPAD_LINE, (rect.left+10, y), (rect.right-10, y), 1)
        y += lh


def stars_surface():
    import random
    s = pygame.Surface((SW, SH))
    s.fill(BLACK)
    rng = random.Random(42)
    for _ in range(120):
        x = rng.randint(0, SW-1)
        y = rng.randint(0, SH-1)
        b = rng.randint(100, 255)
        s.set_at((x, y), (b, b, b))
    return s


BG_STARS = stars_surface()

# ---------------------------------------------------------------------------
# INTRO SCREEN  — returns participant number string
# ---------------------------------------------------------------------------
def screen_intro():
    participant_nr = ""
    t = 0
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    quit_game()
                elif event.key == pygame.K_BACKSPACE:
                    participant_nr = participant_nr[:-1]
                elif event.key == pygame.K_RETURN:
                    if participant_nr.strip():
                        return participant_nr.strip()
                else:
                    ch = event.unicode
                    if ch and ch.isprintable() and len(participant_nr) < 20:
                        participant_nr += ch

        dt = clock.tick(60) / 1000
        t += dt
        screen.blit(BG_STARS, (0, 0))
        pulse = abs((t % 2) - 1)
        box_col = (int(20+40*pulse), int(20+40*pulse), int(80+60*pulse))
        title_rect = pygame.Rect(SW//2-340, SH//2-200, 680, 130)
        pygame.draw.rect(screen, box_col, title_rect, border_radius=12)
        pygame.draw.rect(screen, LIGHT_BLUE, title_rect, 3, border_radius=12)
        draw_text(screen, "LANGUAGE", FNT_TITLE, YELLOW, SW//2, SH//2-188, align="center")
        draw_text(screen, "GAME",     FNT_TITLE, WHITE,  SW//2, SH//2-138, align="center")
        draw_text(screen, "A reasoning puzzle in four levels", FNT_SMALL, GREY, SW//2, SH//2-30, align="center")

        # Participant number field
        field_w = 320
        field_r = pygame.Rect(SW//2 - field_w//2, SH//2 + 10, field_w, 36)
        lbl_s = FNT_SMALL.render("Participant number:", True, LIGHT_BLUE)
        screen.blit(lbl_s, (field_r.left, field_r.top - 22))
        filled = bool(participant_nr.strip())
        fbg  = (20, 30, 60)
        fbor = GREEN if filled else (80, 100, 200)
        pygame.draw.rect(screen, fbg,  field_r, border_radius=5)
        pygame.draw.rect(screen, fbor, field_r, 2, border_radius=5)
        nr_s = FNT_MED.render(participant_nr, True, WHITE)
        screen.blit(nr_s, (field_r.left + 10, field_r.top + 7))
        # blinking cursor
        if int(t * 2) % 2 == 0:
            cx = field_r.left + 10 + FNT_MED.size(participant_nr)[0]
            pygame.draw.rect(screen, WHITE, pygame.Rect(cx, field_r.top + 8, 2, 18))

        if filled:
            draw_text(screen, ">> PRESS ENTER TO BEGIN <<", FNT_MED, GREEN,
                      SW//2, field_r.bottom + 28, align="center")
        else:
            draw_text(screen, "Enter a participant number to start", FNT_SMALL, MID_GREY,
                      SW//2, field_r.bottom + 28, align="center")

        draw_text(screen, "Low / Medium / Hard / Advanced  |  ESC to quit",
                  FNT_TINY, DARK_GREY, SW//2, SH - 40, align="center")
        pygame.display.flip()


# ---------------------------------------------------------------------------
# EXPLANATION SCREEN
# ---------------------------------------------------------------------------
def screen_explain():
    for page in EXPLAIN_PAGES:
        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    quit_game()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        quit_game()
                    waiting = False
            screen.blit(BG_STARS, (0, 0))
            panel = pygame.Rect(SW//2-400, 80, 800, SH-160)
            draw_panel(screen, panel)
            y = panel.top + 30
            for i, line in enumerate(page):
                if i == 0:
                    draw_text(screen, line, FNT_MED, YELLOW, SW//2, y, align="center")
                    y += 44
                elif line == "":
                    y += 12
                elif line.startswith("[ "):
                    draw_text(screen, line, FNT_SMALL, LIGHT_BLUE, SW//2, y+10, align="center")
                    y += 32
                else:
                    col = WHITE if not line.startswith("  ") else GREY
                    draw_text(screen, line, FNT_SMALL, col, panel.left+40, y)
                    y += 28
            clock.tick(60)
            pygame.display.flip()


# ---------------------------------------------------------------------------
# MAIN LEVEL SCREEN
# ---------------------------------------------------------------------------
SW_FIELD_H = 28   # height of each selected-words input bar

def screen_level(level_idx, participant_nr=""):
    level          = LEVELS[level_idx]
    pairs          = level["pairs"]
    sections       = level["legend_sections"]
    difficulty_col = level["color"]
    n_pairs        = len(pairs)

    # Layout
    MARGIN   = 10
    LEFT_W   = 420
    RIGHT_W  = 420
    HEADER_H = 52
    PANEL_Y  = HEADER_H + MARGIN
    FA_H     = 120

    notepad_visible = True

    def compute_layout():
        panel_h = SH - PANEL_Y - MARGIN
        if notepad_visible:
            left_w  = LEFT_W
            mid_w   = SW - left_w - RIGHT_W - 4*MARGIN
            left_x  = MARGIN
            mid_x   = left_x + left_w + MARGIN
            right_x = mid_x + mid_w + MARGIN
            np_h    = panel_h - FA_H - MARGIN
            r_rect  = pygame.Rect(right_x, PANEL_Y, RIGHT_W, np_h)
            f_rect  = pygame.Rect(right_x, PANEL_Y + np_h + MARGIN, RIGHT_W, FA_H)
        else:
            total_w = SW - 3*MARGIN
            left_w  = total_w // 2
            mid_w   = total_w - left_w
            left_x  = MARGIN
            mid_x   = left_x + left_w + MARGIN
            r_rect  = pygame.Rect(0, 0, 0, 0)   # hidden
            f_rect  = pygame.Rect(mid_x + mid_w - RIGHT_W, PANEL_Y + panel_h - FA_H,
                                  RIGHT_W, FA_H)
        l_rect = pygame.Rect(left_x, PANEL_Y, left_w, panel_h)
        m_rect = pygame.Rect(mid_x,  PANEL_Y, mid_w,  panel_h)
        b_w, b_h = 150, 30
        b_rect = pygame.Rect(f_rect.right - b_w - 10, f_rect.bottom - b_h - 8, b_w, b_h)
        return l_rect, m_rect, r_rect, f_rect, b_rect

    left_rect, mid_rect, right_rect, fa_rect, btn_rect = compute_layout()
    PANEL_H = left_rect.height
    btn_w   = 150

    # ---- Notepad ----
    notepad_lines  = [""]
    notepad_cursor = 0
    notepad_scroll = 0
    NP_LH      = 22
    NP_VISIBLE = max(1, (right_rect.height - 30) // NP_LH)

    def refresh_layout():
        nonlocal left_rect, mid_rect, right_rect, fa_rect, btn_rect, PANEL_H, NP_VISIBLE
        nonlocal pair_heights, total_content_h, pair_y_offsets, PAIR_TEXT_W
        nonlocal LEG_TEXT_W, legend_items, legend_total_h
        left_rect, mid_rect, right_rect, fa_rect, btn_rect = compute_layout()
        PANEL_H     = left_rect.height
        NP_VISIBLE  = max(1, (right_rect.height - 30) // NP_LH) if notepad_visible else 1
        PAIR_TEXT_W = mid_rect.width - 4 - 30
        LEG_TEXT_W  = left_rect.width - 24
        legend_items    = build_legend_items()
        legend_total_h  = sum(it["height"] for it in legend_items)
        pair_heights    = [pair_block_height(i) for i in range(n_pairs)]
        total_content_h = sum(pair_heights)
        acc = 8
        del pair_y_offsets[:]
        for h in pair_heights:
            pair_y_offsets.append(acc)
            acc += h

    # ---- Final answer ----
    final_answer = ""
    fa_active    = False
    fa_scroll    = 0      # horizontal scroll offset (pixels) for final answer field
    fa_cursor    = 0      # character cursor position in final_answer

    # ---- Selected-words fields: one per pair ----
    # sw_texts[i] = string typed by user for pair i
    sw_texts       = [""] * n_pairs
    sw_scroll      = [0] * n_pairs   # horizontal scroll offset (pixels) per field
    sw_cursors     = [0] * n_pairs   # character cursor position per field
    sw_active      = -1    # index of active sw field (-1 = none)

    # ---- Verdict checkboxes: one per pair ----
    # verdicts[i] in {None, "true", "false", "undecidable", "skip"}
    verdicts = [None] * n_pairs
    VERDICT_OPTIONS = ["true", "false", "undecidable", "skip"]
    VERDICT_COLORS  = {
        "true":        ( 60, 200,  80),
        "false":       (220,  70,  70),
        "undecidable": (200, 160,  30),
        "skip":        ( 80, 160, 220),
    }

    # ---- Scrolls ----
    pair_scroll   = 0
    legend_scroll = 0

    # ---- Legend items (wrapped) ----
    LEG_ITEM_LH = 18
    LEG_HDR_LH  = 28
    LEG_TEXT_W  = left_rect.width - 24

    def build_legend_items():
        items = []
        for sec_title, entries, col in sections:
            items.append({"text": sec_title, "color": col, "is_hdr": True,
                          "height": LEG_HDR_LH + 4})
            items.append({"text": "", "color": WHITE, "is_hdr": False, "height": 8})
            for entry in entries:
                if entry == "":
                    items.append({"text": "", "color": WHITE, "is_hdr": False, "height": 14})
                    continue
                for wline in wrap_text(entry, FNT_SMALL, LEG_TEXT_W - 14):
                    items.append({"text": wline, "color": WHITE, "is_hdr": False,
                                  "height": LEG_ITEM_LH})
            items.append({"text": "", "color": WHITE, "is_hdr": False, "height": 18})
        return items

    legend_items   = build_legend_items()
    legend_total_h = sum(it["height"] for it in legend_items)

    # ---- Build pair content with selected-words bars ----
    PAIR_TEXT_W = mid_rect.width - 4 - 30   # text wrap width inside mid panel

    def text_height(text, font, max_w, line_spacing=4):
        lines = wrap_text(text, font, max_w)
        return len(lines) * (font.get_linesize() + line_spacing)

    PAIR_HDR_H    = 26
    PAIR_SEP_H    = 16
    SW_BAR_H      = SW_FIELD_H + 20
    VERDICT_ROW_H = 22

    def pair_block_height(pair_idx):
        p = pairs[pair_idx]
        h  = PAIR_HDR_H
        h += text_height(p["a"], FNT_SMALL, PAIR_TEXT_W - 26) + 4
        h += VERDICT_ROW_H
        h += text_height(p["b"], FNT_SMALL, PAIR_TEXT_W - 26) + 6
        h += SW_BAR_H
        h += PAIR_SEP_H
        return h

    pair_heights    = [pair_block_height(i) for i in range(n_pairs)]
    total_content_h = sum(pair_heights)

    pair_y_offsets = []
    acc = 8
    for h in pair_heights:
        pair_y_offsets.append(acc)
        acc += h

    # ---- Cursor blink ----
    blink_t     = 0
    show_cursor = True

    running = True

    while running:
        dt = clock.tick(60) / 1000
        blink_t += dt
        if blink_t > 0.5:
            blink_t     = 0
            show_cursor = not show_cursor

        mx, my = pygame.mouse.get_pos()
        btn_hover = btn_rect.collidepoint(mx, my)

        # Toggle button: small pill in top-right corner of screen
        tog_w, tog_h = 96, 22
        tog_rect = pygame.Rect(SW - tog_w - 8, 14, tog_w, tog_h)
        tog_hover = tog_rect.collidepoint(mx, my)

        # --- Helpers: on-screen rects for interactive elements in mid panel ---
        def sw_screen_rect(i):
            vy      = pair_y_offsets[i] + pair_heights[i] - PAIR_SEP_H - SW_BAR_H + 20
            sy      = mid_rect.top + 2 + vy - pair_scroll
            field_x = mid_rect.left + 2 + 12
            field_w = mid_rect.width - 4 - 24
            return pygame.Rect(field_x, sy, field_w, SW_FIELD_H)

        # Returns list of 4 rects (true / false / undecidable / skip) for pair i
        CB_W, CB_H = 12, 12
        CB_GAPS_HIT = [75, 75, 110, 75]  # must match rendering CB_GAPS
        def verdict_screen_rects(i):
            p       = pairs[i]
            a_h     = text_height(p["a"], FNT_SMALL, (mid_rect.width - 4) - 30 - 26) + 4
            vy      = pair_y_offsets[i] + PAIR_HDR_H + a_h + 2
            sy      = mid_rect.top + 2 + vy - pair_scroll
            rects   = []
            cx      = mid_rect.left + 2 + 26
            for k in range(len(VERDICT_OPTIONS)):
                rects.append(pygame.Rect(cx, sy, CB_W, CB_H))
                cx += CB_GAPS_HIT[k]
            return rects

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Notepad toggle
                if tog_rect.collidepoint(mx, my):
                    notepad_visible = not notepad_visible
                    refresh_layout()
                    pair_scroll = 0
                    continue

                # Check verdict checkboxes first
                clicked_verdict = False
                for i in range(n_pairs):
                    for k, vr in enumerate(verdict_screen_rects(i)):
                        hit_rect = vr.inflate(10, 10)   # slightly larger hit area
                        if hit_rect.collidepoint(mx, my):
                            opt = VERDICT_OPTIONS[k]
                            verdicts[i] = None if verdicts[i] == opt else opt
                            clicked_verdict = True
                            break
                    if clicked_verdict:
                        break

                # Check sw fields
                clicked_sw = -1
                if not clicked_verdict:
                    for i in range(n_pairs):
                        r = sw_screen_rect(i)
                        if r.collidepoint(mx, my):
                            clicked_sw = i
                            break

                if clicked_sw >= 0:
                    sw_active  = clicked_sw
                    fa_active  = False
                    # Place cursor at click position within the text
                    i = clicked_sw
                    r = sw_screen_rect(i)
                    rel_x = mx - r.left - 5 + sw_scroll[i]
                    best_pos = 0
                    for p in range(len(sw_texts[i]) + 1):
                        if FNT_SMALL.size(sw_texts[i][:p])[0] <= rel_x:
                            best_pos = p
                    sw_cursors[i] = best_pos
                elif fa_rect.collidepoint(mx, my):
                    fa_active = True
                    sw_active = -1
                elif notepad_visible and right_rect.collidepoint(mx, my):
                    fa_active = False
                    sw_active = -1
                else:
                    fa_active = False
                    sw_active = -1

                if btn_rect.collidepoint(mx, my):
                    if all(v is not None for v in verdicts):
                        running = False

            if event.type == pygame.KEYDOWN:
                key = event.key

                # ESC always quits
                if key == pygame.K_ESCAPE:
                    quit_game()

                # Scroll keys (always active)
                elif key == pygame.K_PAGEDOWN:
                    pair_scroll = min(pair_scroll + 120,
                                      max(0, total_content_h - PANEL_H + 20))
                elif key == pygame.K_PAGEUP:
                    pair_scroll = max(0, pair_scroll - 120)
                elif key == pygame.K_F1:
                    legend_scroll = max(0, legend_scroll - 60)
                elif key == pygame.K_F2:
                    legend_scroll = min(legend_scroll + 60,
                                        max(0, legend_total_h - PANEL_H + 20))
                elif key == pygame.K_TAB:
                    # cycle: sw fields -> notepad -> final answer -> back
                    if sw_active >= 0:
                        sw_active = -1
                        fa_active = False
                    elif not fa_active:
                        fa_active = True
                    else:
                        fa_active = False

                # Selected-words field input
                elif sw_active >= 0:
                    i = sw_active
                    field_inner_w = mid_rect.width - 4 - 24 - 10
                    cur = sw_cursors[i]
                    if key == pygame.K_RETURN or key == pygame.K_TAB:
                        sw_active = -1
                    elif key == pygame.K_BACKSPACE:
                        if cur > 0:
                            sw_texts[i] = sw_texts[i][:cur-1] + sw_texts[i][cur:]
                            sw_cursors[i] = cur - 1
                    elif key == pygame.K_DELETE:
                        if cur < len(sw_texts[i]):
                            sw_texts[i] = sw_texts[i][:cur] + sw_texts[i][cur+1:]
                    elif key == pygame.K_LEFT:
                        sw_cursors[i] = max(0, cur - 1)
                    elif key == pygame.K_RIGHT:
                        sw_cursors[i] = min(len(sw_texts[i]), cur + 1)
                    elif key == pygame.K_HOME:
                        sw_cursors[i] = 0
                    elif key == pygame.K_END:
                        sw_cursors[i] = len(sw_texts[i])
                    else:
                        ch = event.unicode
                        if ch and ch.isprintable():
                            sw_texts[i] = sw_texts[i][:cur] + ch + sw_texts[i][cur:]
                            sw_cursors[i] = cur + 1
                    # Keep scroll so cursor stays visible
                    cur_x = FNT_SMALL.size(sw_texts[i][:sw_cursors[i]])[0]
                    if cur_x - sw_scroll[i] > field_inner_w:
                        sw_scroll[i] = cur_x - field_inner_w
                    elif cur_x < sw_scroll[i]:
                        sw_scroll[i] = cur_x

                # Final-answer field
                elif fa_active:
                    fa_field_inner_w = fa_rect.width - btn_w - 30 - 8
                    cur = fa_cursor
                    if key == pygame.K_RETURN:
                        if all(v is not None for v in verdicts):
                            running = False
                    elif key == pygame.K_BACKSPACE:
                        if cur > 0:
                            final_answer = final_answer[:cur-1] + final_answer[cur:]
                            fa_cursor -= 1
                    elif key == pygame.K_DELETE:
                        if cur < len(final_answer):
                            final_answer = final_answer[:cur] + final_answer[cur+1:]
                    elif key == pygame.K_LEFT:
                        fa_cursor = max(0, cur - 1)
                    elif key == pygame.K_RIGHT:
                        fa_cursor = min(len(final_answer), cur + 1)
                    elif key == pygame.K_HOME:
                        fa_cursor = 0
                    elif key == pygame.K_END:
                        fa_cursor = len(final_answer)
                    else:
                        ch = event.unicode
                        if ch and ch.isprintable():
                            final_answer = final_answer[:cur] + ch + final_answer[cur:]
                            fa_cursor += 1
                    # update scroll so cursor stays visible
                    cur_x = FNT_SMALL.size(final_answer[:fa_cursor])[0]
                    if cur_x - fa_scroll > fa_field_inner_w:
                        fa_scroll = cur_x - fa_field_inner_w
                    elif cur_x < fa_scroll:
                        fa_scroll = cur_x

                # Notepad
                else:
                    if key == pygame.K_RETURN:
                        notepad_lines.insert(notepad_cursor+1, "")
                        notepad_cursor += 1
                        if notepad_cursor >= notepad_scroll + NP_VISIBLE:
                            notepad_scroll += 1
                    elif key == pygame.K_BACKSPACE:
                        if notepad_lines[notepad_cursor]:
                            notepad_lines[notepad_cursor] = notepad_lines[notepad_cursor][:-1]
                        elif notepad_cursor > 0:
                            notepad_lines.pop(notepad_cursor)
                            notepad_cursor -= 1
                            if notepad_cursor < notepad_scroll:
                                notepad_scroll = max(0, notepad_scroll-1)
                    elif key == pygame.K_UP:
                        if notepad_cursor > 0:
                            notepad_cursor -= 1
                            if notepad_cursor < notepad_scroll:
                                notepad_scroll -= 1
                    elif key == pygame.K_DOWN:
                        if notepad_cursor < len(notepad_lines)-1:
                            notepad_cursor += 1
                            if notepad_cursor >= notepad_scroll + NP_VISIBLE:
                                notepad_scroll += 1
                    else:
                        ch = event.unicode
                        if ch and ch.isprintable():
                            np_w = RIGHT_W - 30
                            notepad_lines[notepad_cursor] += ch
                            # auto-wrap: if line exceeds width, break at last space
                            while FNT_SMALL.size(notepad_lines[notepad_cursor])[0] >= np_w:
                                line = notepad_lines[notepad_cursor]
                                break_at = line.rfind(" ")
                                if break_at <= 0:
                                    break_at = len(line) - 1
                                head = line[:break_at]
                                tail = line[break_at:].lstrip(" ")
                                notepad_lines[notepad_cursor] = head
                                notepad_lines.insert(notepad_cursor + 1, tail)
                                notepad_cursor += 1
                                if notepad_cursor >= notepad_scroll + NP_VISIBLE:
                                    notepad_scroll += 1

            if event.type == pygame.MOUSEWHEEL:
                if mid_rect.collidepoint(mx, my):
                    pair_scroll = max(0, min(pair_scroll - event.y*30,
                                             max(0, total_content_h - PANEL_H + 20)))
                elif left_rect.collidepoint(mx, my):
                    legend_scroll = max(0, min(legend_scroll - event.y*30,
                                               max(0, legend_total_h - PANEL_H + 20)))

        # =====================================================================
        # DRAW
        # =====================================================================
        screen.blit(BG_STARS, (0, 0))

        # Header
        pygame.draw.rect(screen, DARK_BLUE, pygame.Rect(0, 0, SW, HEADER_H))
        pygame.draw.line(screen, difficulty_col, (0, HEADER_H-2), (SW, HEADER_H-2), 2)
        draw_text(screen, f"LEVEL {level_idx+1}  |  {level['name'].upper()}",
                  FNT_MED, difficulty_col, MARGIN, 12)
        draw_text(screen,
                  "PgUp/PgDn: scroll pairs or legend"
                  "     |  Tab: switch field  |  ESC: quit",
                  FNT_TINY, MID_GREY, MARGIN, 34)

        # Notepad toggle button (top-right of header)
        tog_bg  = (60, 60, 100) if tog_hover else (35, 35, 70)
        tog_lbl = "[x] notes" if notepad_visible else "[ ] notes"
        tog_col = LIGHT_BLUE if notepad_visible else MID_GREY
        pygame.draw.rect(screen, tog_bg, tog_rect, border_radius=5)
        pygame.draw.rect(screen, tog_col, tog_rect, 1, border_radius=5)
        ts = FNT_TINY.render(tog_lbl, True, tog_col)
        screen.blit(ts, (tog_rect.centerx - ts.get_width()//2,
                         tog_rect.centery - ts.get_height()//2))
        hint_s = FNT_SMALL.render("click to show/hide notepad", True, GREY)
        screen.blit(hint_s, (tog_rect.left - hint_s.get_width() - 8,
                              tog_rect.centery - hint_s.get_height()//2))

        # ================================================================
        # LEFT: Legend (offscreen surface, clipped)
        # ================================================================
        draw_panel(screen, left_rect)
        leg_surf_w = left_rect.width - 4
        leg_surf_h = max(left_rect.height, legend_total_h + 20)
        leg_surf   = pygame.Surface((leg_surf_w, leg_surf_h))
        leg_surf.fill(PANEL_BG)
        ly = 6
        for it in legend_items:
            h = it["height"]
            if not it["text"]:
                ly += h
                continue
            if it["is_hdr"]:
                ts = FNT_MED.render(it["text"], True, it["color"])
                leg_surf.blit(ts, (6, ly))
                pygame.draw.line(leg_surf, it["color"],
                                 (4, ly + h - 3), (leg_surf_w - 4, ly + h - 3), 1)
            else:
                ts = FNT_SMALL.render(it["text"], True, it["color"])
                leg_surf.blit(ts, (14, ly))
            ly += h
        clip_rect = pygame.Rect(0, legend_scroll, leg_surf_w, left_rect.height - 4)
        screen.blit(leg_surf, (left_rect.left+2, left_rect.top+2), clip_rect)

        # ================================================================
        # MIDDLE: Sentence pairs + selected-words bars (offscreen surface)
        # ================================================================
        draw_panel(screen, mid_rect)
        mid_surf_w = mid_rect.width - 4
        mid_surf_h = max(mid_rect.height, total_content_h + 20)
        mid_surf   = pygame.Surface((mid_surf_w, mid_surf_h))
        mid_surf.fill(PANEL_BG)
        tw = mid_surf_w - 30   # text wrap width

        for i, pair in enumerate(pairs):
            py = pair_y_offsets[i]   # top of this block on virtual surface

            # --- Pair header ---
            hdr = FNT_SMALL.render(f"--- Pair {i+1} ---", True, difficulty_col)
            mid_surf.blit(hdr, (8, py))
            py += PAIR_HDR_H

            # --- Sentence a ---
            mid_surf.blit(FNT_TINY.render("a:", True, LIGHT_BLUE), (8, py))
            ah = draw_wrapped(mid_surf, pair["a"], FNT_SMALL, WHITE, 26, py, tw-26)
            py += ah + 4

            # --- Verdict checkboxes (TRUE / FALSE / UNDECIDABLE / SKIP) ---
            CB_GAPS = [75, 75, 110, 75]  # extra gap before SKIP to avoid overlap with UNDECIDABLE
            cx = 26
            for k, opt in enumerate(VERDICT_OPTIONS):
                col   = VERDICT_COLORS[opt]
                is_on = (verdicts[i] == opt)
                box_r = pygame.Rect(cx, py, CB_W, CB_H)
                pygame.draw.rect(mid_surf, col if is_on else DARK_GREY, box_r, border_radius=2)
                if is_on:
                    pygame.draw.line(mid_surf, WHITE,
                                     (box_r.left+2, box_r.centery),
                                     (box_r.left+4, box_r.bottom-3), 2)
                    pygame.draw.line(mid_surf, WHITE,
                                     (box_r.left+4, box_r.bottom-3),
                                     (box_r.right-2, box_r.top+2), 2)
                else:
                    pygame.draw.rect(mid_surf, col, box_r, 1, border_radius=2)
                lbl_s = FNT_TINY.render(opt.upper(), True, col if is_on else MID_GREY)
                mid_surf.blit(lbl_s, (cx + CB_W + 4, py))
                cx += CB_GAPS[k]
            py += VERDICT_ROW_H

            # --- Sentence b ---
            mid_surf.blit(FNT_TINY.render("b:", True, ORANGE), (8, py))
            bh = draw_wrapped(mid_surf, pair["b"], FNT_SMALL, GREY, 26, py, tw-26)
            py += bh + 6

            # --- Selected-words bar ---
            lbl = FNT_TINY.render("Selected words from b:", True, SW_FIELD_ACT)
            mid_surf.blit(lbl, (8, py))
            py += 14

            field_r = pygame.Rect(8, py, mid_surf_w - 16, SW_FIELD_H)
            is_active_sw = (sw_active == i)
            fbg  = (28, 28, 65) if is_active_sw else SW_FIELD_BG
            fbor = SW_FIELD_ACT if is_active_sw else SW_FIELD_BOR
            pygame.draw.rect(mid_surf, fbg,  field_r, border_radius=4)
            pygame.draw.rect(mid_surf, fbor, field_r, 1, border_radius=4)

            sw_surf = FNT_SMALL.render(sw_texts[i], True, WHITE)
            field_inner_w = field_r.width - 10
            text_w = sw_surf.get_width()
            if is_active_sw:
                # clamp scroll so cursor stays visible
                sw_scroll[i] = max(0, min(sw_scroll[i], max(0, text_w - field_inner_w)))
                offset = sw_scroll[i]
            else:
                # inactive: always show end of text
                offset = max(0, text_w - field_inner_w)
            sw_x = field_r.left + 5 - offset
            mid_surf.set_clip(field_r)
            mid_surf.blit(sw_surf, (sw_x, field_r.top + 6))
            mid_surf.set_clip(None)
            if is_active_sw and show_cursor:
                cur_text_w = FNT_SMALL.size(sw_texts[i][:sw_cursors[i]])[0]
                cx = field_r.left + 5 + cur_text_w - offset
                cx = max(field_r.left + 5, min(cx, field_r.right - 5))
                pygame.draw.rect(mid_surf, WHITE, pygame.Rect(cx, field_r.top+6, 2, 15))

            py += SW_FIELD_H + 6

            # --- Separator ---
            pygame.draw.line(mid_surf, DARK_GREY, (8, py+4), (mid_surf_w-8, py+4), 1)

        # Clip and blit mid surface
        mid_clip = pygame.Rect(0, pair_scroll, mid_surf_w, mid_rect.height - 4)
        screen.blit(mid_surf, (mid_rect.left+2, mid_rect.top+2), mid_clip)

        # ================================================================
        # RIGHT TOP: Notepad (only when visible)
        # ================================================================
        if notepad_visible:
            draw_notepad_bg(screen, right_rect)
            np_lbl = FNT_SMALL.render("NOTEPAD  (scratch work)", True, NOTEPAD_TXT)
            screen.blit(np_lbl, (right_rect.centerx - np_lbl.get_width()//2, right_rect.top+6))
            NP_TOP = right_rect.top + 26
            for i in range(NP_VISIBLE):
                li = notepad_scroll + i
                if li >= len(notepad_lines):
                    break
                yp  = NP_TOP + i * NP_LH
                txt = notepad_lines[li]
                s   = FNT_SMALL.render(txt, True, NOTEPAD_TXT)
                screen.blit(s, (right_rect.left+12, yp))
                if li == notepad_cursor and sw_active < 0 and not fa_active and show_cursor:
                    cx = right_rect.left + 12 + FNT_SMALL.size(txt)[0]
                    pygame.draw.rect(screen, NOTEPAD_TXT, pygame.Rect(cx, yp, 2, 15))

        # ================================================================
        # RIGHT BOTTOM: Final Answer
        # ================================================================
        fa_border = FINAL_BORDER if fa_active else (40, 100, 40)
        pygame.draw.rect(screen, FINAL_BG,    fa_rect, border_radius=8)
        pygame.draw.rect(screen, fa_border,   fa_rect, 2, border_radius=8)

        lbl_s = FNT_SMALL.render("FINAL ANSWER", True, FINAL_TXT)
        screen.blit(lbl_s, (fa_rect.left+10, fa_rect.top+8))

        field_w = fa_rect.width - btn_w - 28
        field_r = pygame.Rect(fa_rect.left+8, fa_rect.top+30, field_w, 28)
        pygame.draw.rect(screen, (30,55,30) if fa_active else (22,40,22), field_r, border_radius=4)
        pygame.draw.rect(screen, fa_border, field_r, 1, border_radius=4)
        ans_s = FNT_SMALL.render(final_answer, True, WHITE)
        fa_field_inner_w = field_r.width - 8
        fa_text_w = ans_s.get_width()
        if fa_active:
            fa_scroll = max(0, min(fa_scroll, max(0, fa_text_w - fa_field_inner_w)))
            fa_off = fa_scroll
        else:
            fa_off = max(0, fa_text_w - fa_field_inner_w)
        screen.set_clip(field_r)
        screen.blit(ans_s, (field_r.left + 4 - fa_off, field_r.top + 7))
        screen.set_clip(None)
        if fa_active and show_cursor:
            cx = field_r.left + 4 + FNT_SMALL.size(final_answer[:fa_cursor])[0] - fa_off
            pygame.draw.rect(screen, WHITE, pygame.Rect(cx, field_r.top+7, 2, 14))

        verdicts_done = all(v is not None for v in verdicts)
        if verdicts_done:
            hint_s = FNT_TINY.render("Enter to submit", True, GREY if fa_active else MID_GREY)
            screen.blit(hint_s, (fa_rect.left+10, fa_rect.top+66))
            bcol = SUBMIT_HOV if btn_hover else SUBMIT_COL
            btn_txt_col = WHITE
        else:
            missing = sum(1 for v in verdicts if v is None)
            warn1 = FNT_TINY.render("Fill in a verdict for every pair", True, RED)
            warn2 = FNT_TINY.render(f"before submitting  ({missing} missing)", True, RED)
            screen.blit(warn1, (fa_rect.left+10, fa_rect.top+66))
            screen.blit(warn2, (fa_rect.left+10, fa_rect.top+80))
            bcol = DARK_GREY
            btn_txt_col = MID_GREY

        pygame.draw.rect(screen, bcol,  btn_rect, border_radius=5)
        pygame.draw.rect(screen, MID_GREY if not verdicts_done else WHITE, btn_rect, 1, border_radius=5)
        bs = FNT_TINY.render("SUBMIT ->", True, btn_txt_col)
        screen.blit(bs, (btn_rect.centerx - bs.get_width()//2,
                         btn_rect.centery - bs.get_height()//2))

        pygame.display.flip()

    screen_level_done(level_idx, notepad_lines, sw_texts, verdicts, final_answer, participant_nr)


# ---------------------------------------------------------------------------
# LEVEL DONE SCREEN
# ---------------------------------------------------------------------------
def screen_level_done(level_idx, notepad_lines, sw_texts, verdicts, final_answer, participant_nr=""):
    """Summary screen → then feedback screen."""
    import json, os, datetime, re as _re

    is_last   = (level_idx == len(LEVELS) - 1)
    akey      = ANSWER_KEYS[level_idx]
    vcols     = {"true": (60,200,80), "false": (220,70,70),
                 "undecidable": (200,160,30), None: MID_GREY}

    # ------------------------------------------------------------------ #
    # Save human run log                                                   #
    # ------------------------------------------------------------------ #
    def _normalize(s):
        return _re.sub(r'[^a-z0-9 ]', ' ', s.lower()).split()

    pairs_log = []
    for i, pair in enumerate(LEVELS[level_idx]["pairs"]):
        ak         = akey["pairs"][i] if i < len(akey["pairs"]) else {}
        player_vd  = verdicts[i]
        player_sw  = sw_texts[i].strip()
        correct_vd = ak.get("verdict", "")
        correct_sw = ak.get("selected_words", "")
        pairs_log.append({
            "pair":            i + 1,
            "sentence_a":      pair["a"],
            "sentence_b":      pair["b"],
            "player_verdict":  player_vd,
            "correct_verdict": correct_vd,
            "verdict_correct": player_vd == correct_vd if player_vd else False,
            "player_words":    player_sw,
            "correct_words":   correct_sw,
            "words_correct":   _normalize(player_sw) == _normalize(correct_sw) if player_sw else False,
        })

    def _answer_tokens(s):
        s = s.strip().lower()
        # split on whitespace/punctuation; if result is one token, split into chars
        tokens = _re.sub(r'[^a-z0-9 ]', ' ', s).split()
        if len(tokens) == 1 and len(tokens[0]) > 1:
            tokens = list(tokens[0])
        return tokens

    valid_answers = [a.strip() for a in akey.get("emergent_answer", "").split("/")]
    fa_correct    = any(_answer_tokens(final_answer.strip()) == _answer_tokens(a)
                        for a in valid_answers)

    run_log = {
        "participant":        participant_nr,
        "level":              level_idx + 1,
        "level_name":         LEVELS[level_idx]["name"],
        "timestamp":          datetime.datetime.now().isoformat(),
        "final_answer":       final_answer.strip(),
        "correct_answer":     akey.get("emergent_answer", ""),
        "final_answer_correct": fa_correct,
        "pairs":              pairs_log,
        "notepad":            notepad_lines,
    }

    _lang_base   = os.path.join(os.path.dirname(__file__), "human_runs", "language_game")
    _is_max      = LEVELS[level_idx]["name"].lower().startswith("maximum")
    _subdir      = "max_complexity" if _is_max else "low_high_complexity"
    log_dir      = os.path.join(_lang_base, _subdir)
    os.makedirs(log_dir, exist_ok=True)
    ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"participant{participant_nr}_level{level_idx+1}_{ts}.json"
    with open(os.path.join(log_dir, fname), "w", encoding="utf-8") as f:
        json.dump(run_log, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------ #
    # Phase 1: brief submitted screen                                      #
    # ------------------------------------------------------------------ #
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:   quit_game()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: quit_game()
                if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    waiting = False

        screen.blit(BG_STARS, (0, 0))
        panel = pygame.Rect(SW//2-440, SH//2-160, 880, 320)
        draw_panel(screen, panel, border=YELLOW)

        title = "ALL LEVELS COMPLETE!" if is_last else f"LEVEL {level_idx+1} SUBMITTED"
        draw_text(screen, title, FNT_BIG, YELLOW, SW//2, panel.top+20, align="center")

        draw_text(screen, "Your final answer:", FNT_SMALL, LIGHT_BLUE,
                  panel.left+30, panel.top+65)
        ans = final_answer.strip() if final_answer.strip() else "(none entered)"
        draw_text(screen, ans, FNT_MED, WHITE, panel.left+30, panel.top+87,
                  max_width=panel.width-60)

        draw_text(screen, ">> PRESS ANY KEY TO SEE FEEDBACK <<",
                  FNT_MED, LIGHT_BLUE, SW//2, panel.bottom-38, align="center")
        clock.tick(60)
        pygame.display.flip()

    # ------------------------------------------------------------------ #
    # Phase 2: scrollable feedback screen                                  #
    # ------------------------------------------------------------------ #

    # Build the full virtual content as a list of render-items
    # Each item: ("hdr"/"row"/"sep"/"note", data, color)
    CONTENT_W = SW - 80
    TEXT_W    = CONTENT_W - 60
    fb_scroll = 0

    def build_feedback_surface():
        """Render everything onto a tall Surface and return it."""
        items = []   # (type, args)

        def add_hdr(txt, col):
            items.append(("hdr", txt, col))
        def add_row(txt, col=WHITE):
            items.append(("row", txt, col))
        def add_sep():
            items.append(("sep", "", DARK_GREY))
        def add_blank():
            items.append(("blank", "", WHITE))

        def normalize_words(s):
            import re
            return re.sub(r'[^a-z0-9 ]', ' ', s.lower()).split()

        add_hdr(f"FEEDBACK — {LEVELS[level_idx]['name'].upper()}", YELLOW)
        add_blank()

        # Emergent layer shown first so it's always visible without scrolling
        add_hdr("FINAL ANSWER", LIGHT_BLUE)
        add_row(f"  Emergent sentence: {akey['emergent']}", WHITE)
        add_row(f"  Correct answer:    {akey['emergent_answer']}", GREEN)
        add_row(f"  Your final answer: {final_answer.strip() if final_answer.strip() else '(none)'}", YELLOW)
        add_sep()
        add_blank()

        pairs = LEVELS[level_idx]["pairs"]
        for i, pair in enumerate(pairs):
            ak = akey["pairs"][i] if i < len(akey["pairs"]) else None
            player_vd = verdicts[i]
            player_sw = sw_texts[i].strip()

            correct_vd = ak["verdict"] if ak else "?"
            correct_sw = ak["selected_words"] if ak else "?"

            vd_match = (player_vd == correct_vd) if player_vd else None
            sw_match = (normalize_words(player_sw) == normalize_words(correct_sw)) if player_sw else None

            # Pair header
            add_hdr(f"Pair {i+1}", LEVELS[level_idx]["color"])
            add_blank()

            # Sentence a
            add_row(f"  a: {pair['a']}", MID_GREY)

            # Verdict comparison
            pv_str  = player_vd.upper() if player_vd else "not answered"
            cv_str  = correct_vd.upper()
            cv_col  = vcols.get(correct_vd, WHITE)
            if vd_match is True:
                add_row(f"  Verdict:  yours [{pv_str}]  correct [{cv_str}]  CORRECT", GREEN)
            elif vd_match is False:
                add_row(f"  Verdict:  yours [{pv_str}]  correct [{cv_str}]  WRONG", RED)
            else:
                add_row(f"  Verdict:  not answered  correct [{cv_str}]", MID_GREY)

            # Selected words comparison
            if player_sw:
                sw_col = GREEN if sw_match else RED
                mark   = "CORRECT" if sw_match else "WRONG"
                add_row(f"  Your words:    {player_sw}", WHITE)
                add_row(f"  Correct words: {correct_sw}", cv_col)
                add_row(f"  Words: {mark}", sw_col)
            else:
                add_row(f"  Your words:    (not entered)", MID_GREY)
                add_row(f"  Correct words: {correct_sw}", cv_col)

            # Explanation note
            if ak and ak.get("note"):
                for line in wrap_text(f"  Note: {ak['note']}", FNT_TINY, TEXT_W - 20):
                    items.append(("note", line, MID_GREY))

            add_sep()

        add_blank()
        add_blank()

        # Now render to surface
        LH_HDR  = 38
        LH_ROW  = 26
        LH_NOTE = 18
        LH_SEP  = 16
        LH_BLK  = 18

        total_h = 0
        for kind, txt, col in items:
            if kind == "hdr":   total_h += LH_HDR
            elif kind == "row": total_h += LH_ROW
            elif kind == "note":total_h += LH_NOTE
            elif kind == "sep": total_h += LH_SEP
            elif kind == "blank":total_h += LH_BLK

        surf = pygame.Surface((CONTENT_W, total_h + 40))
        surf.fill(PANEL_BG)

        cy = 10
        for kind, txt, col in items:
            if kind == "hdr":
                ts = FNT_MED.render(txt, True, col)
                surf.blit(ts, (10, cy))
                pygame.draw.line(surf, col, (8, cy+LH_HDR-3), (CONTENT_W-8, cy+LH_HDR-3), 1)
                cy += LH_HDR
            elif kind == "row":
                # wrap long rows
                for wline in wrap_text(txt, FNT_SMALL, CONTENT_W - 20):
                    ts = FNT_SMALL.render(wline, True, col)
                    surf.blit(ts, (10, cy))
                    cy += LH_ROW
            elif kind == "note":
                ts = FNT_TINY.render(txt, True, col)
                surf.blit(ts, (10, cy))
                cy += LH_NOTE
            elif kind == "sep":
                pygame.draw.line(surf, col, (8, cy+4), (CONTENT_W-8, cy+4), 1)
                cy += LH_SEP
            elif kind == "blank":
                cy += LH_BLK

        return surf, total_h + 40

    fb_surf, fb_total_h = build_feedback_surface()
    VISIBLE_H = SH - 100  # drawable height for the panel

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: quit_game()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:  quit_game()
                elif event.key == pygame.K_PAGEDOWN:
                    fb_scroll = min(fb_scroll + 120, max(0, fb_total_h - VISIBLE_H + 20))
                elif event.key == pygame.K_PAGEUP:
                    fb_scroll = max(0, fb_scroll - 120)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    running = False
            if event.type == pygame.MOUSEWHEEL:
                fb_scroll = max(0, min(fb_scroll - event.y*30,
                                       max(0, fb_total_h - VISIBLE_H + 20)))

        screen.blit(BG_STARS, (0, 0))

        # Header bar
        pygame.draw.rect(screen, DARK_BLUE, pygame.Rect(0, 0, SW, 52))
        pygame.draw.line(screen, YELLOW, (0, 50), (SW, 50), 2)
        draw_text(screen, "FEEDBACK  —  scroll with PgUp/PgDn or mousewheel",
                  FNT_SMALL, MID_GREY, 20, 10)
        if is_last:
            next_msg = "SPACE to finish"
        else:
            next_msg = f"SPACE to continue to Level {level_idx+2}"
        draw_text(screen, next_msg, FNT_SMALL, LIGHT_BLUE, 20, 30)

        # Panel border
        panel_r = pygame.Rect(30, 60, SW-60, VISIBLE_H)
        draw_panel(screen, panel_r, bg=PANEL_BG, border=PANEL_BORDER)

        # Blit clipped slice of the feedback surface
        clip = pygame.Rect(0, fb_scroll, CONTENT_W, VISIBLE_H - 4)
        screen.blit(fb_surf, (30+2, 60+2), clip)

        # Scroll indicator
        if fb_total_h > VISIBLE_H:
            pct   = fb_scroll / max(1, fb_total_h - VISIBLE_H)
            bar_h = max(30, int(VISIBLE_H * VISIBLE_H / fb_total_h))
            bar_y = 60 + int(pct * (VISIBLE_H - bar_h))
            pygame.draw.rect(screen, PANEL_BORDER,
                             pygame.Rect(SW-18, bar_y, 6, bar_h), border_radius=3)

        clock.tick(60)
        pygame.display.flip()


# ---------------------------------------------------------------------------
# CONTROL CONDITIONS
# ---------------------------------------------------------------------------
# One entry per complexity level (same order as LEVELS: low, medium, high, max).
# Each entry:
#   "label"           — shown as the section title in the screen
#   "condition"       — the emergent sentence / question shown to the participant
#   "correct_answer"  — shown on the feedback screen
#   "legend_sections" — which rule sections to show on the left panel
_CTRL_LEGEND = [
    ("Word Selection Rules", WORD_SELECT_RULES, LIGHT_BLUE),
    ("Base World Rules",     BASE_RULES,         GREY),
]

CONTROL_CONDITIONS = [
    {
        "label":          "Low Complexity — Control",
        "condition":      "What is the normal color of leaves on a tree?",
        "correct_answer": "Green",
        "legend_sections": _CTRL_LEGEND,
    },
    {
        "label":          "Medium Complexity — Control",
        "condition":      "How many hours are in 3 days?",
        "correct_answer": "72",
        "legend_sections": _CTRL_LEGEND,
    },
    {
        "label":          "High Complexity — Control",
        "condition":      "My neighbors' dog jumped pool down to the store and however way the food ran up.",
        "correct_answer": "My neighbors' dog jumped pool down to the store and however way the food ran up.",
        "legend_sections": _CTRL_LEGEND,
    },
    {
        "label":          "Maximum Complexity — Control",
        "condition": (
            "The new game goes in this way: the first sentence spells the first question. "
            "The second spells the second question, etc. Your answer to these questions may be "
            "A, B, C or D. The corresponding answers will be listed after.\n\n"
            "1: How many answers are A?    A=1  B=2  C=3  D=4\n"
            "2: I'm unhappy when I wear what color?    A=Green  B=Blue  C=Purple  D=Grass\n"
            "3: The answer to this question is?    A=A  B=B  C=C  D=D"
        ),
        "correct_answer": "B, A, A",
        "legend_sections": _CTRL_LEGEND,
    },
]


# ---------------------------------------------------------------------------
# CONTROL INTRO SCREEN
# ---------------------------------------------------------------------------
def screen_control_intro():
    """Intro shown once before the control-condition loop."""
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    quit_game()
                waiting = False
        screen.blit(BG_STARS, (0, 0))
        panel = pygame.Rect(SW // 2 - 480, SH // 2 - 200, 960, 400)
        draw_panel(screen, panel, border=LIGHT_BLUE)
        y = panel.top + 30
        draw_text(screen, "CONTROL CONDITIONS", FNT_BIG, YELLOW, SW // 2, y, align="center")
        y += 54
        lines = [
            "You will now be shown some already constructed sentences,",
            "one sentence at a time. These sentences should be treated",
            "like emergent sentences (the sentence you get once you",
            "combine the selected/extracted words) and can be either",
            "nonsense or a question/direction. You will only be asked",
            "to give the answer and no longer have to evaluate the",
            "truth of any sentences or select any words.",
            "",
            "Type your answer in the field on the right,",
            "then press SUBMIT or ENTER to confirm.",
        ]
        for line in lines:
            if line == "":
                y += 10
            else:
                draw_text(screen, line, FNT_SMALL, WHITE, panel.left + 40, y, max_width=panel.width - 80)
                y += 28
        draw_text(screen, ">> PRESS ANY KEY TO BEGIN <<", FNT_MED, GREEN,
                  SW // 2, panel.bottom - 46, align="center")
        clock.tick(60)
        pygame.display.flip()


# ---------------------------------------------------------------------------
# CONTROL LEVEL SCREEN
# ---------------------------------------------------------------------------
def screen_control(ctrl_idx, participant_nr=""):
    """Single control-condition screen.
    Layout: title top-left | left 1/2 = scrollable legend | right 1/2 = condition text
            final-answer field bottom-right corner.
    """
    import json, os, datetime

    ctrl      = CONTROL_CONDITIONS[ctrl_idx]
    label     = ctrl["label"]
    condition = ctrl["condition"]
    sections  = ctrl["legend_sections"]

    MARGIN    = 10
    TITLE_H   = 36
    PANEL_Y   = MARGIN + TITLE_H + MARGIN
    FA_H      = 120
    SUBMIT_H  = 38

    avail_w  = SW - 3 * MARGIN
    left_w   = avail_w // 2
    right_w  = avail_w - left_w
    panel_h  = SH - PANEL_Y - MARGIN

    left_x  = MARGIN
    right_x = left_x + left_w + MARGIN

    # left: legend, full height
    left_rect = pygame.Rect(left_x,  PANEL_Y, left_w, panel_h)

    # right top: condition panel — stops above the FA box
    cond_h    = panel_h - FA_H - MARGIN
    cond_rect = pygame.Rect(right_x, PANEL_Y, right_w, cond_h)

    # right bottom: final-answer panel — separate, below condition panel
    fa_rect   = pygame.Rect(right_x, PANEL_Y + cond_h + MARGIN, right_w, FA_H)
    btn_rect  = pygame.Rect(fa_rect.right - 140 - 6, fa_rect.bottom - SUBMIT_H - 6, 140, SUBMIT_H)

    # ---- Fonts for this screen (one size up) ----
    FNT_LEG_HDR  = FNT_MED      # section headers in legend
    FNT_LEG_BODY = FNT_SMALL    # body text in legend
    FNT_COND     = FNT_MED      # condition text (bigger)
    FNT_FA       = FNT_MED      # final-answer input

    # ---- Legend ----
    LEG_ITEM_LH = FNT_LEG_BODY.get_linesize() + 4
    LEG_HDR_LH  = FNT_LEG_HDR.get_linesize() + 4
    LEG_TEXT_W  = left_w - 30

    def build_legend_items():
        items = []
        for sec_title, entries, col in sections:
            items.append({"text": sec_title, "color": col, "is_hdr": True,
                          "height": LEG_HDR_LH + 4})
            items.append({"text": "", "color": WHITE, "is_hdr": False, "height": 8})
            for entry in entries:
                if entry == "":
                    items.append({"text": "", "color": WHITE, "is_hdr": False, "height": 14})
                    continue
                for wline in wrap_text(entry, FNT_LEG_BODY, LEG_TEXT_W - 14):
                    items.append({"text": wline, "color": WHITE, "is_hdr": False,
                                  "height": LEG_ITEM_LH})
            items.append({"text": "", "color": WHITE, "is_hdr": False, "height": 18})
        return items

    legend_items   = build_legend_items()
    legend_total_h = sum(it["height"] for it in legend_items)
    legend_scroll  = 0

    # ---- Final answer ----
    final_answer = ""
    fa_active    = False
    fa_scroll    = 0
    fa_cursor    = 0

    # ---- Condition text (pre-wrapped with bigger font) ----
    COND_TEXT_W = right_w - 32
    cond_lines = []
    for raw_line in condition.split("\n"):
        if raw_line == "":
            cond_lines.append(("", False))
        else:
            wrapped = wrap_text(raw_line, FNT_COND, COND_TEXT_W)
            for i, wl in enumerate(wrapped):
                cond_lines.append((wl, i == 0 and raw_line.startswith("The new game")))

    submitted = False

    def _save_log(answer):
        _base = os.path.join(os.path.dirname(__file__), "human_runs", "language_game", "control_conditions")
        os.makedirs(_base, exist_ok=True)
        ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"participant{participant_nr}_control{ctrl_idx+1}_{ts}.json"
        data = {
            "participant":     participant_nr,
            "control_idx":     ctrl_idx + 1,
            "label":           label,
            "condition":       condition,
            "player_answer":   answer.strip(),
            "correct_answer":  ctrl["correct_answer"],
            "timestamp":       datetime.datetime.now().isoformat(),
        }
        with open(os.path.join(_base, fname), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    while not submitted:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
            if event.type == pygame.MOUSEWHEEL:
                legend_scroll = max(0, legend_scroll - event.y * 20)
            if event.type == pygame.MOUSEBUTTONDOWN:
                if fa_rect.collidepoint(event.pos):
                    fa_active = True
                else:
                    fa_active = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    quit_game()
                elif fa_active:
                    cur = fa_cursor
                    if event.key == pygame.K_BACKSPACE:
                        if cur > 0:
                            final_answer = final_answer[:cur-1] + final_answer[cur:]
                            fa_cursor = cur - 1
                    elif event.key == pygame.K_DELETE:
                        if cur < len(final_answer):
                            final_answer = final_answer[:cur] + final_answer[cur+1:]
                    elif event.key == pygame.K_LEFT:
                        fa_cursor = max(0, cur - 1)
                    elif event.key == pygame.K_RIGHT:
                        fa_cursor = min(len(final_answer), cur + 1)
                    elif event.key == pygame.K_HOME:
                        fa_cursor = 0
                    elif event.key == pygame.K_END:
                        fa_cursor = len(final_answer)
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if final_answer.strip():
                            _save_log(final_answer)
                            submitted = True
                    else:
                        ch = event.unicode
                        if ch and ch.isprintable():
                            final_answer = final_answer[:cur] + ch + final_answer[cur:]
                            fa_cursor = cur + 1
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if final_answer.strip():
                        _save_log(final_answer)
                        submitted = True

            # Submit button click
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if btn_rect.collidepoint(event.pos) and final_answer.strip():
                    _save_log(final_answer)
                    submitted = True

        # ── Draw ──────────────────────────────────────────────────────────
        screen.blit(BG_STARS, (0, 0))

        # Title: top-left
        draw_text(screen, label, FNT_MED, YELLOW, MARGIN, MARGIN)

        # ── Left panel: legend ────────────────────────────────────────────
        draw_panel(screen, left_rect)
        leg_clip = pygame.Rect(left_rect.left + 2, left_rect.top + 2,
                               left_rect.width - 4, left_rect.height - 4)
        old_clip = screen.get_clip()
        screen.set_clip(leg_clip)
        cy = left_rect.top + 8 - legend_scroll
        for it in legend_items:
            if it["is_hdr"]:
                ts = FNT_LEG_HDR.render(it["text"], True, it["color"])
                screen.blit(ts, (left_rect.left + 10, cy))
                pygame.draw.line(screen, it["color"],
                                 (left_rect.left + 8,  cy + LEG_HDR_LH),
                                 (left_rect.right - 8, cy + LEG_HDR_LH), 1)
            elif it["text"]:
                ts = FNT_LEG_BODY.render(it["text"], True, it["color"])
                screen.blit(ts, (left_rect.left + 14, cy))
            cy += it["height"]
        screen.set_clip(old_clip)

        # Scrollbar for legend
        if legend_total_h > left_rect.height:
            pct   = legend_scroll / max(1, legend_total_h - left_rect.height)
            bar_h = max(24, int(left_rect.height * left_rect.height / legend_total_h))
            bar_y = left_rect.top + int(pct * (left_rect.height - bar_h))
            pygame.draw.rect(screen, PANEL_BORDER,
                             pygame.Rect(left_rect.right - 7, bar_y, 4, bar_h),
                             border_radius=2)

        # ── Right top: condition panel (separate from FA) ─────────────────
        draw_panel(screen, cond_rect)
        draw_text(screen, "CONDITION", FNT_MED, LIGHT_BLUE,
                  cond_rect.left + 14, cond_rect.top + 12)
        pygame.draw.line(screen, LIGHT_BLUE,
                         (cond_rect.left + 12, cond_rect.top + 34),
                         (cond_rect.right - 12, cond_rect.top + 34), 1)
        ty = cond_rect.top + 50
        for line, _is_title in cond_lines:
            if line == "":
                ty += 14
            else:
                col = YELLOW if _is_title else WHITE
                ts  = FNT_COND.render(line, True, col)
                screen.blit(ts, (cond_rect.left + 14, ty))
                ty += FNT_COND.get_linesize() + 6

        # ── Right bottom: final-answer panel (separate box) ───────────────
        draw_panel(screen, fa_rect, bg=FINAL_BG, border=FINAL_BORDER if fa_active else PANEL_BORDER)
        draw_text(screen, "Final answer:", FNT_SMALL, GREEN,
                  fa_rect.left + 10, fa_rect.top + 8)

        field_h     = FNT_FA.get_linesize() + 10
        field_inner = pygame.Rect(fa_rect.left + 8, fa_rect.top + 32,
                                  fa_rect.width - 18, field_h)
        pygame.draw.rect(screen, (10, 30, 10), field_inner, border_radius=3)
        pygame.draw.rect(screen, FINAL_BORDER if fa_active else PANEL_BORDER,
                         field_inner, 1, border_radius=3)

        cur_x = FNT_FA.size(final_answer[:fa_cursor])[0]
        if cur_x - fa_scroll > field_inner.width - 10:
            fa_scroll = cur_x - field_inner.width + 10
        elif cur_x - fa_scroll < 0:
            fa_scroll = max(0, cur_x - 10)
        fa_clip = pygame.Rect(field_inner.left + 2, field_inner.top,
                              field_inner.width - 4, field_inner.height)
        screen.set_clip(fa_clip)
        fa_surf = FNT_FA.render(final_answer, True, FINAL_TXT)
        screen.blit(fa_surf, (field_inner.left + 5 - fa_scroll, field_inner.top + 4))
        if fa_active and int(pygame.time.get_ticks() / 500) % 2 == 0:
            cx = field_inner.left + 5 + cur_x - fa_scroll
            pygame.draw.rect(screen, FINAL_TXT,
                             pygame.Rect(cx, field_inner.top + 4, 2, field_h - 8))
        screen.set_clip(old_clip)

        # submit button
        mx, my = pygame.mouse.get_pos()
        can_submit = bool(final_answer.strip())
        btn_col = SUBMIT_HOV if (btn_rect.collidepoint(mx, my) and can_submit) else SUBMIT_COL
        btn_alpha = 255 if can_submit else 100
        btn_surf = pygame.Surface((btn_rect.width, btn_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(btn_surf, (*btn_col, btn_alpha),
                         pygame.Rect(0, 0, btn_rect.width, btn_rect.height), border_radius=6)
        screen.blit(btn_surf, btn_rect.topleft)
        lbl = FNT_MED.render("SUBMIT", True, WHITE if can_submit else MID_GREY)
        screen.blit(lbl, (btn_rect.centerx - lbl.get_width() // 2,
                          btn_rect.centery - lbl.get_height() // 2))

        clock.tick(60)
        pygame.display.flip()

    return final_answer.strip()


# ---------------------------------------------------------------------------
# CONTROL FEEDBACK SCREEN
# ---------------------------------------------------------------------------
def screen_control_feedback(ctrl_idx, player_answer):
    """Brief feedback after a control condition: shows correct answer vs player answer."""
    import re as _re

    ctrl    = CONTROL_CONDITIONS[ctrl_idx]
    correct = ctrl["correct_answer"]

    def _norm(s):
        return _re.sub(r'[^a-z0-9 ]', ' ', s.lower()).split()

    is_correct = bool(player_answer.strip()) and (_norm(player_answer) == _norm(correct))
    verdict_text  = "CORRECT" if is_correct else "WRONG"
    verdict_color = GREEN     if is_correct else RED

    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    quit_game()
                waiting = False
        screen.blit(BG_STARS, (0, 0))
        panel = pygame.Rect(SW // 2 - 500, SH // 2 - 220, 1000, 440)
        draw_panel(screen, panel, border=LIGHT_BLUE)

        y = panel.top + 24
        draw_text(screen, f"FEEDBACK — {ctrl['label'].upper()}", FNT_MED, YELLOW,
                  SW // 2, y, align="center")
        y += 48
        pygame.draw.line(screen, YELLOW, (panel.left + 20, y), (panel.right - 20, y), 1)
        y += 16

        draw_text(screen, "Condition:", FNT_SMALL, MID_GREY, panel.left + 30, y)
        y += 22
        draw_text(screen, ctrl["condition"], FNT_TINY, WHITE,
                  panel.left + 30, y, max_width=panel.width - 60)
        y += FNT_TINY.get_linesize() * len(wrap_text(ctrl["condition"], FNT_TINY, panel.width - 60)) + 20

        pygame.draw.line(screen, DARK_GREY, (panel.left + 20, y), (panel.right - 20, y), 1)
        y += 14

        draw_text(screen, f"Your answer:    {player_answer if player_answer else '(none)'}",
                  FNT_SMALL, WHITE, panel.left + 30, y, max_width=panel.width - 60)
        y += 32
        draw_text(screen, f"Correct answer: {correct}",
                  FNT_SMALL, GREEN, panel.left + 30, y, max_width=panel.width - 60)
        y += 36

        # Verdict badge
        badge_w, badge_h = 200, 38
        badge_x = SW // 2 - badge_w // 2
        pygame.draw.rect(screen, verdict_color, pygame.Rect(badge_x, y, badge_w, badge_h), border_radius=8)
        vt = FNT_MED.render(verdict_text, True, BLACK)
        screen.blit(vt, (badge_x + badge_w // 2 - vt.get_width() // 2,
                         y + badge_h // 2 - vt.get_height() // 2))

        draw_text(screen, ">> PRESS ANY KEY TO CONTINUE <<", FNT_MED, LIGHT_BLUE,
                  SW // 2, panel.bottom - 42, align="center")
        clock.tick(60)
        pygame.display.flip()


# ---------------------------------------------------------------------------
# GAME OVER SCREENS
# ---------------------------------------------------------------------------
def screen_goodbye_standard():
    """End screen after Low/Medium/High — tells participant to come back later."""
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
            if event.type == pygame.KEYDOWN:
                quit_game()
        screen.blit(BG_STARS, (0, 0))
        pulse = abs(((pygame.time.get_ticks() / 1000) % 2) - 1)
        box_col = (int(20+30*pulse), int(20+30*pulse), int(60+40*pulse))
        panel = pygame.Rect(SW//2-460, SH//2-140, 920, 280)
        pygame.draw.rect(screen, box_col, panel, border_radius=14)
        pygame.draw.rect(screen, GREEN, panel, 2, border_radius=14)
        draw_text(screen, "Thank you for playing!", FNT_BIG, YELLOW, SW//2, SH//2-110, align="center")
        draw_text(screen, "We'll continue with the Maximum Complexity", FNT_MED, WHITE, SW//2, SH//2-55, align="center")
        draw_text(screen, "at a later moment.", FNT_MED, WHITE, SW//2, SH//2-20, align="center")
        draw_text(screen, "You can close the game now.", FNT_SMALL, GREY, SW//2, SH//2+40, align="center")
        draw_text(screen, "Press any key to exit", FNT_TINY, MID_GREY, SW//2, SH//2+80, align="center")
        clock.tick(60)
        pygame.display.flip()


def screen_game_over():
    """End screen after Maximum Complexity — full completion."""
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
            if event.type == pygame.KEYDOWN:
                quit_game()
        screen.blit(BG_STARS, (0, 0))
        draw_text(screen, "ALL LEVELS COMPLETE!", FNT_BIG, YELLOW, SW//2, SH//2-30, align="center")
        draw_text(screen, "Thank you for participating.", FNT_SMALL, GREY, SW//2, SH//2+20, align="center")
        draw_text(screen, "Press any key to exit", FNT_TINY, MID_GREY, SW//2, SH//2+50, align="center")
        clock.tick(60)
        pygame.display.flip()


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Language Game")
    parser.add_argument("--mode", choices=["standard", "maximum"], default="standard",
                        help="'standard' runs Low/Medium/High; 'maximum' runs Maximum Complexity only")
    args = parser.parse_args()

    participant_nr = screen_intro()
    screen_explain()

    if args.mode == "maximum":
        screen_level(3, participant_nr)   # index 3 = Maximum Complexity
        # Control conditions: intro → low → medium → high → max, each with feedback
        screen_control_intro()
        for ctrl_idx in range(len(CONTROL_CONDITIONS)):
            answer = screen_control(ctrl_idx, participant_nr)
            screen_control_feedback(ctrl_idx, answer)
        screen_game_over()
    else:
        for lvl_idx in range(3):          # indices 0, 1, 2 = Low/Medium/High
            screen_level(lvl_idx, participant_nr)
        screen_goodbye_standard()


if __name__ == "__main__":
    main()
