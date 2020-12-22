from enum import Enum
import vk_api

import threading
import json
import requests
from forex_python.converter import CurrencyRates


class ListingType(Enum):
    STOCK = 1,
    CURRENCY = 2,


class Listing:
    def __init__(self, type_: ListingType, **kwargs):
        self.type_ = type_
        if type_ == ListingType.STOCK:
            self.symbol = kwargs["symbol"]
            self.name = kwargs["name"]
        elif type_ == ListingType.CURRENCY:
            self.from_cur = kwargs["from_cur"]
            self.to_cur = kwargs["to_cur"]
            self.pair = f"{self.from_cur}\\{self.to_cur}"


class SubscribeInfo:
    def __init__(self, user_id, type_: ListingType, **kwargs):
        self.user_id = user_id
        self.type_ = type_

        if type_ == ListingType.STOCK:
            self.symbol = kwargs["symbol"]
        elif type_ == ListingType.CURRENCY:
            self.from_cur = kwargs["from_cur"]
            self.to_cur = kwargs["to_cur"]


class Monitor:
    __instance = None

    @classmethod
    def get_instance(cls, *args, **kwargs):
        if not cls.__instance:
            cls.__instance = Monitor(*args, *kwargs)
        return cls.__instance

    def __init__(self):
        if Monitor.__instance:
            return

        self.c = CurrencyRates()

        with open("currencies.json") as read_file:
            data = json.load(read_file)
            currencies = {
                e["cc"]: e["name"] for e in data
            }

        data = json.loads(requests.get("https://api.iextrading.com/1.0/ref-data/symbols").text)
        stock = {
            e["symbol"]: Listing(ListingType.STOCK, symbol=e["symbol"], name=e["name"]) for e in data
        }

        self.listings = {
            "stock": stock,
            "currencies": currencies,
        }

        self.subscribers = {}
        vk_session = vk_api.VkApi(token="99455e87cabba8273be935f69d9a9ab92f2fa9724bd7dd8ea6611d4af8afd2b99247369cf49e1da1ca7fa")
        self.vk = vk_session.get_api()
        self.get_updates()

    def parse(self, user_id, raw_input):
        raw_input = raw_input.split("/")

        if len(raw_input) == 2:
            from_cur = raw_input[0]
            to_cur = raw_input[1]
            if from_cur in self.listings["currencies"] and to_cur in self.listings["currencies"]:
                return SubscribeInfo(user_id, ListingType.CURRENCY, from_cur=from_cur, to_cur=to_cur)
        elif len(raw_input) == 1:
            ticker = raw_input[0]
            if ticker in self.listings["stock"]:
                return SubscribeInfo(user_id, ListingType.STOCK, symbol=ticker)
        return None

    def add_subscriber(self, info: SubscribeInfo):
        type_ = info.type_

        if type_ == ListingType.CURRENCY:
            listing = Listing(ListingType.CURRENCY, from_cur=info.from_cur, to_cur=info.to_cur)
            if listing not in self.subscribers:
                self.subscribers[listing] = []
            self.subscribers[listing].append(info.user_id)

        elif type_ == ListingType.STOCK:
            listing = self.listings["stock"][info.symbol]
            if listing not in self.subscribers:
                self.subscribers[listing] = []
            self.subscribers[listing].append(info.user_id)

    def get_updates(self):
        for listing, subscribers in self.subscribers.items():
            if listing.type_ == ListingType.STOCK:
                new_price = requests.get(f"https://api.iextrading.com/1.0/tops/last?symbols={listing.symbol}").json()[0]["price"]
                for subscriber in subscribers:
                    self.vk.messages.send(peer_id=subscriber, message=f"Ticker {listing.symbol} стоит {new_price} USD",
                                          random_id=0)
            elif listing.type_ == ListingType.CURRENCY:
                rate = self.c.get_rate(listing.from_cur, listing.to_cur)
                for subscriber in subscribers:
                    self.vk.messages.send(peer_id=subscriber, message=f"1 {listing.from_cur} стоит {rate} {listing.to_cur}",
                                          random_id=0)
        threading.Timer(1.0, self.get_updates).start()
