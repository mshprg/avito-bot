from aiogram.fsm.state import State, StatesGroup


# Все состояние
class States(StatesGroup):
    # Состояние ввода номера телефона
    phone = State()
    # Состояние ввода ФИО
    name = State()
    # Состояние ввода локации
    city = State()
    # Состояние ввода кода, отправленного на телефон
    phone_code = State()
    # Состояние ввода сообщения в чате авито
    message = State()
    avito_info = State()
    admin_change = State()
    report_date = State()
    cities_to_add = State()
    cities_to_remove = State()
    shop_price = State()
    add_location = State()
    previous_state = State()
    feedback = State()
    visible_feedbacks = State()
    visible_payments = State()
    ban = State()
    unban = State()
    sending_text = State()
    sending_locations = State()
    visible_tariffs = State()
    current_admin_tariff = State()

    # Здесь храняться id сообщений
    ids = State()
    admin_ids = State()
    shop_ids = State()
    cities_ids = State()
    make_admin_ids = State()
    report_ids = State()
    location_ids = State()
    feedback_admin_ids = State()
    payments_admin_ids = State()
    ban_ids = State()
    user_ids = State()
    sending_ids = State()
    subscribe_ids = State()

    feedback_ids = State()
    video_ids = State()
