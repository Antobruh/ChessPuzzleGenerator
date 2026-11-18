# chess_logic.py
import chess
import random

# Tactical positions pool for puzzle generation (extended)
EXAMPLE_FENS = [
    # --- FORK positions ---
    "r1bqkb1r/pppp1ppp/2n2n2/4p3/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 0 1",
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 0 1",
    "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    "r1b1kb1r/ppppqppp/2n5/1B2p3/3PP3/5N2/PPP2PPP/RNBQK2R w KQkq - 2 6",
    "r4rk1/ppp2ppp/3p4/8/3nP3/2N5/PPP2PPP/R1BR2K1 b - - 0 1",
    "5rk1/p4ppp/1p6/2pP4/2Pn4/1P6/P4PPP/R3R1K1 b - - 0 1",
    "r1bq1rk1/pppp1ppp/2n2n2/4p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQ - 4 5",
    "r1bqkb1r/ppp2ppp/2n5/3pp3/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 0 5",
    "rnbqkb1r/pppp1ppp/5n2/4p3/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 2 3",
    "r1bq1rk1/pp3ppp/2pbpn2/3p4/3P4/2NBPN2/PPP2PPP/R1BQ1RK1 w - - 0 9",
    "r2q1rk1/ppp2ppp/2n1bn2/3p4/3P4/2N1BN2/PPP2PPP/R2Q1RK1 w - - 0 9",
    "2kr3r/ppp2ppp/2n1b3/8/3N4/2P5/PP3PPP/R1B1R1K1 w - - 0 1",
    "r2q1rk1/ppp2ppp/2n1bn2/3p4/3P4/2N1BN2/PPP1BPPP/R2Q1RK1 w - - 0 9",
    "r1bqkbnr/ppp2ppp/2np4/4p3/2BPP3/5N2/PPP2PPP/RNBQK2R w KQkq - 0 5",
    # --- PIN positions ---
    "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1",
    "r1bqkbnr/ppp2ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1",
    "r1bq1rk1/ppp2ppp/2n1pn2/3p2B1/3P4/2N1PN2/PPP2PPP/R2QKB1R w KQ - 0 7",
    "r3k2r/ppp2ppp/2n5/3b4/3B4/2N5/PPP2PPP/R3K2R w KQkq - 0 1",
    "r2q1rk1/ppp2ppp/2n1bn2/3p4/3P4/2N1BN2/PPP2PPP/R2QKB1R w - - 0 8",
    "rnbqkbnr/ppp2ppp/8/3p4/3P4/8/PPP2PPP/RNBQKBNR w KQkq - 0 1",
    # --- SKEWER positions ---
    "8/8/8/4k3/R7/8/8/4K3 w - - 0 1",
    "4k3/8/8/8/3r4/8/3Q4/3K4 w - - 0 1",
    "r4rk1/ppp2ppp/8/8/8/8/PPP2PPP/R3K2R w KQkq - 0 1",
    "8/2k5/8/R7/8/8/8/2K5 w - - 0 1",
    # --- BACK-RANK MATE positions ---
    "4r1k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1",
    "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1",
    "1r4k1/5ppp/8/8/8/8/5PPP/1R4K1 w - - 0 1",
    "5rk1/ppp2ppp/8/8/8/8/PPP2PPP/5RK1 w - - 0 1",
    "r3k2r/ppp2ppp/8/8/8/8/PPP2PPP/R3K2R w KQkq - 0 1",
    "2r1r1k1/pp3ppp/8/8/8/8/PP3PPP/2R1R1K1 w - - 0 1",
    # --- MIXED / DISCOVERED positions ---
    "r3r1k1/ppp2ppp/2n5/3Pp1b1/2B5/2N5/PPP2PPP/R1B1R1K1 w - - 0 1",
    "r1b1k2r/ppppqppp/2n5/2b5/3NPp2/2P1B3/PP4PP/RN1QKB1R w KQkq - 0 9",
]

def detect_fork(board: chess.Board) -> bool:
    color = not board.turn
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.color == color and piece.piece_type == chess.KNIGHT:
            attacks = board.attacks(square)
            valuable = sum(1 for t in attacks if (p := board.piece_at(t)) and p.color != color and p.piece_type in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT))
            if valuable >= 2:
                return True
    return False

def detect_pin(board: chess.Board) -> bool:
    return any(board.is_pinned(board.turn, sq) for sq in chess.SQUARES)

def detect_skewer(board: chess.Board) -> bool:
    color = not board.turn
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        # Only long-range pieces (Queen, Rook, Bishop) can perform a skewer
        if piece and piece.color == color and piece.piece_type in (chess.ROOK, chess.BISHOP, chess.QUEEN):
            attacks = list(board.attacks(square))
            
            # A skewer requires at least two pieces on the same line of attack
            # We filter for enemy pieces specifically
            targets = [board.piece_at(t) for t in attacks if board.piece_at(t) and board.piece_at(t).color != color]
            
            # If we are attacking 2+ pieces on one line, it's likely a tactical motif
            if len(targets) >= 2:
                # Optional: Ensure the first target is more valuable than the second
                # (This is the definition of a skewer vs a pin)
                return True
    return False

def detect_back_rank_mate(board: chess.Board) -> bool:
    if not board.is_check():
        return False
    king = board.king(board.turn)
    if king is None:
        return False
    rank = chess.square_rank(king)
    return (board.turn == chess.WHITE and rank == 0) or (board.turn == chess.BLACK and rank == 7)

def generate_puzzle(board: chess.Board) -> dict | None:
    original_fen = board.fen()
    tactical_moves = []
    for move in list(board.legal_moves):
        board.push(move)
        motif = None
        if detect_fork(board):
            motif = "fork"
        elif detect_pin(board):
            motif = "pin"
        elif detect_skewer(board):
            motif = "skewer"
        elif detect_back_rank_mate(board):
            motif = "back_rank_mate"
        board.pop()
        if motif:
            tactical_moves.append({"move": move, "san": board.san(move), "motif": motif})
    if not tactical_moves:
        return None
    chosen = random.choice(tactical_moves)
    return {"fen": original_fen, "solution": chosen["san"], "motif": chosen["motif"]}


def generate_random_position() -> chess.Board:
    """
    Create a unique mid-game board by playing a random number of
    semi-random legal moves from the starting position.
    Each call is extremely unlikely to produce the same FEN twice,
    giving the generator an effectively infinite supply of new positions.
    """
    board = chess.Board()
    # Play between 6 and 20 half-moves (3–10 full moves each side)
    num_moves = random.randint(6, 20)
    for _ in range(num_moves):
        legal = list(board.legal_moves)
        if not legal or board.is_game_over():
            break
        # 70% chance pick a capture/check (more tactical), 30% any move
        interesting = [m for m in legal if board.is_capture(m) or board.gives_check(m)]
        pool = interesting if interesting and random.random() < 0.70 else legal
        board.push(random.choice(pool))
    return board


def generate_batch_puzzles(n: int = 10) -> list:
    """
    Try up to n*4 random positions and return up to n puzzles found.
    This always produces NEW FENs (random play positions), so the
    duplicate-FEN check in save_puzzle will never silently block them.
    """
    found = []
    attempts = 0
    max_attempts = n * 4
    while len(found) < n and attempts < max_attempts:
        attempts += 1
        try:
            board = generate_random_position()
            puzzle = generate_puzzle(board)
            if puzzle:
                found.append(puzzle)
        except Exception:
            pass
    return found