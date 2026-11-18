# ui.py
import tkinter as tk
from tkinter import ttk, scrolledtext
import chess
import random
import threading
from chess_logic import generate_puzzle, generate_batch_puzzles, EXAMPLE_FENS
from ai_helper import give_hint, explain_solution
from storage import load_puzzles, save_puzzle, init_if_empty

SQUARE_SIZE  = 65   # pixels per square
RANK_MARGIN  = 24   # left margin reserved for rank numbers (1-8)
FILE_MARGIN  = 20   # bottom margin reserved for file letters (a-h)
TOP_MARGIN   = 4    # tiny top padding

class ChessUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("♟️ Local AI Chess Puzzle Generator")
        self.geometry("980x700")
        self.resizable(True, True)
        self.minsize(900, 640)

        self.board           = chess.Board()
        self.current_puzzle  = None
        self.solution        = None
        self.motif           = None
        self.solved          = False
        self.selected_square = None
        self.highlighted     = []          # list of (rank, file) currently green

        # Shuffled-deck queue: puzzles play in random order, no repeats
        # until every puzzle has been seen, then the deck reshuffles.
        self._puzzle_queue   = []          # remaining puzzles this round
        self._puzzle_index   = 0           # how many played this round
        self._puzzle_total   = 0           # size of current deck

        self.create_widgets()
        init_if_empty()
        self.load_new_puzzle()

    # ------------------------------------------------------------------ #
    #  Widget layout
    # ------------------------------------------------------------------ #
    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=12)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(main_frame, text="♟️ Local AI Chess Puzzle Generator",
                  font=("Arial", 16, "bold")).pack(pady=(0, 12))

        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill="both", expand=True)

        # ── Left: chessboard canvas ────────────────────────────────────
        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side="left", padx=(0, 20), anchor="n")

        self.board_frame = ttk.Frame(left_frame)
        self.board_frame.pack()
        self.create_chessboard()

        # ── Right: controls + hint panel ──────────────────────────────
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side="right", fill="both", expand=True)

        self.status_label = ttk.Label(
            right_frame, text="Click piece → Click destination",
            font=("Arial", 11))
        self.status_label.pack(anchor="w", pady=5)

        self.feedback = ttk.Label(right_frame, text="", font=("Arial", 11))
        self.feedback.pack(anchor="w", pady=5)

        self.progress_label = ttk.Label(
            right_frame, text="",
            font=("Arial", 9), foreground="#777777")
        self.progress_label.pack(anchor="w", pady=(0, 4))

        control_frame = ttk.LabelFrame(right_frame, text=" Controls ", padding=12)
        control_frame.pack(fill="x", pady=10)

        # ── Puzzle counter ─────────────────────────────────────────────
        self.puzzle_count_label = ttk.Label(
            control_frame,
            text=self._puzzle_count_text(),
            font=("Arial", 9),
            foreground="#555555"
        )
        self.puzzle_count_label.pack(anchor="w", pady=(0, 6))

        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(fill="x", pady=(0, 6))
        ttk.Button(btn_frame, text="New Puzzle",    command=self.load_new_puzzle).pack(side="left", padx=4, fill="x", expand=True)
        ttk.Button(btn_frame, text="Retry Puzzle",  command=self.retry_puzzle).pack(side="left", padx=4, fill="x", expand=True)
        ttk.Button(btn_frame, text="Get Hint",      command=self.get_hint).pack(side="left", padx=4, fill="x", expand=True)
        ttk.Button(btn_frame, text="Show Solution", command=self.show_solution).pack(side="left", padx=4, fill="x", expand=True)

        # ── Generate more puzzles button ───────────────────────────────
        gen_frame = ttk.Frame(control_frame)
        gen_frame.pack(fill="x", pady=(4, 0))
        self.gen_btn = ttk.Button(
            gen_frame,
            text="⚙ Generate More Puzzles (AI)",
            command=self.generate_more_puzzles
        )
        self.gen_btn.pack(fill="x", padx=4)

        hint_frame = ttk.LabelFrame(right_frame, text=" Hint & AI Explanation ", padding=10)
        hint_frame.pack(fill="both", expand=True, pady=10)

        self.hint_text = scrolledtext.ScrolledText(
            hint_frame, height=14, font=("Arial", 10),
            wrap=tk.WORD, background="#f8f9fa")
        self.hint_text.pack(fill="both", expand=True)

        ttk.Label(main_frame, text="Fully local • Click to move • mistral:7b",
                  font=("Arial", 9), foreground="gray").pack(pady=(12, 0))

    # ------------------------------------------------------------------ #
    #  Canvas-based chessboard
    # ------------------------------------------------------------------ #
    def create_chessboard(self):
        """Pixel-perfect board: squares + coordinates rendered on one Canvas."""
        canvas_w = RANK_MARGIN + 8 * SQUARE_SIZE
        canvas_h = TOP_MARGIN  + 8 * SQUARE_SIZE + FILE_MARGIN

        self.canvas = tk.Canvas(
            self.board_frame,
            width=canvas_w, height=canvas_h,
            highlightthickness=0, bg="#d6d0c4"
        )
        self.canvas.pack()

        LIGHT, DARK = "#f0d9b5", "#b58863"

        # ── Square rectangles ──────────────────────────────────────────
        self.sq_rects = {}
        for rank in range(8):
            for file in range(8):
                x1 = RANK_MARGIN + file * SQUARE_SIZE
                y1 = TOP_MARGIN  + rank * SQUARE_SIZE
                x2, y2 = x1 + SQUARE_SIZE, y1 + SQUARE_SIZE
                fill = LIGHT if (rank + file) % 2 == 0 else DARK
                rect = self.canvas.create_rectangle(
                    x1, y1, x2, y2, fill=fill, outline="", tags="square")
                self.sq_rects[(rank, file)] = rect

        # ── Rank labels: 8 at top → 1 at bottom ──────────────────────
        for rank in range(8):
            cy = TOP_MARGIN + rank * SQUARE_SIZE + SQUARE_SIZE // 2
            self.canvas.create_text(
                RANK_MARGIN // 2, cy,
                text=str(8 - rank),
                font=("Arial", 11, "bold"), fill="#333333", anchor="center")

        # ── File labels: a … h ────────────────────────────────────────
        for file in range(8):
            cx = RANK_MARGIN + file * SQUARE_SIZE + SQUARE_SIZE // 2
            self.canvas.create_text(
                cx, TOP_MARGIN + 8 * SQUARE_SIZE + FILE_MARGIN // 2,
                text="abcdefgh"[file],
                font=("Arial", 11, "bold"), fill="#333333", anchor="center")

        # ── Piece text items (one per square) ─────────────────────────
        self.piece_texts = {}
        for rank in range(8):
            for file in range(8):
                cx = RANK_MARGIN + file * SQUARE_SIZE + SQUARE_SIZE // 2
                cy = TOP_MARGIN  + rank * SQUARE_SIZE + SQUARE_SIZE // 2
                tid = self.canvas.create_text(
                    cx, cy, text="",
                    font=("Arial", 36), anchor="center", tags="piece")
                self.piece_texts[(rank, file)] = tid

        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self._draw_pieces()

    # ── Piece map ──────────────────────────────────────────────────────
    _PIECE_MAP = {
        'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'Q': '♕', 'K': '♔',
        'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛', 'k': '♚'
    }

    def _draw_pieces(self):
        for rank in range(8):
            for file in range(8):
                sq     = chess.square(file, 7 - rank)
                piece  = self.board.piece_at(sq)
                symbol = self._PIECE_MAP.get(piece.symbol(), "") if piece else ""
                self.canvas.itemconfig(self.piece_texts[(rank, file)], text=symbol)

    def update_board_display(self):
        self._draw_pieces()

    # ── Canvas click → board coordinates ──────────────────────────────
    def _on_canvas_click(self, event):
        rx = event.x - RANK_MARGIN
        ry = event.y - TOP_MARGIN
        if rx < 0 or rx >= 8 * SQUARE_SIZE or ry < 0 or ry >= 8 * SQUARE_SIZE:
            return
        file = int(rx // SQUARE_SIZE)
        rank = int(ry // SQUARE_SIZE)
        self.on_square_click(rank, file)

    # ------------------------------------------------------------------ #
    #  Square interaction
    # ------------------------------------------------------------------ #
    def on_square_click(self, rank, file):
        if self.solved or not self.current_puzzle:
            return

        square = chess.square(file, 7 - rank)

        if self.selected_square is None:
            piece = self.board.piece_at(square)
            if piece and piece.color == self.board.turn:
                self.selected_square = square
                self.highlight_legal_moves(square)
        else:
            move = chess.Move(self.selected_square, square)
            if move in self.board.legal_moves:
                san = self.board.san(move)
                self.board.push(move)
                self.update_board_display()
                self.clear_highlights()

                if san == self.solution:
                    self.feedback.config(text="✅ Correct! Great job!", foreground="green")
                    self.solved = True
                else:
                    self.feedback.config(text="Legal move, but not the puzzle solution", foreground="orange")

                self.selected_square = None
            else:
                piece = self.board.piece_at(square)
                if piece and piece.color == self.board.turn:
                    self.clear_highlights()
                    self.selected_square = square
                    self.highlight_legal_moves(square)
                else:
                    self.clear_highlights()
                    self.selected_square = None

    def highlight_legal_moves(self, from_square):
        self.clear_highlights()
        for move in self.board.legal_moves:
            if move.from_square == from_square:
                to_rank = 7 - chess.square_rank(move.to_square)
                to_file = chess.square_file(move.to_square)
                self.canvas.itemconfig(self.sq_rects[(to_rank, to_file)], fill="#90EE90")
                self.highlighted.append((to_rank, to_file))

    def clear_highlights(self):
        LIGHT, DARK = "#f0d9b5", "#b58863"
        for r, f in self.highlighted:
            color = LIGHT if (r + f) % 2 == 0 else DARK
            self.canvas.itemconfig(self.sq_rects[(r, f)], fill=color)
        self.highlighted.clear()

    # ------------------------------------------------------------------ #
    #  Puzzle management
    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #
    def _puzzle_count_text(self) -> str:
        n = len(load_puzzles())
        return f"📚 Puzzle bank: {n} puzzle{'s' if n != 1 else ''}"

    def _refresh_puzzle_count(self):
        self.puzzle_count_label.config(text=self._puzzle_count_text())

    # ------------------------------------------------------------------ #
    #  Puzzle management
    # ------------------------------------------------------------------ #
    def _refill_queue(self):
        """Reload all puzzles, shuffle them into the queue, and reset progress."""
        puzzles = load_puzzles()
        if not puzzles:
            return False
        self._puzzle_queue  = puzzles[:]
        random.shuffle(self._puzzle_queue)
        self._puzzle_index  = 0
        self._puzzle_total  = len(self._puzzle_queue)
        return True

    def load_new_puzzle(self):
        # If queue is empty (or first run), refill it
        if not self._puzzle_queue:
            if not self._refill_queue():
                # Try seeding from scratch
                self.status_label.config(text="No puzzles found. Initializing...", foreground="orange")
                self.feedback.config(text="Creating example puzzles now...", foreground="blue")
                init_if_empty()
                if not self._refill_queue():
                    self.status_label.config(text="Still no puzzles. Check storage.py", foreground="red")
                    return
            if self._puzzle_index > 0:
                # Deck just reshuffled — let the user know
                self.hint_text.delete(1.0, tk.END)
                self.hint_text.insert(tk.END,
                    "🔄 You've completed the full puzzle bank!\n"
                    "Reshuffling all puzzles for another round...\n"
                )

        self.current_puzzle  = self._puzzle_queue.pop(0)
        self._puzzle_index  += 1
        self.board           = chess.Board(self.current_puzzle["fen"])
        self.solution        = self.current_puzzle["solution"]
        self.motif           = self.current_puzzle["motif"]
        self.solved          = False
        self.selected_square = None
        self.highlighted     = []

        self.hint_text.delete(1.0, tk.END)
        desc = self.current_puzzle.get('description', '')
        motif_text = f"Motif: {self.motif.upper()}"
        if desc:
            motif_text += f"  •  {desc}"
        self.feedback.config(text=motif_text, foreground="blue")
        self.status_label.config(text="Click piece → Click destination", foreground="black")
        self.progress_label.config(
            text=f"Puzzle {self._puzzle_index} / {self._puzzle_total}  "
                 f"({len(self._puzzle_queue)} remaining in this round)"
        )
        self._refresh_puzzle_count()
        self.update_board_display()

    def generate_more_puzzles(self):
        """Generate new puzzles from random positions in a background thread."""
        self.gen_btn.config(state="disabled", text="⏳ Generating...")
        self.hint_text.delete(1.0, tk.END)
        self.hint_text.insert(tk.END,
            "⚙️ Generating 10 new puzzles from random game positions...\n\n"
            "Playing random moves to create unique mid-game positions,\n"
            "then scanning for forks, pins, skewers and back-rank mates.\n\n"
            "Please wait..."
        )
        self.update_idletasks()

        def _worker():
            puzzles = generate_batch_puzzles(n=10)
            saved   = []          # only the ones actually saved (new, not duplicate)
            for p in puzzles:
                try:
                    save_puzzle(p)
                    saved.append(p)
                except Exception as e:
                    print(f"Save error: {e}")
            self.after(0, lambda: self._on_generation_done(saved, len(puzzles)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_generation_done(self, saved: list, tried: int):
        self.gen_btn.config(state="normal", text="⚙ Generate More Puzzles (AI)")
        added = len(saved)
        total = len(load_puzzles())

        # Inject new puzzles into the live queue immediately so remaining count rises
        if saved:
            insert_at = min(len(self._puzzle_queue), 1)   # put them near the front
            for i, p in enumerate(random.sample(saved, len(saved))):
                self._puzzle_queue.insert(insert_at + i, p)
            self._puzzle_total += added
            # Update progress label
            self.progress_label.config(
                text=f"Puzzle {self._puzzle_index} / {self._puzzle_total}  "
                     f"({len(self._puzzle_queue)} remaining in this round)"
            )

        self.hint_text.delete(1.0, tk.END)
        if added > 0:
            self.hint_text.insert(tk.END,
                f"✅ Generated {added} new puzzle{'s' if added != 1 else ''}!\n\n"
                f"📚 Total puzzles in bank: {total}\n"
                f"🎯 Added to current round queue — play them now with 'New Puzzle'!"
            )
        else:
            self.hint_text.insert(tk.END,
                f"ℹ Checked {tried} positions — no new unique tactical motifs found.\n\n"
                f"All positions may already be in the puzzle bank ({total} total).\n"
                f"You can still click 'New Puzzle' to play existing ones!"
            )
        self._refresh_puzzle_count()

    def retry_puzzle(self):
        if not self.current_puzzle:
            return
        self.board           = chess.Board(self.current_puzzle["fen"])
        self.solved          = False
        self.selected_square = None
        self.hint_text.delete(1.0, tk.END)
        self.feedback.config(text=f"Motif: {self.motif.upper()}", foreground="blue")
        self.status_label.config(text="Try again! Click piece → destination", foreground="black")
        self.clear_highlights()
        self.update_board_display()

    def get_hint(self):
        if not self.current_puzzle or self.solved:
            return
        self.hint_text.delete(1.0, tk.END)
        self.hint_text.insert(tk.END, "🤖 Thinking...\n\n")
        self.update_idletasks()
        hint = give_hint(self.board.fen(), self.motif, self.solution)
        self.hint_text.delete(1.0, tk.END)
        self.hint_text.insert(tk.END, f"💡 HINT:\n\n{hint}")

    def show_solution(self):
        if not self.current_puzzle:
            return
        self.hint_text.delete(1.0, tk.END)
        self.hint_text.insert(tk.END, f"📌 SOLUTION: {self.solution}\n\n")
        self.hint_text.insert(tk.END, "🤖 AI Explanation:\n")
        self.update_idletasks()
        explanation = explain_solution(self.board.fen(), self.solution, self.motif)
        self.hint_text.insert(tk.END, explanation)

        try:
            move_obj = self.board.parse_san(self.solution)
            self.board.push(move_obj)
            self.update_board_display()
            self.solved = True
        except Exception:
            pass