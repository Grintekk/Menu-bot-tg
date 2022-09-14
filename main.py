import os

import aiogram.dispatcher.webhook
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import Message, InputFile, InputMedia, InputMediaPhoto
from states import OrderRolls
import logging
import sqlite3

bot = Bot(token=os.environ["token"])
dp = Dispatcher(bot, storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)
con = sqlite3.connect("menu_meal.db")
cur = con.cursor()

# TODO replace buttons,send contact information
# last_message = ""


def buttons_default(kb):
    kb.add(types.InlineKeyboardButton(text="Вернуться в меню"))
    kb.add(types.InlineKeyboardButton(text="На главную"))


# def last_message(last_message):


@dp.message_handler(commands=["start"])
@dp.message_handler(state="*", content_types=['text'], text="На главную")
async def start_menu(message: types.Message, state: FSMContext):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.InlineKeyboardButton(text="Меню"))
    kb.add(types.InlineKeyboardButton(text="Контакты", callback_data="contacts"))
    await message.answer("Ky-ky", reply_markup=kb)
    await state.finish()


@dp.message_handler(state="*", content_types=['text'], text=['Меню', "В меню", "Вернуться в меню"])
async def show_menu(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['last_message'] = ""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.InlineKeyboardButton(text="Запечённые роллы"))
    kb.add(types.InlineKeyboardButton(text="Особенные роллы"))
    kb.add(types.InlineKeyboardButton(text="Драконы"))
    kb.add(types.InlineKeyboardButton(text="Сеты роллов"))
    kb.add(types.InlineKeyboardButton(text="На главную"))
    await message.answer("Вот такое вот меню блять", reply_markup=kb)
    await OrderRolls.first_menu.set()


@dp.callback_query_handler(text="comeback")
@dp.message_handler(state=OrderRolls.first_menu)
@dp.message_handler(state=OrderRolls.adding_dish, content_types=['text'], text=['Вернуться назад'])
async def show_second_menu(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        if 'Вернуться назад' == message.text:
            text = data['last_message']
        else:
            text = message.text
    text = text.split(" ")[0]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    cur.execute(f"SELECT include_meals, path_to_photo FROM grouped_meals WHERE type_meal='{text}'")
    rows = cur.fetchall()

    if rows:
        if text in "Сеты роллов":
            media = types.MediaGroup()
            for row in rows:
                dish_list = row[0].split(", ")
                media.attach_photo(types.InputFile(row[1]))
                for i in dish_list:
                    kb.add(types.InlineKeyboardButton(text=i))

            await bot.send_media_group(media=media, chat_id=message.chat.id)
        else:
            rows = rows[0]
            dish_list = rows[0].split(", ")
            # media.attach_photo(types.InputFile(rows[1]))
            for i in dish_list:
                kb.add(types.InlineKeyboardButton(text=i))
            # await bot.send_media_group(media=media, chat_id=message.chat.id)
            await bot.send_photo(photo=InputFile(rows[1]), chat_id=message.chat.id)
        # await state.update_data(last_message=text)
        async with state.proxy() as data:
            data['last_message'] = text
        kb.add(types.InlineKeyboardButton(text="В меню"))
        await message.answer("Выберите роллы", reply_markup=kb)
        await OrderRolls.second_menu.set()
    else:
        await message.answer("Воспользуйтесь пожалуйста клавиатурой")
        return


@dp.message_handler(state=OrderRolls.second_menu)
async def show_dish(message: types.Message, state: FSMContext):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    cur.execute(f"SELECT description, price, path_to_photo, id FROM menu_meal WHERE name='{message.text}'")
    rows = cur.fetchone()
    kb.add(types.InlineKeyboardButton(text="Добавить в корзину", callback_data="add_to_cart"))
    kb.add(types.InlineKeyboardButton(text="Просмотреть корзину", callback_data="check_cart"))
    kb.add(types.InlineKeyboardButton(text="Вернуться назад", callback_data="comeback"))
    buttons_default(kb)
    async with state.proxy() as data:
        data['last_meal_name'] = message.text
        data['last_meal_price'] = rows[1]
    if rows[2] is None:
        await message.answer(text=message.text + "\n" + rows[0] + "\n" + str(rows[1]) + "₴", reply_markup=kb)
    else:
        await bot.send_photo(photo=InputFile(rows[2]), chat_id=message.chat.id,
                             caption=rows[0] + "\n" + str(rows[1]) + "₴", reply_markup=kb)
    await OrderRolls.adding_dish.set()


@dp.callback_query_handler(text="add_to_cart")
@dp.message_handler(state=OrderRolls.adding_dish, content_types=['text'], text="Добавить в корзину")
async def adding_to_cart(message: types.Message, state: FSMContext):
    cur.execute(f"SELECT name_meals, price_sum FROM orders WHERE id_telegram='{message.chat.id}'")
    rows = cur.fetchone()
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.InlineKeyboardButton(text="Просмотреть корзину", callback_data="check_cart"))
    kb.add(types.InlineKeyboardButton(text="Изменить корзину", callback_data="change_cart"))
    kb.add(types.InlineKeyboardButton(text="Отправить заказ", callback_data="send_order"))
    kb.add(types.InlineKeyboardButton(text="Вернуться назад", callback_data="comeback"))
    kb.add(types.InlineKeyboardButton(text="Вернуться в меню"))
    async with state.proxy() as data:
        meal_name = data['last_meal_name']
        price_meal = data['last_meal_price']

    if rows:
        if len(rows[0].split('+')) > 7:
            await message.answer(text="Слишком много позиций в корзине", reply_markup=kb)
            return
        meal_name = str(rows[0]) + '+' + str(meal_name)
        price_meal = str(rows[1]) + '+' + str(price_meal)
        cur.execute(f"UPDATE orders SET name_meals='{meal_name}',"
                    f" price_sum='{price_meal}' WHERE id_telegram='{message.chat.id}'")
    else:
        cur.execute(f"INSERT INTO orders VALUES ('{message.chat.id}','{meal_name}','{price_meal}')")

    con.commit()
    await OrderRolls.adding_dish.set()
    await message.answer(text="Роллы добавлены", reply_markup=kb)


