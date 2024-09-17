from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import callbacks


def generate_inline_markup(data):
    markup = InlineKeyboardBuilder()
    for i in data:
        markup.row(InlineKeyboardButton(text=i[0], callback_data=i[1]))
    return markup.as_markup()


def create_cities_keyboard(cities):
    buttons = []
    tmp = []
    for city in cities:
        button = KeyboardButton(text=city)
        tmp.append(button)
        if len(tmp) == 2:
            buttons.append(tmp)
            tmp = []

    if tmp:
        buttons.append(tmp)

    return ReplyKeyboardMarkup(keyboard=buttons, one_time_keyboard=True)


def create_feedback_keyboard():
    button_1 = KeyboardButton(text="Обратная связь")
    button_2 = KeyboardButton(text="Обучающие видео")
    button_3 = KeyboardButton(text="Информация о подписке")
    return ReplyKeyboardMarkup(keyboard=[[button_1], [button_2], [button_3]])


def create_repeat_phone_keyboard():
    return generate_inline_markup([
        ['Повторить ввод номера', callbacks.REPEAT_PHONE_CALLBACK]
    ])


def create_policy_accept_callback():
    return generate_inline_markup([
        ['Далее', callbacks.POLICY_ACCEPT_CALLBACK]
    ])


def create_feedback_actions_keyboard():
    return generate_inline_markup([
        ['Задать вопрос', callbacks.SEND_QUESTION_CALLBACK],
        ['Предложить улучшение', callbacks.SEND_IMPROVEMENT_CALLBACK]
    ])


def create_clear_feedback_keyboard():
    return generate_inline_markup([
        ['Удалить сообщения', callbacks.DELETE_MESSAGES_CALLBACK],
    ])


def create_clear_video_keyboard():
    return generate_inline_markup([
        ['Удалить видео', callbacks.DELETE_MESSAGES_CALLBACK],
    ])


def create_answer_feedback_keyboard():
    return generate_inline_markup([
        ['Ответить на вопрос', callbacks.ANSWER_QUESTION_CALLBACK],
    ])


def create_show_applications_keyboard():
    return generate_inline_markup([['Показать заявки', callbacks.SHOW_APPLICATIONS_CALLBACK]])


def create_application_keyboard():
    return generate_inline_markup([['Взять заявку', callbacks.TAKE_APPLICATION_CALLBACK]])


def create_back_to_apps_keyboard():
    return generate_inline_markup([['Отказаться от заявки', callbacks.BACK_TO_APPS_CALLBACK]])


def create_exactly_back_keyboard():
    return generate_inline_markup([['Я точно хочу отказаться', callbacks.EXACTLY_BACK_CALLBACK]])


def create_application_actions_keyboard():
    return generate_inline_markup([
        ['Завешил работу', callbacks.FINISH_APPLICATION_CALLBACK],
        ['Отказаться от заявки', callbacks.STOP_APPLICATION_CALLBACK]
    ])


def create_stop_application_keyboard():
    return generate_inline_markup([
        ['Я хочу отказаться от заявки', callbacks.EXACTLY_STOP_CALLBACK],
        ['Нет', callbacks.BACK_TO_APPLICATION_CALLBACK]
    ])


def create_finish_application_keyboard():
    return generate_inline_markup([
        ['Я получил оплату, завершить работу', callbacks.EXACTLY_FINISH_CALLBACK],
        ['Назад', callbacks.BACK_TO_APPLICATION_CALLBACK]
    ])


def create_paid_comm_keyboard():
    return generate_inline_markup([
        ['Я оплатил', callbacks.PAID_COMM_CALLBACK],
    ])


def create_activate_admin_keyboard():
    return generate_inline_markup([
        ['Активировать права', callbacks.ACTIVATE_ADMIN_CALLBACK],
    ])


def create_deactivate_admin_keyboard():
    return generate_inline_markup([
        ['Деактивировать права', callbacks.DEACTIVATE_ADMIN_CALLBACK],
    ])


def create_delete_admin_messages_keyboard():
    return generate_inline_markup([
        ['Удалить сообщения для администратора', callbacks.DELETE_MESSAGES_CALLBACK],
    ])


def create_manage_cities_keyboard():
    return generate_inline_markup([
        ['Добавить города', callbacks.ADD_CITIES_CALLBACK],
        ['Удалить города', callbacks.DELETE_CITIES_CALLBACK],
        ['Удалить сообщения для администратора', callbacks.DELETE_MESSAGES_CALLBACK],
    ])


def create_manage_shop_keyboard():
    return generate_inline_markup([
        ['Изменить цену подписки на 30 дней', callbacks.CHANGE_30_CALLBACK],
        ['Удалить сообщения для администратора', callbacks.DELETE_MESSAGES_CALLBACK],
    ])


def create_manage_requisites_keyboard():
    return generate_inline_markup([
        ['Изменить номер карты', callbacks.CHANGE_REQUISITES_CALLBACK],
        ['Удалить сообщения для администратора', callbacks.DELETE_MESSAGES_CALLBACK],
    ])


def create_add_city_keyboard():
    return generate_inline_markup([
        ['Добавить локацию', callbacks.ADD_CITY_TO_ITEM_CALLBACK],
    ])


def create_close_application_keyboard():
    return generate_inline_markup([
        ['Закрыть заявку', callbacks.CLOSE_APPLICATION_CALLBACK],
    ])


def create_list_confirmations_keyboard():
    return generate_inline_markup([
        ['Отправить сообщение с действиями', callbacks.APPROVED_CONF_CALLBACK],
    ])


def create_select_sending_keyboard():
    return generate_inline_markup([
        ['Отправить сообщение всем пользователям', callbacks.SEND_MESSAGE_ALL_CALLBACK],
        ['Выбрать локацию', callbacks.SELECT_SENDING_CITY_CALLBACK],
    ])


def create_pay_subscribe_keyboard():
    return generate_inline_markup([
        ['Оплатить доступ', callbacks.BUY_SUBSCRIBE_CALLBACK],
    ])


def create_admin_subscribe_keyboard():
    return generate_inline_markup([
        ['Продлить подписку бесплатно', callbacks.BUY_ADMIN_SUBSCRIBE_CALLBACK],
    ])
