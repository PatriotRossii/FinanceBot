from enum import Enum
import vk_api

import threading
import json
import requests
from forex_python.converter import CurrencyRates

import sqlite3

class EntityType(Enum):
    Currency = 1,
    Stock = 2,

class MonitoringType(Enum):
    CurrencyPair = 1,
    Stock = 2,
    Invalid = 3,

class Monitor:
    __instance = None

    @classmethod
    def get_instance(cls, *args, **kwargs):
        if not cls.__instance:
            cls.__instance = Monitor(*args, *kwargs)
        return cls.__instance

    def __init__(self, update=False):
        if Monitor.__instance:
            return

        self.conn = sqlite3.connect("resources/database.db")
        self.cursor = self.conn.cursor()

        self.c = CurrencyRates()

        if update:
            self.drop_table("currencies", "symbols")

            self.load_symbols()
            self.load_currencies()
        self.load_prices()

        self.listings = {
            "stock": stock,
            "currencies": currencies,
        }

        self.subscribers = {}
        vk_session = vk_api.VkApi(token="99455e87cabba8273be935f69d9a9ab92f2fa9724bd7dd8ea6611d4af8afd2b99247369cf49e1da1ca7fa")
        self.vk = vk_session.get_api()
        self.get_updates()

    def drop_table(self, *args):
        if not args:
            raise RuntimeError("Do you wanna drop any table?")
        for table in args:
            self.cursor.execute(f"DROP {table}")
        self.conn.commit()

    def load_symbols(self):
        insert_statement = "INSERT INTO symbols(symbol, name) VALUES(?, ?)"

        symbols_data = json.loads(requests.get("https://api.iextrading.com/1.0/ref-data/symbols").text)
        for element in symbols_data:
            self.cursor.execute(insert_statement, (element["symbol"], element["name"]))
        self.conn.commit()

    def load_prices(self):
        update_statement = "UPDATE symbols SET last_price=?, current_price=? WHERE symbol=?"

        prices_data = json.loads(requests.get("https://api.iextrading.com/1.0/tops/last").text)
        for element in prices_data:
            price = element["price"]
            self.cursor.execute(update_statement, (price, price, element["symbol"]))
        self.conn.commit()

    def load_currencies(self):
        insert_statement = "INSERT INTO currencies(code, symbol, name) VALUES(?, ?, ?)"
        with open("currencies.json") as read_file:
            currencies_data = json.load(read_file)
            for currency in currencies_data:
                self.cursor.execute(insert_statement, (currency["cc"], currency["symbol"], currency["name"]))

    def currency_exists(self, code):
        select_statement = "EXISTS(SELECT 1 FROM currencies WHERE code = ?)"

        self.cursor.execute(select_statement, (code,))
        return self.cursor.fetchone()[0]

    def listing_exists(self, symbol):
        select_statement = "EXISTS(SELECT 1 FROM symbols WHERE symbol = ?)"

        self.cursor.execute(select_statement, (symbol,))
        return self.cursor.fetchone()[0]

    def get_type(self, input_string):
        input_data = input_string.split("/")
        length = len(input_data)

        if length == 2:
            if all([self.currency_exist(e) for e in input_data]):
                return MonitoringType.CurrencyPair
        elif length == 1:
            if self.listing_exists(input_data[0]):
                return MonitoringType.Stock
        return MonitoringType.Invalid

    def get_id(self, type, symbol):
        if type == EntityType.Currency:
            self.cursor.execute("SELECT(currency_id) FROM currencies WHERE code = ?", (symbol,))
        elif type == EntityType.Stock:
            self.cursor.execute("SELECT(symbol_id) FROM symbols WHERE symbol = ?", (symbol,))
        return self.cursor.fetchone()[0]

    def add_subscriber(self, user_id, type, symbol):
        if type == MonitoringType.CurrencyPair:
            insert_statement = "INSERT INTO pairs_subscribers(user_id, from_id, to_id) VALUES(?, ?, ?)"
            symbol = symbol.split("/")
            self.cursor.execute(insert_statement, (user_id, self.get_id(symbol[0]), self.get_id(symbol[1])))

        elif type == MonitoringType.Stock:
            insert_statement = "INSERT INTO stock_subscribers(user_id, symbol_id) VALUES(?, ?)"
            self.cursor.execute(insert_statement, (user_id, self.get_id(symbol)))
        self.conn.commit()

    def get_stock_updates(self):
        select_stocks_stmt = "SELECT symbol_id, symbol FROM stock_subscribers INNER JOIN symbols " \
                             "ON symbols.symbol_id = stock_subscribers.symbol_id"
        stocks = self.cursor.execute(select_stocks_stmt).fetchall()

        all_symbols = [e[1] for e in stocks]
        new_prices = requests.get(f"https://api.iextrading.com/1.0/tops/last?symbols={','.join(all_symbols)}").json()

        result = []
        for i in range(len(new_prices)):
            result.append(
                (
                    stocks[i][0],
                    new_prices[i]["price"]
                )
            )
        return result

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