@dp.callback_query_handler(text="check_cart")
@dp.message_handler(state="*", content_types=['text'], text="Просмотреть корзину")
async def show_cart(message: types.Message, state: FSMContext):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    order_info = show_order(message.chat.id)
    if order_info is None:
        kb.add(types.InlineKeyboardButton(text="Вернуться назад", callback_data="comeback"))
        kb.add(types.InlineKeyboardButton(text="Вернуться в меню"))
        await message.answer(text="Ваша корзина пуста", reply_markup=kb)
    else:
        kb.add(types.InlineKeyboardButton(text="Изменить корзину", callback_data="change_cart"))
        kb.add(types.InlineKeyboardButton(text="Вернуться назад", callback_data="comeback"))
        kb.add(types.InlineKeyboardButton(text="Вернуться в меню"))
        await message.answer(text=order_info['text_message'], reply_markup=kb)


@dp.callback_query_handler(text="change_cart")
@dp.message_handler(state="*", content_types=['text'], text="Изменить корзину")
async def change_cart(message: types.Message, state: FSMContext):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    order_info = show_order(message.chat.id)
    if order_info['name_meals'] is not None:
        for i in order_info['name_meals']:
            kb.add(types.InlineKeyboardButton(text=i, callback_data="delete_position"))
        kb.add(types.InlineKeyboardButton(text="Очистить всю корзину", callback_data="delete_position"))
    else:
        kb.add(types.InlineKeyboardButton(text="В меню"))
        await message.answer(text="Увы, Ваша корзина пока что пуста :(", reply_markup=kb)
        return
    kb.add(types.InlineKeyboardButton(text="В меню"))
    await message.answer(text=order_info['text_message'], reply_markup=kb)
    await message.answer(text="Выберите блюдо, которое нужно убрать")
    await OrderRolls.change_cart.set()


@dp.callback_query_handler(text="delete_position")
@dp.message_handler(state=OrderRolls.change_cart, content_types=['text'])
async def delete_from_cart(message: types.Message, state: FSMContext):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    cur.execute(f"SELECT name_meals, price_sum FROM orders WHERE id_telegram='{message.chat.id}'")
    orders = cur.fetchone()
    if message.text == "Очистить всю корзину":
        a = ""
        cur.execute(f"UPDATE orders SET name_meals = '{a}', price_sum = '{a}' WHERE id_telegram='{message.chat.id}'")
        con.commit()
        kb.add(types.InlineKeyboardButton(text="Вернуться в меню"))
        await message.answer(text="Корзина очищена", reply_markup=kb)
    else:
        cur.execute(f"SELECT price FROM menu_meal WHERE name='{message.text}'")
        price_meal = cur.fetchone()[0]

        if orders[0] is not None:
            meal_and_price = [delete_position(orders[0], message.text), delete_position(orders[1], str(price_meal))]
            cur.execute(f"UPDATE orders SET name_meals='{meal_and_price[0]}', price_sum='{meal_and_price[1]}'"
                        f" WHERE id_telegram='{message.chat.id}'")
            con.commit()
            kb.add(types.InlineKeyboardButton(text="Просмотреть корзину", callback_data="check_cart"))
            kb.add(types.InlineKeyboardButton(text="Изменить корзину", callback_data="change_cart"))
            kb.add(types.InlineKeyboardButton(text="Вернуться в меню"))
            await message.answer(text="Блюдо удалено - " + message.text, reply_markup=kb)
        else:
            kb.add(types.InlineKeyboardButton(text="Вернуться в меню"))
            await message.answer(text="Увы, но корзина пуста", reply_markup=kb)


def delete_position(data_list, element):
    """
    delete 1 pos from order
    :param data_list: str (full order)
    :param element: str
    :return:
    """
    data_list = data_list.replace(element, '', 1)
    data_list = data_list.replace("++", "+")
    data_list = data_list.strip("+")
    return data_list


def show_order(id_telegram):
    """
    showing all positions in ur order
    :param id_telegram: int
    :return: dict
    """
    cur.execute(f"SELECT name_meals, price_sum FROM orders WHERE id_telegram='{id_telegram}'")
    rows = cur.fetchone()
    sum_meal = 0

    # TODO первый раз "показать корзину" дебаг
    price_list = rows[1].split('+')

    rows = rows[0].split('+')
    if rows[0] != '':
        for i in price_list:
            sum_meal += int(i)
        text_message = ''
        for i in range(len(rows)):
            text_message += rows[i] + ' - ' + price_list[i] + '₴' '\n'
        text_message += "Общая сумма заказа - " + str(sum_meal) + '₴'
        return {'name_meals': rows, 'text_message': text_message, 'sum_meal': sum_meal}
    else:
        return None


async def send_order(message: types.Message):
    # TODO send order to admins, delete order from database "orders", save order to archive, reset state
    pass


@dp.callback_query_handler(text="contacts")
@dp.message_handler(state="*", content_types=['text'], text="Контакты")
async def show_contacts(message: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.InlineKeyboardButton(text="нет"))
    #buttons_default(kb)
    await message.answer("Улица Н", reply_markup=kb)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
