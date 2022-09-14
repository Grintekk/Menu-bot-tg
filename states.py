from aiogram.dispatcher.filters.state import State, StatesGroup


class OrderRolls(StatesGroup):
    first_menu = State()
    second_menu = State()
    adding_dish = State()
    change_cart = State()
    # choosing = State()
    # ending_choosing = State()