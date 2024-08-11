from aiogram import Router, Bot, F, types
from aiogram.enums import ParseMode
from aiogram.filters import StateFilter, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, add_state_id
from models.confirmation import Confirmation
from models.confirmation_addiction import ConfirmationAddiction
from models.user import User
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    @router.message(Command("confirmations"), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def get_confirmations(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="confirmation_admin_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Confirmation)
                    )
                    confirmations = result.scalars().all()

                    if len(confirmations) == 0:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Переводов не найдено",
                            keyboard=kb.create_delete_admin_messages_keyboard(),
                            state_name="confirmation_admin_ids",
                        )
                        return

                    user_ids = [c.telegram_user_id for c in confirmations]
                    result = await session.execute(
                        select(User).filter(User.telegram_user_id.in_(user_ids))
                    )
                    users = result.scalars().all()
                    d = {}

                    for u in users:
                        d[u.telegram_user_id] = u

                    visible_confirmations = []
                    for c in confirmations:
                        text = (f"<b>Подтверждение от пользователя {d[c.telegram_user_id].name}</b>\nНомер телефона: "
                                f"{d[c.telegram_user_id].phone}\nКод: <b>{c.telegram_user_id}</b>\nСумма: <b>{c.amount}</b>")
                        m = await send_state_message(
                            state=state,
                            message=message,
                            text=text,
                            parse_mode=ParseMode.HTML,
                            keyboard=kb.create_list_confirmations_keyboard(),
                            state_name="confirmation_admin_ids",
                        )
                        visible_confirmations.append({
                            'message_id': m.message_id,
                            'confirmation': c.to_dict()
                        })

                    await state.update_data(visible_confirmations=visible_confirmations)

                    await send_state_message(
                        state=state,
                        message=message,
                        text="Действия",
                        keyboard=kb.create_delete_admin_messages_keyboard(),
                        state_name="confirmation_admin_ids",
                    )

                await session.commit()

        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.APPROVED_CONF_CALLBACK, UserFilter(check_admin=True))
    async def approved_confirmation_callback(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    conf = None
                    data = await state.get_data()
                    visible_confirmations = data.get("visible_confirmations", [])

                    for c in visible_confirmations:
                        if c['message_id'] == callback_query.message.message_id:
                            conf = c['confirmation']

                    if conf is None:
                        result = await session.execute(
                            select(ConfirmationAddiction).filter(and_(
                                ConfirmationAddiction.telegram_chat_id == callback_query.message.chat.id,
                                ConfirmationAddiction.telegram_message_id == callback_query.message.message_id,
                            ))
                        )
                        conf_addiction = result.scalars().first()
                        result = await session.execute(
                            select(Confirmation).filter(Confirmation.id == conf_addiction.confirmation_id)
                        )
                    else:
                        result = await session.execute(
                            select(Confirmation).filter(Confirmation.id == conf['id'])
                        )
                    confirmation = result.scalars().first()

                    if confirmation is None:
                        return

                    if confirmation.type == "open":
                        text = "Оплата подтверждена"
                        await bot.edit_message_text(
                            chat_id=confirmation.telegram_user_id,
                            message_id=confirmation.telegram_message_id,
                            text=text,
                            reply_markup=kb.create_confirmation_keyboard()
                        )
                    elif confirmation.type == "close":
                        text = "Оплата подтверждена"
                        await bot.edit_message_text(
                            chat_id=confirmation.telegram_user_id,
                            message_id=confirmation.telegram_message_id,
                            text=text,
                            reply_markup=kb.create_close_application_keyboard()
                        )

                    result = await session.execute(
                        select(ConfirmationAddiction).filter(ConfirmationAddiction.confirmation_id == confirmation.id)
                    )
                    conf_addictions = result.scalars().all()

                    await bot.delete_message(
                        chat_id=callback_query.message.chat.id,
                        message_id=callback_query.message.message_id
                    )

                    for ca in conf_addictions:
                        try:
                            await bot.delete_message(
                                chat_id=ca.telegram_chat_id,
                                message_id=ca.telegram_message_id
                            )
                            await session.delete(ca)
                        except:
                            ...

                    await session.delete(confirmation)

                await session.commit()
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.DELETE_CONF_CALLBACK)
    async def delete_conf_message(callback_query: types.CallbackQuery):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(ConfirmationAddiction).filter(and_(
                            ConfirmationAddiction.telegram_chat_id == callback_query.message.chat.id,
                            ConfirmationAddiction.telegram_message_id == callback_query.message.message_id,
                        ))
                    )
                    conf_addiction = result.scalars().first()

                    if conf_addiction:
                        await session.delete(conf_addiction)

                    try:
                        await bot.delete_message(
                            chat_id=callback_query.message.chat.id,
                            message_id=callback_query.message.message_id
                        )
                    except:
                        ...

                await session.commit()
        except Exception as e:
            print(e)

    dp.include_router(router)
