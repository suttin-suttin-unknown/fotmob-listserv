__all__ = ("FotmobAPI",)

import requests
import re

from cachetools import cached, TTLCache
from dataclasses import dataclass

from shared import *


NO_CACHE_HEADER = {"Cache-Control": "no-cache"}

BASE_URL = "https://www.fotmob.com/api"

LEAGUES_URL = BASE_URL + "/leagues?"
MATCHES_URL = BASE_URL + "/matches?"
TEAMS_URL = BASE_URL + "/teams?"
PLAYERS_URL = BASE_URL + "/players?"
MATCH_DETAILS_URL = BASE_URL + "/matchDetails?"

SEARCH_URL = "https://apigw.fotmob.com/searchapi/"

DATE_REGEX = r"(20\d{2})(\d{2})(\d{2})"


class NoJSONResponse(Exception):
    pass


def check_date(date):
    return re.search(DATE_REGEX, date)


def _wrap_cache(maxsize, ttl):
    return cached(cache=TTLCache(maxsize=maxsize, ttl=ttl))

# TODO: config with ini
DAY_SECONDS = 60 * 60 * 24

LEAGUES_ROUTE_CACHE_MAXSIZE = 50
LEAGUES_ROUTE_CACHE_TTL = DAY_SECONDS

MATCHES_ROUTE_CACHE_MAXSIZE = 100
MATCHES_ROUTE_CACHE_TTL = 60 * 60 * 24

TEAMS_ROUTE_CACHE_MAXSIZE = 200
TEAMS_ROUTE_CACHE_TTL = 60 * 60 * 24

# TODO: factory - too ugly rn
league_route_cache = _wrap_cache(LEAGUES_ROUTE_CACHE_MAXSIZE, LEAGUES_ROUTE_CACHE_TTL)
matches_route_cache = _wrap_cache(MATCHES_ROUTE_CACHE_MAXSIZE, MATCHES_ROUTE_CACHE_TTL)
teams_route_cache = _wrap_cache(TEAMS_ROUTE_CACHE_MAXSIZE, TEAMS_ROUTE_CACHE_TTL)


def _handle_api_call(url, headers=NO_CACHE_HEADER):
    logger.info(f"Url: {url}")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        response = response.json()
        if response is None:
            raise NoJSONResponse
        else:
            return response
    except requests.HTTPError as error:
        logger.error(f"Error: {error.response.json()}")
        raise
    except Exception as error:
        logger.error(f"Error: {error}")
        raise

@cached(cache=TTLCache(maxsize=1024, ttl=3600))
def get_matches_by_date(date):
    if check_date(date) is not None:
        return _handle_api_call(f"{MATCHES_URL}date={date}")


@league_route_cache
def get_league(league_id, tab="overview", type="league", time_zone="America/Los_Angeles"):
    return _handle_api_call(f"{LEAGUES_URL}id={league_id}&tab={tab}&type={type}&timeZone={time_zone}")


@teams_route_cache
def get_team(team_id, tab="overview", type="team", time_zone="America/New_York"):
    return _handle_api_call(f"{TEAMS_URL}id={team_id}&tab={tab}&type={type}&timeZone={time_zone}")


@cached(cache=TTLCache(maxsize=1024, ttl=3600))
def get_player(player_id):
    return _handle_api_call(f"{PLAYERS_URL}id={player_id}")


@cached(cache=TTLCache(maxsize=1024, ttl=3600))
def get_match_details(match_id):
    return _handle_api_call(f"{MATCH_DETAILS_URL}matchId={match_id}")


@cached(cache=TTLCache(maxsize=1024, ttl=3600))
def search(search_term):
    return _handle_api_call(f"{SEARCH_URL}suggest?term={search_term}")


def get_league_transfers(league_id):
    return get_league(league_id)["transfers"]["data"]


def convert_euro_price(euro_price):
    if match := re.match(r"€(\d+\.?\d*)([MK])", euro_price):
        value_str, multiplier = match.groups()
        value = float(value_str)
        if multiplier == 'M':
            value *= 1000000
        elif multiplier == 'K':
            value *= 1000
        return int(value)


@dataclass(frozen=True)
class Transfer:
    player_id: int
    player_name: str
    transfer_date: str
    from_id: int
    from_name: str
    to_id: int
    to_name: str
    transfer_fee_str: str
    on_loan: bool
    from_date: str
    to_date: str
    market_value_str: str
        
    def __str__(self):
        return f"{self.player_name}: {self.from_name} -> {self.to_name} ({self.transfer_fee_str})"
    
    @property
    def transfer_fee(self):
        fee = convert_euro_price(self.transfer_fee_str)
        if fee is None:
            return 0
        
        return fee
    
    @property
    def market_value(self):
        value = convert_euro_price(self.transfer_fee_str)
        if value is None:
            return 0
        
        return value
    
    @property
    def tf_mv_ratio(self):
        return round(float(self.transfer_fee / self.market_value), 2)


if __name__ == "__main__":
    configure_logger(logger)
