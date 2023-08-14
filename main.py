import logging
import re
import math
import json
import time

import requests

from cachetools import cached, TTLCache

from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from operator import itemgetter

NO_CACHE_HEADER = {"Cache-Control": "no-cache"}
DATE_REGEX = r"(20\d{2})(\d{2})(\d{2})"
TZ_LA = "America/Los_Angeles"

logger = logging.getLogger(__name__)


class App:
    def something(self):
        self.cache = {}


class _RouteHandler:
    def __init__(self):
        pass

    def route_request(self, function_name, *args, **kwargs):
        if hasattr(self, function_name):
            function = getattr(self, function_name)
            if callable(function):
                return function(*args, **kwargs)
            else:
                raise ValueError(f"{function_name} is not callable")
        else:
            raise ValueError(f"Function {function_name} not found")
            
class _ResponseHandler:
    def __call__(self, url, params={}, headers=NO_CACHE_HEADER):
        try:
            # use session?
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            if hasattr(response, "json"):
                return response.json()
            else:
                raise ValueError(f"No JSON returned from API. See: {response.text}")
        except requests.HTTPError as error:
            logger.error(f"Error: {error}")
        except requests.exceptions.JSONDecodeError as error:
            logger.error(f"Error: {error}")
        except Exception as error:
            logger.error(f"Error: {error}")
        
        return {}


class API:
    """
    Singleton class for interacting with fotmob api. Routes mapped to object methods.

    Restful routes covered:

    GET matches - https://www.fotmob.com/api/matches?date={}
    GET leagues - https://www.fotmob.com/api/leagues?id={}&tab={}&type={}&timeZone={}
    GET teams - https://www.fotmob.com/api/teams?id={}&tab={}&type={}&timeZone={}
    GET players - https://www.fotmob.com/api/playerData?id={}
    GET matchDetails - https://www.fotmob.com/api/matchDetails?matchId={}

    Search route:

    GET search - https://apigw.fotmob.com/searchapi/suggest?term={}&lang={}
    """
    _instance = None
    
    _BASE_URL = "https://www.fotmob.com/api"
    _SEARCH_URL = "https://apigw.fotmob.com/searchapi/"

    response_handler = _ResponseHandler()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
            
    def get_matches(self, date):
        return self.response_handler(self._BASE_URL + f"/matches?date={date}")
    
    def get_match_details(self, match_id):
        return self.response_handler(self._BASE_URL + f"/matchDetails?matchId={match_id}")
    
    def get_player(self, player_id):
        return self.response_handler(self._BASE_URL + f"/playerData?id={player_id}")
    
    def get_league(self, league_id, time_zone=TZ_LA):
        return self.response_handler(self._BASE_URL + "/leagues", params={
            "id": league_id,
            "tab": "overview",
            "type": "league",
            "timeZone": time_zone
        })
            
    def get_team(self, team_id, time_zone=TZ_LA):
        return self.response_handler(self._BASE_URL + "/teams", params={
            "id": team_id,
            "tab": "overview",
            "type": "league",
            "timeZone": time_zone
        })
    
    # TODO: Schedule searches - for players not added yet
    def search(self, term):
        return self.response_handler(f"{self._SEARCH_URL}suggest?term={term}")


class _Response:
    """
    Private super class for converting expected json responses from API to attributed objects.

    General pattern:

    raw_json (stored in self._response_json) => treated_json (to instantiate subclasses) => properties for readability.
    """
    _response_json = {}

    def __init__(self, response_json):
        self._response_json = response_json
        self._creation_time = datetime.now()
        self._fotmob_id = None

    @classmethod
    def _dump(cls):
        raise NotImplementedError("'_dump' not implemented.")

    @classmethod
    def from_fotmob_id(cls, fotmob_id):
        raise NotImplementedError("'from_fotmob_id' not implemented.")
    



default_metrics_list = [
    "Top scorer", 
    "Assists", 
    "Goals + Assists", 
    "FotMob rating", 
    "Goals per 90",
    "Expected goals (xG)", 
    "Expected goals (xG) per 90", 
    "Expected goals on target (xGOT)",
    "Shots on target per 90", 
    "Shots per 90", 
    "Accurate passes per 90", 
    "Big chances created",
    "Chances created", 
    "Accurate long balls per 90", 
    "Expected assist (xA)",
    "Expected assist (xA) per 90", 
    "xG + xA per 90", 
    "Successful dribbles per 90",
    "Big chances missed", 
    "Penalties won", 
    "Successful tackles per 90", 
    "Interceptions per 90",
    "Clearances per 90", 
    "Blocks per 90", 
    "Penalties conceded", 
    "Possession won final 3rd per 90",
    "Clean sheets", 
    "Save percentage", 
    "Saves per 90", 
    "Goals prevented", 
    "Goals conceded per 90",
    "Fouls committed per 90", 
    "Yellow cards", 
    "Red cards"
]


