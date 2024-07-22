from aiogram.fsm.state import State, StatesGroup


# Состояние
class States(StatesGroup):
    phone = State()
    name = State()
    city = State()
    message = State()
    avito_info = State()
    pay_type = State()
    finish_files = State()
    finish_price = State()
    admin_change = State()
    report_date = State()
    cities_to_add = State()
    cities_to_remove = State()
    fixed_commission = State()
    percent_commission = State()
    requisites = State()
    add_location = State()
    previous_state = State()

    ids = State()
    admin_ids = State()
    commission_ids = State()
    requisites_ids = State()
    cities_ids = State()
    make_admin_ids = State()
    report_ids = State()
    location_ids = State()
