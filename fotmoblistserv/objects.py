import glob
import json
import math
import os
import re
from dataclasses import dataclass, fields
from datetime import datetime
from functools import reduce
from operator import itemgetter
from urllib.parse import urlparse, parse_qs

import pycountry

from .api import handle_response, FotmobEntity
from .shared import convert_euro_price_string


class League(FotmobEntity):
    def get_name(self):
        return self.get_item("details", "name")
    
    def get_country_code(self):
        return self.get_item("details", "country")
    
    def get_country(self):
        try:
            return pycountry.countries.get(alpha_3=self.get_country_code()).name
        except AttributeError:
            return None

    def get_totw_for_week(self, week=0):
        week = int(week)
        glob_pattern = f"league_{self._id}_totw_*.json" if week == 0 else f"league_{self._id}_totw_*_{week}.json"
        paths = glob.glob(glob_pattern)
        if paths:
            try:
                path = max(paths, key=os.path.getmtime)
                if path and week == 0:
                    with open(path, "r") as f:
                        return json.load(f)
                    
                pattern = re.compile(f"league_{self._id}_totw_(\d+)_{week}.json")
                if re.match(pattern, path):
                    with open(path, "r") as f:
                        return json.load(f)       
            except Exception:
                pass

        rounds_url = self.get_item("stats", "seasonStatLinks")
        if not rounds_url:
            raise ValueError(f"Cannot find TOTW range link for league {self._id}")

        rounds_url = rounds_url[0]["TotwRoundsLink"]
        totw_data = handle_response(rounds_url)
        if not totw_data:
            raise ValueError(f"No TOTW data returned for league {self._id}")
        
        round_completed = False
        if week == 0:
            round_completed = totw_data["last"]["isCompleted"]
            totw_link = totw_data["last"]["link"]
        else:
            totw_rounds = totw_data["rounds"]
            totw_round = list(filter(lambda r: int(r["roundId"]) == int(week), totw_rounds))
            if not totw_round:
                msg = f"No TOTW link found for round {week}. Try an int from 1 to {len(totw_rounds)}"
                raise ValueError(msg)
        
            totw_round = totw_round[0]
            round_completed = totw_data["last"]["isCompleted"]
            totw_link = totw_round["link"]

        totw = handle_response(totw_link)
        if not totw:
            raise ValueError(f"No TOTW data returned from call to {totw_link}.")
        
        if round_completed:
            params = parse_qs(urlparse(totw_link).query)
            path_string = f"league_{self._id}_totw_{params['stages'][0]}_{params['roundid'][0]}.json"
            paths = glob.glob(path_string)
            if not paths:
                with open(path_string, "w") as f:
                    json.dump(totw, f)

        return totw


class Player(FotmobEntity):
    def __str__(self):
        return str(self.get_player_tuple())

    def get_player_tuple(self):
        return tuple([self.get_name(), self.get_club_string(), self.get_position_string(), self.get_age(), self.get_total_senior_appearances()])

    def get_age(self):
        birth_date = self.get_item("meta", "personJSONLD", "birthDate")
        age_days = datetime.now().date() - datetime.fromisoformat(birth_date).date()
        return math.floor(age_days.days / 365)

    def get_name(self):
        return self.get_item("name")
    
    def get_first_name(self):
        return self.get_name().split(" ")[0]
    
    def get_club_name(self):
        return self.get_item("origin", "teamName")
    
    def get_club_string(self):
        return self.get_item("meta", "personJSONLD", "affiliation", "name")
    
    def is_on_loan(self):
        return self.get_item("origin", "onLoan")
    
    def get_total_senior_appearances(self):
        clubs = self.get_item("careerHistory", "careerData", "careerItems", "senior")
        total = 0
        for club in clubs:
            apps = club["appearances"]
            if not apps:
                continue

            match = re.match(r"(\d+)", club["appearances"])
            if match:
                total += int(match.group())
        
        return total
    
    def get_positions(self):
        return tuple([(p["strPosShort"]["label"], p["isMainPosition"]) for p in self.get_item(*[
            "origin", 
            "positionDesc", 
            "positions"
        ])])
    
    def get_main_positions(self):
        return [label for (label, is_main) in self.get_positions() if is_main]
    
    def get_other_positions(self):
        return [label for (label, is_main) in self.get_positions() if not is_main]

    def get_position_string(self):
        main_positions = self.get_main_positions()
        positions = main_positions
        other_positions = self.get_other_positions()
        if other_positions:
            positions += other_positions
        return "/".join(positions)


class Team(FotmobEntity):
    def get_name(self):
        return self.get_item("details", "name")
    
    def get_transfers(self):
        transfers = reduce(lambda x, y: x + y, self.get_item("transfers", "data").values())
        transfers = sorted(transfers, key=lambda t: -int(datetime.fromisoformat(t["transferDate"]).timestamp()))
        return transfers


@dataclass(frozen=True)
class Transfer:
    player: str
    player_id: int
    date: str
    from_club: str
    from_club_id: int
    to_club: str
    to_club_id: int
    transfer_fee_string: str
    market_value_string: str
    on_loan: bool
    contract_extension: bool
    free_agent: bool

    def __str__(self):
        return str(tuple([
            self.player, 
            self.get_date_string(), 
            f"{self.from_club} => {self.to_club}", 
            self.transfer_fee_string,
            self.market_value_string,
            self.get_tf_mv_ratio_string()
        ]))
    
    def get_date_string(self):
        return str(datetime.fromisoformat(self.date).date())

    def get_tf_mv_ratio_string(self):
        ratio = self.get_fee_to_value_ratio()
        if not isinstance(ratio, (float, int)) or ratio == 0:
            return 0
        return ratio

    def get_transfer_value(self):
        try:
            return convert_euro_price_string(self.transfer_fee_string)
        except IndexError:
            return 0
    
    def get_market_value(self):
        try:
            return convert_euro_price_string(self.market_value_string)
        except IndexError:
            return 0
    
    def get_fee_to_value_ratio(self):
        try:
            return float(str(round(self.get_transfer_value() / self.get_market_value(), 2))[0:4])
        except ZeroDivisionError:
            return 0
    
    def is_discount(self):
        return self.get_fee_to_value_ratio() < 1
    
    def is_premium(self):
        return self.get_fee_to_value_ratio() > 1
    
    @staticmethod
    def convert_transfer_data(transfer):
        fee = transfer["fee"]
        if fee and fee.get("value"):
            fee = fee.get("value") 
        else:
            fee = ""

        return {
            "player": transfer["name"],
            "player_id": transfer["playerId"],
            "date": transfer["transferDate"],
            "from_club": transfer["fromClub"],
            "from_club_id": int(transfer["fromClubId"]),
            "to_club": transfer["toClub"],
            "to_club_id": int(transfer["toClubId"]),
            "transfer_fee_string": fee,
            "market_value_string": transfer.get("marketValue", ""),
            "on_loan": transfer["onLoan"],
            "contract_extension": transfer["contractExtension"],
            "free_agent": "Free agent" in [transfer["fromClub"], transfer["toClub"]]
        }

    @classmethod
    def get_transfers_from_team(cls, team):
        transfers = team.get_transfers()
        for transfer in transfers:
            yield cls(**cls.convert_transfer_data(transfer))