class StatFactory:
    def __call__(self, metric, player, team, value):
        if metric not in default_metrics_list:
            raise ValueError(f"Metric {metric} not recognized as part of fotmob schema.")
        
        return PlayerStat(metric=metric, player=player, team=team, value=value)


@dataclass(frozen=True)
class PlayerStat:
    metric: str 
    player: str
    team: str
    value: str

    def as_array(self):
        return [self.metric, self.player, self.team, self.value]

    def as_dict(self):
        return asdict(self)
        

class League(_Response):
    __slots__ = ["_name", "_country", "_transfers_json", "_matches_json", "_player_stats_json"]

    def __init__(self, response_json):

        # perhaps validate instead
        self._fotmob_id = response_json["details"]["id"]
        self._name = response_json["details"]["name"]
        self._country = response_json["details"]["country"]
        self._transfers_json = response_json.get("transfers", {}).get("data")
        self._matches_json = response_json.get("matches", {}).get("allMatches")
        self._stats_json = response_json.get("stats", {})
        self._player_stats_json = self._stats_json.get("players")
        super().__init__(response_json)

    @classmethod
    def from_fotmob_id(cls, fotmob_id):
        api = API()
        league = api.get_league(fotmob_id)
        return cls(league)

    def get_league_id(self):
        return self._fotmob_id

    def get_name(self):
        return self._name
    
    def get_country(self):
        return self._country
    
    def _get_player_stats_json(self):
        stats = {}
        for stat_json in self._player_stats_json:
            metric = stat_json["header"]
            stats[metric] = []
            for entry in stat_json["topThree"]:
                main_keys = ["name", "teamName", "value"]
                stats[metric].append(dict(zip(main_keys, itemgetter(*main_keys)(entry))))
        return stats
    
    def _get_player_stats(self):
        for (metric, entries) in self._get_player_stats_json().items():
            for entry in entries:
                yield PlayerStat(**{
                    "metric": metric,
                    "player": entry["name"],
                    "team": entry["teamName"],
                    "value": entry["value"]
                })
                
    def get_player_stats(self):
        return self._get_player_stats()
    
    def get_player_stats_table(self, snake_case=True):
        table = {}
        for stat in self.player_stats:
            if table.get(stat.metric):
                table[stat.metric].append(stat.as_dict())
            else:
                table[stat.metric] = [stat.as_dict()]
        
        if snake_case:
            snake_case_table = {}
            for k, v in table.items():
                sc_k = "_".join(w.lower() for w in re.findall(r"\w+", k))
                snake_case_table[sc_k] = v
            return {"player_stats": snake_case_table}
        
        return {"Player stats": table}
    
    def _get_latest_totw_round_url(self):
        return self._stats_json["seasonStatLinks"][0]["TotwRoundsLink"]
    
    league_id = property(get_league_id)
    name = property(get_name)
    country = property(get_country)
    player_stats = property(get_player_stats)
    latest_totw_round_url = property(_get_latest_totw_round_url)


def get_stat_list_string(metric, entries):
    entry_string = "\n".join([f"{entry['player']} ({entry['team']}) - {entry['value']}" for entry in entries])
    banner = "================================================"
    stat_list_string = f"{banner}\n{metric}\n\n{entry_string}\n{banner}"
    return stat_list_string


def print_player_stats(league):
    player_stats = league.get_player_stats_table()["player_stats"]
    for (metric, entries) in player_stats.items():
        print(f"{get_stat_list_string(metric, entries)}\n")


# Calls in here probably good to cache
@cached(cache=TTLCache(maxsize=100, ttl=3600))
def get_league_last_totw(league):
    totw_dict = {}

    logger.info(f"Getting latest {league.name} TOTW link...")
    latest_totw_url = requests.get(league.latest_totw_round_url).json()["last"]["link"]
    latest_round_number = int(latest_totw_url[-1])
    totw_dict["round"] = latest_round_number

    logger.info(f"Getting latest {league.name} TOTW...")
    totw = requests.get(latest_totw_url).json()["players"]
    main_keys = ["assists", "goals", "matchId", "motm", "name", "participantId", "rating", "roundNumber"]
    totw_dict["players"] = [dict(zip(main_keys, itemgetter(*main_keys)(player))) for player in totw]

    return totw_dict

