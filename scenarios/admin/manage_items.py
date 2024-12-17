import time
from asyncio import sleep

from aiogram import Router, Bot, types, F
from aiogram.filters import StateFilter, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, add_state_id
from models.application import Application
from models.item import Item
from models.item_addiction import ItemAddiction
from models.subscription import Subscription
from models.user import User
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    # Обработчик команды /items для отображения объявлений без указания локации
    @router.message(Command('items'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def get_none_items(message: types.Message):
        try:
            from applications import show_new_item_for_admin
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Получаем объявления, у которых не указана локация
                    result = await session.execute(
                        select(Item).filter(
                            Item.location == "None"
                        )
                    )
                    items = result.scalars().all()

                    if len(items) == 0:
                        # Если таких объявлений нет, отправляем уведомление
                        await bot.send_message(
                            chat_id=message.chat.id,
                            text="Нет новых объявлений"
                        )
                        return

                    # Для каждого объявления вызываем обработку и показ для админов
                    for item in items:
                        await show_new_item_for_admin(
                            session=session,
                            bot=bot,
                            url=item.url,
                            item_id=item.id,
                            avito_item_id=item.avito_item_id,
                            chat_id=message.chat.id
                        )
        except Exception as e:
            print(e)

    # Обработчик коллбэка для добавления локации к объявлению
    @router.callback_query(F.data == callbacks.ADD_CITY_TO_ITEM_CALLBACK, UserFilter(check_admin=True))
    async def add_location_to_item(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            # Сохраняем текущее состояние FSM
            current_state = await state.get_state()
            await state.update_data(previous_state=current_state)

            # Сохраняем ID сообщения для дальнейшей обработки
            await add_state_id(
                state=state,
                message_id=callback_query.message.message_id,
                state_name="location_ids"
            )

            # Запрашиваем у пользователя список локаций
            await send_state_message(
                state=state,
                message=callback_query.message,
                text="Введите локации через запятую, например:\nМосква, Московская область",
                state_name="location_ids"
            )

            # Сохраняем дополнительные данные о сообщении
            await state.update_data(add_location=[callback_query.message.message_id, callback_query.message.chat.id])
            await state.set_state(States.add_location)
        except Exception as e:
            print(e)

    # Обработчик состояния для чтения введённых локаций
    @router.message(States.add_location, UserFilter(check_admin=True))
    async def read_locations(message: types.Message, state: FSMContext):
        from applications import show_application
        try:
            # Сохраняем ID сообщения для дальнейшей обработки
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="location_ids"
            )

            # Получаем введённые локации
            locations = message.text
            if not locations:
                # Если текст пустой, просим повторить ввод
                await send_state_message(
                    state=state,
                    message=message,
                    text="Ошибка, повторите ввод",
                    state_name="location_ids"
                )
                await state.set_state(States.add_location)
                return

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Извлекаем данные состояния FSM
                    data = await state.get_data()
                    data = data.get("add_location", [1, 1])

                    # Получаем связь между сообщением и объявлением
                    result = await session.execute(
                        select(ItemAddiction).filter(and_(
                            ItemAddiction.telegram_message_id == data[0],
                            ItemAddiction.telegram_chat_id == data[1]
                        ))
                    )
                    item_addiction = result.scalars().first()

                    if not item_addiction:
                        return

                    # Получаем само объявление
                    result = await session.execute(
                        select(Item).filter(Item.id == item_addiction.item_id)
                    )
                    item = result.scalars().first()

                    if not item:
                        return

                    # Получаем все заявки, связанные с этим объявлением
                    result = await session.execute(
                        select(Application).filter(Application.item_id == item.avito_item_id)
                    )
                    applications = result.scalars().all()

                    # Обновляем локацию для объявления и всех связанных заявок
                    item.location = locations
                    for ap in applications:
                        ap.item_location = locations

                    # Получаем всех подписчиков с активной подпиской
                    result = await session.execute(
                        select(Subscription).filter(Subscription.end_time > int(time.time() * 1000))
                    )
                    subscriptions = result.scalars().all()

                    # Отбираем пользователей, которые не заблокированы и не работают
                    user_ids = list(set([s.telegram_user_id for s in subscriptions]))
                    result = await session.execute(
                        select(User).filter(and_(
                            User.in_working == False,
                            User.banned == False,
                            User.telegram_user_id.in_(user_ids)
                        ))
                    )
                    users = result.scalars().all()

                    # Удаляем связи между сообщениями и объявлениями и удаляем все сообщения новых объявлений у админов
                    result = await session.execute(
                        select(ItemAddiction).filter(ItemAddiction.item_id == item.id)
                    )
                    item_addictions = result.scalars().all()

                    for ad in item_addictions:
                        await sleep(0.2)
                        try:
                            await bot.delete_message(
                                chat_id=ad.telegram_chat_id,
                                message_id=ad.telegram_message_id,
                            )
                        except Exception as e:
                            print(e)
                        await session.delete(ad)

                    await session.flush()

                    # Отправляем заявки подходящим пользователям
                    for user in users:
                        for ap in applications:
                            await show_application(
                                session=session,
                                application=ap,
                                user_city=user.city,
                                bot=bot,
                                chat_id=user.telegram_chat_id,
                                is_root_admin=user.admin,
                            )

                # Подтверждаем изменения в базе данных
                await session.commit()

            # Сообщаем об успешном добавлении локации
            await send_state_message(
                state=state,
                message=message,
                text="Локация успешно добавлена",
                state_name="location_ids",
                keyboard=kb.create_delete_admin_messages_keyboard()
            )

            # Возвращаемся к предыдущему состоянию, если оно было сохранено
            data = await state.get_data()
            previous_state = data.get('previous_state')

            if previous_state:
                await state.set_state(previous_state)

        except Exception as e:
            print(e)

    dp.include_router(router)
