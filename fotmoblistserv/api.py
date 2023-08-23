import glob
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from functools import reduce
from types import MappingProxyType

import requests
from cachetools import cached, TTLCache

from .shared import (convert_camel_to_snake, ImmutableDictConverter as converter)

logger = logging.getLogger(__name__)


def handle_response(url, params={}, headers={"Cache-Control": "no-cache"}):
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        if not hasattr(response, "json"):
            raise ValueError(f"No JSON returned from API. See: {response.text}")
        return response.json()
    except requests.HTTPError as error:
        logger.error(f"Error: {error}")
    except requests.exceptions.JSONDecodeError as error:
        logger.error(f"Error: {error}")
    except Exception as error:
        logger.error(f"Error: {error}")
    
    return {}

class ResponseHandler:
    def __call__(self, url, params, headers):
        return self._handle_response(url, params, headers)

    def _handle_response(self, url, params, headers):
        return handle_response(url, params=params, headers=headers)


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
    
    @cached(TTLCache(maxsize=10, ttl=60 * 60))
    def get_player(self, player_id):
        return handle_response(self._BASE_URL + f"/playerData?id={player_id}")
    
    @cached(TTLCache(maxsize=10, ttl=60 * 60))
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
    
    def search(self, term):
        return handle_response(f"{self._SEARCH_URL}suggest?term={term}")


@dataclass(frozen=True)
class FotmobEntity:
    _id: int
    
    def __post_init__(self):
        self.save()

    @classmethod
    def get_api_method_name(cls):
        return f"get_{convert_camel_to_snake(cls.__name__)}"

    def get_local_file(self):
        subclass = convert_camel_to_snake(self.__class__.__name__)
        paths = glob.glob(f"{subclass}_{self._id}_*")
        
        if len(paths) == 0:
            return ""
        
        pattern = re.compile(f"{subclass}_{self._id}_(\d+).json")
        paths = [path for path in paths if re.match(pattern, path)]
        return max(paths, key=os.path.getmtime)
    
    def get_local_data(self):
        path = self.get_local_file()
        if path:
            with open(path, "r") as f:
                return converter.to_immutable(json.load(f))
        return MappingProxyType({})
            
    def get_api_data(self):
        method = getattr(API(), self.get_api_method_name())
        if not method:
            raise ValueError(f"Cannot find api method for object {self.__class__.__name__}")
        return converter.to_immutable(method(self._id))
    
    def get_item(self, *args):
        return reduce(lambda d, k: d.get(k, {}), args, self.local_data)
    
    def should_update_local(self, force=False, expiry=None):
        if not expiry:
            expiry = 24 * 7

        expiry = round(float(expiry), 1)
        
        if force:
            return True
        else:
            local_file = self.get_local_file()
            if not local_file:
                return True
            else:
                hours = (time.time() - os.stat(local_file).st_ctime) / 3600
                return hours > expiry

    def save(self, force=False):
        if self.should_update_local(force=force):
            ts = round(time.time())
            subclass = convert_camel_to_snake(self.__class__.__name__)
            path = f"{subclass}_{self._id}_{ts}.json"
            with open(path, "w") as f:
                json.dump(converter.to_mutable(self.get_api_data()), f)
                return path

    local_data = property(get_local_data)