def get_totw_all_ids(league):
    round_info = requests.get(league.latest_totw_round_url).json()["rounds"]
    totw_ids = []
    for info in round_info:
        link = info["link"]
        totw = requests.get(link, headers=NO_CACHE_HEADER).json()
        for player in totw["players"]:
            player_id = player["participantId"]
            totw_ids.append(player_id)

    return set(totw_ids)



def get_totw_player_ids(league):
    totw = get_league_last_totw(league)
    return [p["participantId"] for p in totw["players"]]


class Foot(Enum):
    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True)
class Country:
    full_name: str
    ccode: str


class _Birthdate:
    def __init__(self, year, month, day):
        self.year = year
        self.month = month
        self.day = day


class Player(_Response):
    @dataclass(frozen=True)
    class _BodyMeasurement:
        unit: str
        value: int

        def __str__(self):
            return f"{self.value} {self.unit}"

    @dataclass(frozen=True)
    class _Height(_BodyMeasurement):
        pass

    @dataclass(frozen=True)
    class _Weight(_BodyMeasurement):
        pass
        
    def __init__(self, response_json):
        super().__init__(response_json)

        self._player_props_json = self._response_json["playerProps"]
        self._last_league_json = self._response_json["lastLeague"]
        self._recent_matches_json = self._response_json["recentMatches"]
        self._career_statistics_json = self._response_json["careerStatistics"]
        self._career_history_json = self._response_json["careerHistory"]
        self._related_news_json = self._response_json["relatedNews"]
        self._meta_json = self._response_json["meta"]

        self._person_json = self._meta_json["personJSONLD"]
        self._nationality_json = self._person_json["nationality"]
        self._affiliation_json = self._person_json["affiliation"]
        self._height_json = self._person_json["height"]
        self._weight_json = self._person_json["weight"]

        # name
        self._name = self._person_json["name"]
        self._team_name = self._affiliation_json["name"]

        self._birthdate = datetime.fromisoformat(self._person_json["birthDate"]).date()

        self._nationality_ccode = [p for p in self._player_props_json if p.get("countryCode")][0]["countryCode"]
        self._nationality = Country(full_name=self._nationality_json["name"], ccode=self._nationality_ccode)
        
        # height data
        self._height_units = self._height_json["unitText"]
        self._height_value = self._height_json["value"]
        self._height = Player._Height(unit=self._height_units, value=int(self._height_value))
        # weight data
        self._weight_units = self._weight_json["unitText"]
        self._weight_value = self._weight_json["value"]
        self._weight = Player._Weight(unit=self._weight_units, value=int(self._weight_value))

    @classmethod
    def from_fotmob_id(cls, fotmob_id):
        api = API()
        player = api.get_player(fotmob_id)
        return cls(player)
    
    def get_player_id(self):
        return self._response_json["id"]
    
    def get_name(self):
        return self._name
    
    def get_birthdate(self):
        return self._birthdate
    
    def get_year_of_birth(self):
        return self.get_birthdate().year
    
    def get_month_of_birth(self):
        return self.get_birthdate().month
    
    def get_day_of_birth(self):
        return self.get_birthdate().day
    
    def get_country(self):
        return self._nationality.full_name
    
    def get_country_code(self):
        return self._nationality.ccode

    def get_height_string(self):
        return str(self._height)

    def get_weight_string(self):
        return str(self._weight)
    
    def get_height(self):
        return self._height.value

    def get_weight(self):
        return self._weight.value
    
    def get_age(self):
        birth_delta = datetime.now().date() - self.get_birthdate()
        return math.floor(birth_delta.days / 365)
    
    def get_total_senior_matches(self):
        return sum([int(_["totalMatches"]) for _ in self._career_statistics_json])
    
    def is_raw(self, match_threshold=100):
        return self.get_total_senior_matches() < match_threshold
    

def dump_player(player):
    player_id = player.get_player_id()
    player_timestamp = round(player._creation_time.timestamp())
    path = f"{player_id}_{player_timestamp}"
    with open(path, "w") as f:
        json.dump(player._response_json, f)


class Match(_Response):
    def __init__(self, response_json):
        super().__init__(response_json)


class Team(_Response):
    def __init__(self, response_json):
        super().__init__(response_json)


class MatchDetails(_Response):
    def __init__(self, response_json):
        super().__init__(response_json)


class Query:
    pass


class View:
    pass


if __name__ == "__main__":
    from pprint import pprint
    print("Main: ")
    api = API()
