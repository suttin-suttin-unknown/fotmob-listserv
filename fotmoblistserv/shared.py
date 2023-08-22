import json
import logging
import os
import pickle
import re
import time

from types import MappingProxyType

EURO_SYMBOL = "€"


class FileCache:
    def __init__(self, filename):
        self.filename = filename
        if not os.path.exists(filename):
            with open(filename, "wb") as f:
                pickle.dump({}, f)

    def get(self, key):
        with open(self.filename, "rb") as f:
            return pickle.load(f).get(key, None)
        
    def set(self, key, value):
        with open(self.filename, "rb+") as f:
            data = pickle.load(f)
            data[key] = value
            f.seek(0)
            pickle.dump(data, f)
            f.truncate()

    def clear(self):
        with open(self.filename, "wb") as f:
            pickle.dump({}, f)


class ImmutableDictConverter:
    def __call__(self, data, make_immutable=True):
        return self.convert(data, make_immutable)
    
    def convert(self, data, make_immutable=True):
        if make_immutable:
            if isinstance(data, dict):
                return MappingProxyType({key: self.convert(value, True) for key, value in data.items()})
            elif isinstance(data, list):
                return tuple(self.convert(item, True) for item in data)
        else:
            if isinstance(data, MappingProxyType):
                return {key: self.convert(value, False) for key, value in data.items()}
            elif isinstance(data, tuple):
                return [self.convert(item, False) for item in data]
        
        return data
    
    @classmethod
    def to_mutable(cls, data):
        return cls().convert(data, make_immutable=False)
    
    @classmethod
    def to_immutable(cls, data):
        return cls().convert(data)


def write_json(path=""):
    if len(path) == 0:
        path = int(time.time())
    with open(path, "w") as f:
        json.dump()


def convert_camel_to_snake(cc_str):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", cc_str).lower()


def convert_euro_price_string(eu_str):
    eu_str = eu_str.replace(EURO_SYMBOL, "")
    multiplier = 1

    if eu_str[-1] == "M":
        multiplier = 1000000
        eu_str = eu_str[:-1]
    elif eu_str[-1] == "K":
        multiplier = 1000
        eu_str = eu_str[:-1]
    
    value = float(eu_str)
    value = int(value * multiplier)

    return value


# should be in fotmoblistserv/__init__.py
def configure_logger(logger):
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


logger = logging.getLogger(__name__)
