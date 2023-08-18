from dataclasses import dataclass

import requests
import logging

logger = logging.getLogger(__name__)

from types import MappingProxyType

def handle_response(url, params={}, headers={"Cache-Control": "no-cache"}):
    try:
        # use session?
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        if hasattr(response, "json"):
            response_json = response.json()
            return (lambda c: c(response_json))(ImmutableDictConverter())
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

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
            
    def get_matches(self, date):
        return handle_response(self._BASE_URL + f"/matches?date={date}")
    
    def get_match_details(self, match_id):
        return handle_response(self._BASE_URL + f"/matchDetails?matchId={match_id}")
    
    def get_player(self, player_id):
        return handle_response(self._BASE_URL + f"/playerData?id={player_id}")
    
    def get_league(self, league_id, time_zone="America/Los_Angeles"):
        return handle_response(self._BASE_URL + "/leagues", params={
            "id": league_id,
            "tab": "overview",
            "type": "league",
            "timeZone": time_zone
        })
            
    def get_team(self, team_id, time_zone="America/Los_Angeles"):
        return handle_response(self._BASE_URL + "/teams", params={
            "id": team_id,
            "tab": "overview",
            "type": "league",
            "timeZone": time_zone
        })
    
    # TODO: Schedule searches - for players not added yet
    def search(self, term):
        return handle_response(f"{self._SEARCH_URL}suggest?term={term}")
    

# def recursive_mapping_proxy(data):
#     if isinstance(data, dict):
#         return MappingProxyType({key: recursive_mapping_proxy(value) for key, value in data.items()})
#     elif isinstance(data, list):
#         return tuple(recursive_mapping_proxy(item) for item in data)
#     return data

class ImmutableDictConverter:
    def __call__(self, data):
        return self._convert(data)
    
    def _convert(self, data):
        if isinstance(data, dict):
            return MappingProxyType({key: self._convert(value) for key, value in data.items()})
        elif isinstance(data, list):
            return tuple(self._convert(item) for item in data)
        return data
    

@dataclass(frozen=True)
class APIResponse:
    response: MappingProxyType

    




    
    
