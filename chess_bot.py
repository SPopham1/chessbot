import chess
import random, time

class TranspositionTable:
    """Stores previously evaluated positions to avoid recalculation.

    Each entry stores (depth, eval, flag, best_move) where flag is
    one of 'EXACT', 'LOWER', 'UPPER'. The lookup method accepts alpha/beta
    so it can determine whether a stored bound is usable.
    """
    def __init__(self, size=100000):
        self.table = {}
        self.size = size

    def store(self, key, depth, eval_score, flag='EXACT', best_move=None):
        """Store evaluation for a board position with a flag and optional best move."""
        if len(self.table) > self.size:
            self.table.clear()  # Simple cache eviction
        self.table[key] = (depth, eval_score, flag, best_move)

    def lookup(self, key, depth, alpha, beta):
        """Retrieve a usable evaluation or None.

        Returns a tuple (best_move, eval, flag) when entry is usable for the
        provided alpha/beta/depth. Otherwise returns None.
        """
        if key in self.table:
            stored_depth, eval_score, flag, best_move = self.table[key]
            if stored_depth >= depth:
                if flag == 'EXACT':
                    return best_move, eval_score, flag
                if flag == 'LOWER' and eval_score >= beta:
                    return best_move, eval_score, flag
                if flag == 'UPPER' and eval_score <= alpha:
                    return best_move, eval_score, flag
        return None

    def clear(self):
        """Clear the transposition table"""
        self.table.clear()

