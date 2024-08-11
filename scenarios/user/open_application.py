import time

from aiogram import Router, Bot, types, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from models.addiction import Addiction
from models.application import Application
from models.comission import Commission
from models.confirmation import Confirmation
from models.requisites import Requisites
from models.user import User
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()
    from applications import show_messages_for_application

    @router.callback_query(F.data == callbacks.TAKE_APPLICATION_CALLBACK, UserFilter())
    async def select_application(callback_query: types.CallbackQuery):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.telegram_message_id == callback_query.message.message_id)
                    )
                    addiction = result.scalars().first()

                    if addiction is None:
                        await bot.delete_messages(
                            chat_id=callback_query.message.chat.id,
                            message_ids=[callback_query.message.message_id],
                        )
                        return

                    result = await session.execute(
                        select(Application).filter(
                            Application.id == addiction.application_id)
                    )
                    application = result.scalars().first()

                    if application is None or application.in_working and application.waiting_confirmation:
                        await bot.send_message(
                            text="Данную зявку уже взяли",
                            chat_id=callback_query.message.chat.id
                        )
                        return

                    result = await session.execute(
                        select(Commission)
                    )
                    commission = result.scalars().first()

                    text = (
                        "*Выберите способ оплаты комиссии:*\n_Фиксированная комиссия_ \- платите сразу\n_Процент от "
                        "стоимости_ \- платите процент от стоимости заказа")

                    await bot.edit_message_text(
                        text=text,
                        chat_id=callback_query.message.chat.id,
                        message_id=callback_query.message.message_id,
                        reply_markup=kb.create_price_keyboard(commission.percent, commission.fixed),
                        parse_mode=ParseMode.MARKDOWN_V2,
                    )

        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.SELECT_FIXED_CALLBACK, UserFilter())
    async def wait_paid(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.telegram_message_id == callback_query.message.message_id)
                    )
                    addiction = result.scalars().first()

                    if addiction is None:
                        await bot.delete_messages(
                            chat_id=callback_query.message.chat.id,
                            message_ids=[callback_query.message.message_id],
                        )

                    result = await session.execute(
                        select(Application).filter(
                            Application.id == addiction.application_id)
                    )
                    application = result.scalars().first()

                    if application is None or application.in_working or application.waiting_confirmation:
                        await bot.send_message(
                            text="Данную зявку уже взяли",
                            chat_id=callback_query.message.chat.id
                        )
                        return

                    result = await session.execute(
                        select(Requisites)
                    )
                    requisites = result.scalars().first()

                    result = await session.execute(
                        select(Commission)
                    )
                    commission = result.scalars().first()

                    text = (
                        f"*Требуется оплатить комиссию:*\n\nНомер карты \- *{requisites.card_number}*\nCумма оплаты: "
                        f"*{commission.fixed}* руб\nВ сообщении к переводу укажите номер: *{callback_query.from_user.id}*")

                    await bot.edit_message_text(
                        text=text,
                        chat_id=callback_query.message.chat.id,
                        message_id=callback_query.message.message_id,
                        reply_markup=kb.create_paid_fixed_callback(),
                        parse_mode=ParseMode.MARKDOWN_V2,
                    )

                    await state.update_data(pay_type="fixed")

                await session.commit()

        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.PAID_FIXED_CALLBACK, UserFilter())
    async def paid_fixed_callback(callback_query: types.CallbackQuery):
        from applications import show_confirmation_for_admins
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    text = ("<b>НЕ УДАЛЯЙТЕ ЭТО СООБЩЕНИЕ</b>\nВы сможете открыть заявку как только администратор "
                            "подтвердит перевод")

                    await bot.edit_message_text(
                        chat_id=callback_query.message.chat.id,
                        message_id=callback_query.message.message_id,
                        text=text,
                        parse_mode=ParseMode.HTML,
                    )

                    result = await session.execute(
                        select(Commission)
                    )
                    commission = result.scalars().first()

                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == callback_query.from_user.id)
                    )
                    user = result.scalars().first()
                    user.in_working = True

                    confirmation = Confirmation(
                        telegram_user_id=callback_query.from_user.id,
                        telegram_message_id=callback_query.message.message_id,
                        amount=commission.fixed,
                        created=round(time.time() * 1000),
                        type="open"
                    )
                    session.add(confirmation)
                    await session.flush()

                    result = await session.execute(
                        select(Addiction).filter(and_(
                            Addiction.telegram_message_id == callback_query.message.message_id,
                            Addiction.telegram_chat_id == callback_query.message.chat.id
                        ))
                    )
                    user_addiction = result.scalars().first()

                    result = await session.execute(
                        select(Application).filter(
                            Application.id == user_addiction.application_id)
                    )
                    application = result.scalars().first()

                    application.waiting_confirmation = True

                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.application_id == user_addiction.application_id)
                    )
                    app_addictions = result.scalars().all()

                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.telegram_chat_id == callback_query.message.chat.id)
                    )
                    current_user_addictions = result.scalars().all()

                    for ad in app_addictions:
                        if ad.telegram_message_id != callback_query.message.message_id:
                            try:
                                await bot.delete_message(
                                    chat_id=ad.telegram_chat_id,
                                    message_id=ad.telegram_message_id,
                                )
                            except:
                                ...
                            await session.delete(ad)

                    for ad in current_user_addictions:
                        if ad.telegram_message_id != callback_query.message.message_id:
                            try:
                                await bot.delete_message(
                                    chat_id=ad.telegram_chat_id,
                                    message_id=ad.telegram_message_id,
                                )
                            except:
                                ...
                            await session.delete(ad)

                    await show_confirmation_for_admins(
                        session=session,
                        confirmation=confirmation,
                        author_user=user,
                        bot=bot
                    )

                await session.commit()
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.OPEN_APPLICATION_CALLBACK, UserFilter())
    async def set_application(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            u, a = None, None
            async with AsyncSessionLocal() as session:
                async with session.begin():

                    data = await state.get_data()
                    pay_type = data.get("pay_type")

                    if pay_type is None:
                        await state.update_data(pay_type="percent")
                        pay_type = "percent"

                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == callback_query.from_user.id)
                    )
                    user = result.scalars().first()

                    result = await session.execute(
                        select(Commission)
                    )
                    commission = result.scalars().first()

                    if user is None:
                        return

                    if user.admin:
                        pay_type = "admin"

                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.telegram_message_id == callback_query.message.message_id)
                    )
                    addiction = result.scalars().first()

                    if addiction is None:
                        await bot.delete_messages(
                            chat_id=callback_query.message.chat.id,
                            message_ids=[callback_query.message.message_id],
                        )

                    result = await session.execute(
                        select(Application).filter(
                            Application.id == addiction.application_id)
                    )
                    application = result.scalars().first()

                    application.waiting_confirmation = False
                    application.in_working = True
                    application.working_user_id = callback_query.from_user.id
                    application.pay_type = pay_type
                    if pay_type == "percent":
                        application.com_value = commission.percent
                    elif pay_type == "fixed":
                        application.com_value = commission.fixed

                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.application_id == application.id)
                    )
                    addictions = result.scalars().all()

                    for ad in addictions:
                        try:
                            await bot.delete_message(
                                chat_id=ad.telegram_chat_id,
                                message_id=ad.telegram_message_id,
                            )
                        except:
                            ...
                        await session.delete(ad)

                    await session.flush()

                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.telegram_chat_id == user.telegram_chat_id)
                    )
                    current_user_addictions = result.scalars().all()

                    for ad in current_user_addictions:
                        try:
                            await bot.delete_message(
                                chat_id=ad.telegram_chat_id,
                                message_id=ad.telegram_message_id,
                            )
                        except:
                            ...
                        await session.delete(ad)

                    u = {'telegram_chat_id': user.telegram_chat_id}
                    a = {
                        'avito_chat_id': application.avito_chat_id,
                        'user_id': application.user_id,
                        'author_id': application.author_id,
                        'username': application.username
                    }

                await session.commit()

            await state.clear()

            await show_messages_for_application(
                state=state,
                bot=bot,
                telegram_chat_id=u['telegram_chat_id'],
                avito_chat_id=a['avito_chat_id'],
                avito_user_id=a['user_id'],
                author_id=a['author_id'],
                username=a['username']
            )

            await state.set_state(States.message)
        except Exception as e:
            print(e)

    dp.include_router(router)
