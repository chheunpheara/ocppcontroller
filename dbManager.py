from tinydb import TinyDB, Query


class JsonDB():
    def __init__(self) -> None:
        self.db = TinyDB('./db/ocpp1.6.json')

