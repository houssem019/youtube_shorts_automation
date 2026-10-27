"""Storytelling angle of a long video, per style (the styles and their detectors live in pipeline/styles.py).

The Shorts briefs are about a 45-second highlight; these are about how a 5-10 minute breakdown is told:
what the cold open teases, which chapter gets the most time, what the lessons are built around.
"""

BRIEFS = {
    'missed_mate': """Angle: a forced mate was on the board and nobody (or the wrong player) saw it.
Cold open: show the position with the mate on the board and ask whether the viewer can see what both players missed.
Spend the most time on the moments before and after the missed mate: why it was hard to see, the pattern behind
it, and a "think" pause on it. Show the mate as a variation. Lessons: the mating pattern and how to look for it.""",
    'time_scramble': """Angle: the clock decided this game as much as the moves did. Use the clock facts.
Cold open: how little time was left at the critical moment.
Walk through how the time was spent: where a player thought too long, what simple moves would have saved time,
how the position got harder as the clock ran down. Lessons include one practical time-management lesson.""",
    'comeback': """Angle: the side that lost was clearly winning first. The story is how the advantage slipped away.
Cold open: the position where the loser was winning and how big the advantage was.
Give the winning phase its due (what the plan should have been, shown as a variation), then slow down on the
moves where it drained away. Lessons: converting an advantage.""",
    'puzzle_challenge': """Angle: the viewer plays along. Several positions in this game have one strong move.
Cold open: challenge the viewer that there are moves in this game they can find. Use "think" pauses at the best
moments (up to three) and reveal each answer right after, with the engine line as a variation.
Lessons: the patterns behind the puzzles.""",
    'underdog': """Angle: the lower-rated player won. Mention the rating gap once, then let the chess speak.
Cold open: the rating gap and the moment the favourite's position started to crack.
Give the underdog credit for good decisions (name them), show where the favourite drifted.
Lessons: what decided the game beyond rating.""",
    'chaos': """Angle: a wild game where the advantage changes hands again and again.
Cold open: promise a messy, unpredictable game; show the craziest position.
Keep track of the swings (the eval graph card helps). For each big swing: what went wrong and the move that
held. Lessons: staying calm and checking the opponent's threats.""",
    'miniature': """Angle: the game was over quickly; an opening mistake was punished.
Cold open: how fast it ended. Spend the most time on the opening: the normal plan, where it went wrong, and the
punishment, with variations showing what should have been played. This video can be at the short end (5-6 minutes).
Lessons: the opening principle that was broken.""",
    'long_grind': """Angle: a long, patient game decided in the endgame. Respect the fight.
Cold open: the endgame moment where it was finally decided.
Move faster through the early game (skip), slow down in the endgame: the plan (king activity, passed pawns, the
key squares), the slip, and what would have held. Lessons: one endgame technique.""",
    'turning_point': """Angle: one move decided the game. Classic breakdown.
Cold open: the turning point position and why it matters.
Build up to it: the opening ideas, the middlegame plans, then slow right down on the turning point with the
candidates card, a "think" pause and the better move as a variation. Lessons: what to check before such a move.""",
    'how_did_we_get_here': """Angle: start at the end and make the viewer wonder how the game got there.
Cold open: the final position or the result as a question.
Tell the game as the answer: spend time only on the moves that explain the ending. Lessons: the chain of small
decisions that led there.""",
}
DEFAULT = BRIEFS['turning_point']
