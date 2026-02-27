from aiogram.fsm.state import StatesGroup, State

class SearchVinyl(StatesGroup):
    waiting_for_query = State()
    waiting_for_barcode = State()
    waiting_for_catno = State()