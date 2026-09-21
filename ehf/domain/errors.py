class DataReadError(Exception):
    pass


class MatchNotFound(Exception):
    def __init__(self, match_id: int) -> None:
        super().__init__(f"Match {match_id} was not found")
        self.match_id = match_id


class PlayerNotFound(Exception):
    def __init__(self, player_id: int) -> None:
        super().__init__(f"Player {player_id} was not found")
        self.player_id = player_id