class ChessBot:
    def __init__(self, width=800, height=800, offset=(0,0)):
        self.board = chess.Board()
        self.width = width
        self.height = height
        self.offset = offset
        self.tile_width = width // 8
        self.tile_height = height // 8
        self.selected_piece = None
        self.turn = "white"
        self.game_moves = ""
        self.move_number = 0
        self.history_table = [[0] * 8 for _ in range(8)]
        self.killer_moves = [None] * 5
        self.transposition_table = TranspositionTable(size=100000)
        # MVV-LVA table for capture ordering (victim piece -> attacker piece score)
        self.mvv_lva = {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3,
            chess.ROOK: 5,
            chess.QUEEN: 9,
            chess.KING: 1000,
        }

    def make_move(self, move_uci):
        move = chess.Move.from_uci(move_uci)
        if move in self.board.legal_moves:
            self.board.push(move)
            self.switch_player()
            return True
        else:
            return False

    def switch_player(self):
        """Switch the turn between white and black"""
        self.turn = 'white' if self.turn == 'black' else 'black'

    def get_board_fen(self):
        return self.board.fen()

    def reset_board(self):
        self.board.reset()

    def get_possible_moves(self, colour=None):
        """Get all legal moves for a colour (or all if None)"""
        return list(self.board.legal_moves)

    def evaluate(self):
        """Evaluation based on material balance, pawn structure, and king safety"""
        pawn_value = 1
        knight_value = 3
        bishop_value = 3
        rook_value = 5
        queen_value = 10

        passed_pawn_bonuses = [0, 120, 80, 50, 30, 15, 15, 120]
        isolated_pawn_penalty = [0, -10, -25, -50, -75, -75, -75, -75, -75]
        king_pawn_shield_scores = [4, 7, 4, 3, 6, 3]

        eval_score = 0
        white_isolated_pawns = 0
        black_isolated_pawns = 0

        for square, piece in self.board.piece_map().items():
            value = 0
            file_index = square % 8
            rank_index = square // 8

            if piece.piece_type == 1:  # pawn
                value = pawn_value
                
                # Check if pawn is passed
                if piece.color:  # white pawn
                    if self._is_passed_pawn(square, piece.color):
                        value += passed_pawn_bonuses[rank_index]
                    if self._is_isolated_pawn(square, piece.color):
                        white_isolated_pawns += 1
                else:  # black pawn
                    if self._is_passed_pawn(square, piece.color):
                        value += passed_pawn_bonuses[7 - rank_index]
                    if self._is_isolated_pawn(square, piece.color):
                        black_isolated_pawns += 1
                        
            elif piece.piece_type == 2:  # knight
                value = knight_value
            elif piece.piece_type == 3:  # bishop
                value = bishop_value
            elif piece.piece_type == 4:  # rook
                value = rook_value
            elif piece.piece_type == 5:  # queen
                value = queen_value
            elif piece.piece_type == 6:  # king
                # Bonus for king pawn shield
                if piece.color:  # white king
                    shield_bonus = self._calculate_king_shield(square, True)
                    value += shield_bonus
                else:  # black king
                    shield_bonus = self._calculate_king_shield(square, False)
                    value += shield_bonus

            if piece.color:  # white
                eval_score += value
            else:  # black
                eval_score -= value

        # Apply isolated pawn penalties
        eval_score += isolated_pawn_penalty[white_isolated_pawns]
        eval_score -= isolated_pawn_penalty[black_isolated_pawns]

        return eval_score

    def _score_move_mvv_lva(self, move):
        """Score a capture using MVV-LVA; promotions are high priority."""
        score = 0
        if self.board.is_capture(move):
            victim = self.board.piece_at(move.to_square)
            attacker = self.board.piece_at(move.from_square)
            if victim and attacker:
                score += 1000 * self.mvv_lva.get(victim.piece_type, 0) - self.mvv_lva.get(attacker.piece_type, 0)
            else:
                score += 1000
        if move.promotion:
            score += 800
        # history heuristic
        score += self.history_table[move.from_square // 8][move.from_square % 8]
        return score

    def order_moves(self, moves, depth):
        """Order moves to improve alpha-beta pruning: TT move, captures (MVV-LVA), killer moves, history."""
        scored = []
        tt_key = self.generate_transposition_key()
        tt_entry = self.transposition_table.table.get(tt_key)
        tt_best = tt_entry[3] if tt_entry else None

        for move in moves:
            score = 0
            if tt_best is not None and move == tt_best:
                score += 1000000
            score += self._score_move_mvv_lva(move)
            # killer moves bonus
            if depth < len(self.killer_moves) and self.killer_moves[depth] == move:
                score += 500
            scored.append((score, move))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored]

    def _is_passed_pawn(self, square, is_white):
        """Check if a pawn is passed (no opposing pawns ahead)"""
        file_index = square % 8
        rank_index = square // 8

        if is_white:
            # Check ranks above the pawn on adjacent files
            for rank in range(rank_index + 1, 8):
                for file in [file_index - 1, file_index, file_index + 1]:
                    if 0 <= file < 8:
                        check_square = rank * 8 + file
                        piece = self.board.piece_at(check_square)
                        if piece and piece.piece_type == 1 and not piece.color:  # black pawn
                            return False
        else:
            # Check ranks below the pawn on adjacent files
            for rank in range(rank_index - 1, -1, -1):
                for file in [file_index - 1, file_index, file_index + 1]:
                    if 0 <= file < 8:
                        check_square = rank * 8 + file
                        piece = self.board.piece_at(check_square)
                        if piece and piece.piece_type == 1 and piece.color:  # white pawn
                            return False
        return True

    def _is_isolated_pawn(self, square, is_white):
        """Check if a pawn is isolated (no pawns on adjacent files)"""
        file_index = square % 8

        for file in [file_index - 1, file_index + 1]:
            if 0 <= file < 8:
                for rank in range(8):
                    check_square = rank * 8 + file
                    piece = self.board.piece_at(check_square)
                    if piece and piece.piece_type == 1 and piece.color == is_white:
                        return False
        return True

    def _calculate_king_shield(self, square, is_white):
        """Calculate king pawn shield bonus"""
        king_pawn_shield_scores = [4, 7, 4, 3, 6, 3]
        file_index = square % 8
        rank_index = square // 8
        shield_bonus = 0

        if is_white:
            # Check pawns in front of white king (rank 1 area)
            for file in range(max(0, file_index - 1), min(8, file_index + 2)):
                for rank in range(rank_index, min(8, rank_index + 2)):
                    check_square = rank * 8 + file
                    piece = self.board.piece_at(check_square)
                    if piece and piece.piece_type == 1 and piece.color:  # white pawn
                        shield_bonus += king_pawn_shield_scores[min(5, file)]
        else:
            # Check pawns in front of black king (rank 6 area)
            for file in range(max(0, file_index - 1), min(8, file_index + 2)):
                for rank in range(max(0, rank_index - 1), rank_index + 1):
                    check_square = rank * 8 + file
                    piece = self.board.piece_at(check_square)
                    if piece and piece.piece_type == 1 and not piece.color:  # black pawn
                        shield_bonus += king_pawn_shield_scores[min(5, file)]

        return shield_bonus

    def make_bot_move(self, max_depth=6, time_limit_seconds=5):
        """AI makes the best move using iterative deepening with transposition table"""
        best_move = self.iterative_deepening(max_depth, time_limit_seconds)
        if best_move:
            self.board.push(best_move)
            self.switch_player()
            return best_move
        return None

    def iterative_deepening(self, max_depth, time_limit_seconds):
        """Iterative deepening: gradually increase search depth until time limit"""
        start_time = time.time()
        best_move = None
        depth = 1

        while depth <= max_depth:
            elapsed_time = time.time() - start_time

            if elapsed_time >= time_limit_seconds:
                break  # Time limit exceeded

            # Do NOT clear the transposition table between iterations; reuse stored info
            move, _ = self.search(depth, float("-inf"), float("inf"), self.board.turn, start_time, time_limit_seconds)

            if move is not None:
                best_move = move

            depth += 1

        return best_move

    def generate_transposition_key(self):
        """Generate a unique key for the current board state"""
        # Use board FEN as key (simpler but effective)
        return self.board.fen()

    def quiescence(self, alpha, beta):
        """Quiescence search: only consider captures/promotions to avoid horizon effect."""
        stand_pat = self.evaluate()
        if stand_pat >= beta:
            return beta
        if alpha < stand_pat:
            alpha = stand_pat

        # Only consider capture moves in quiescence
        for move in sorted(self.board.legal_moves, key=lambda m: -self._score_move_mvv_lva(m)):
            if not self.board.is_capture(move) and not move.promotion:
                continue
            self.board.push(move)
            score = -self.quiescence(-beta, -alpha)
            self.board.pop()

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha

    def search(self, depth, alpha, beta, is_maximizing, start_time=None, time_limit=None):
        """Negamax-style search with alpha-beta, transposition table, move ordering and quiescence."""
        # Time cutoff
        if start_time is not None and time_limit is not None:
            if time.time() - start_time >= time_limit:
                return None, 0

        transposition_key = self.generate_transposition_key()

        # TT lookup
        tt_hit = self.transposition_table.lookup(transposition_key, depth, alpha, beta)
        if tt_hit is not None:
            tt_move, tt_eval, tt_flag = tt_hit
            return tt_move, tt_eval

        if depth == 0 or self.board.is_game_over():
            # Use quiescence at leaf
            eval_score = self.quiescence(alpha, beta) if depth == 0 else self.evaluate()
            self.transposition_table.store(transposition_key, depth, eval_score, 'EXACT', None)
            return None, eval_score

        best_move = None
        best_eval = float('-inf')

        moves = list(self.board.legal_moves)
        moves = self.order_moves(moves, depth)

        for move in moves:
            # Time cutoff during long searches
            if start_time is not None and time_limit is not None and time.time() - start_time >= time_limit:
                break

            self.board.push(move)
            _, eval_score = self.search(depth - 1, -beta, -alpha, not is_maximizing, start_time, time_limit)
            if eval_score is None:
                # time cutoff propagated
                self.board.pop()
                break
            eval_score = -eval_score
            self.board.pop()

            if eval_score > best_eval:
                best_eval = eval_score
                best_move = move

            if eval_score > alpha:
                alpha = eval_score

            if alpha >= beta:
                # Beta cutoff: store killer move
                if depth < len(self.killer_moves):
                    self.killer_moves[depth] = move
                # store as LOWER bound
                self.transposition_table.store(transposition_key, depth, best_eval, 'LOWER', best_move)
                # update history heuristic
                self.history_table[move.from_square // 8][move.from_square % 8] += 1
                return best_move, best_eval

        # If we exit the loop normally, store as EXACT
        flag = 'EXACT'
        self.transposition_table.store(transposition_key, depth, best_eval if best_eval != float('-inf') else self.evaluate(), flag, best_move)
        return best_move, best_eval

if __name__ == "__main__":
    bot = ChessBot()
    
    print("=" * 60)
    print("Welcome to Chess Bot!")
    print("=" * 60)
    print("You are playing as WHITE. The bot plays as BLACK.")
    print("Enter moves in UCI format (e.g., e2e4, g1f3)")
    print("Type 'board' to see the current board state")
    print("Type 'moves' to see all legal moves")
    print("Type 'quit' to exit the game")
    print("=" * 60)
    print()
    
    game_over = False
    
    while not game_over:
        # Display board
        print(bot.board)
        print()
        
        # Check game status
        if bot.board.is_checkmate():
            if bot.turn == "white":
                print("Checkmate! Black wins!")
            else:
                print("Checkmate! White wins!")
            game_over = True
            break
        elif bot.board.is_stalemate():
            print("Stalemate! Game is a draw.")
            game_over = True
            break
        elif bot.board.is_check():
            print(f"{bot.turn.upper()} is in check!")
        
        # # Player's turn (White)
        # if bot.turn == "white":
        #     while True:
        #         user_input = input("Your move (white): ").strip().lower()
                
        #         if user_input == "quit":
        #             print("Thanks for playing!")
        #             game_over = True
        #             break
        #         elif user_input == "board":
        #             print(bot.board)
        #             continue
        #         elif user_input == "moves":
        #             legal_moves = list(bot.board.legal_moves)
        #             print(f"Legal moves ({len(legal_moves)}): {', '.join(str(m) for m in legal_moves)}")
        #             continue
        #         else:
        #             try:
        #                 if bot.make_move(user_input):
        #                     print(f"White plays: {user_input}")
        #                     break
        #             except:
        #                 print("Invalid move. Try again.")
        # Bot's turn (White)
        if bot.turn == "white":
            if bot.board.is_game_over():
                continue
            
            print("Bot is thinking...")
            bot_move = bot.make_bot_move(max_depth=3, time_limit_seconds=5)
            
            if bot_move:
                print(f"White plays: {bot_move}")
            else:
                print("Bot couldn't find a move.")
                game_over = True

        # Bot's turn (Black)
        else:
            if bot.board.is_game_over():
                continue
            
            print("Bot is thinking...")
            bot_move = bot.make_bot_move(max_depth=3, time_limit_seconds=5)
            
            if bot_move:
                print(f"Black plays: {bot_move}")
            else:
                print("Bot couldn't find a move.")
                game_over = True
        
        print()
    
    print("\nGame Over!")
    print("Final FEN:", bot.get_board_fen())