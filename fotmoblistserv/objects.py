from .api import API, APIResponse

api = API()


class Player(APIResponse):
    @classmethod
    def from_id(cls, fm_id):
        return cls(api.get_player(fm_id))
    

class League(APIResponse):
    @classmethod
    def from_id(cls, fm_id):
        return cls(api.get_league(fm_id))
    

class Team(APIResponse):
    @classmethod
    def from_id(cls, fm_id):
        return cls(api.get_team(fm_id))
    

class MatchDetails(APIResponse):
    @classmethod
    def from_id(cls, fm_id):
        return cls(api.get_match_details(fm_id))
