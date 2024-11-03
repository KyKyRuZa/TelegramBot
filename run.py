import asyncio
import logging
import sys
import psycopg2

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import TOKEN, DB_URL, ADMIN_IDS
from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.filters import CommandStart,Command
from aiogram.types import Message, ReplyKeyboardMarkup,KeyboardButton

'''
CREATE TABLE users (
    id SERIAL PRIMARY KEY, 
    name VARCHAR(50),  
    age INTEGER,
    telegram_id BIGINT UNIQUE
)
'''

dp = Dispatcher()
router = Router()
dp.include_router(router)

class UserDelete(StatesGroup):
    confirm_delete = State()

class ProfileEdit(StatesGroup):
    waiting_name = State()
    waiting_age = State()

class Registration(StatesGroup):
    waiting_name = State()
    waiting_age = State()

def user_kb(user_telegram_id: int):
    kb_list = []

    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT EXISTS(SELECT 1 FROM users WHERE telegram_id = %s)", (user_telegram_id,))
    is_registered = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    if not is_registered:
        kb_list.append([KeyboardButton(text="Регистрация")]) 
    else:
        kb_list.extend([
            [KeyboardButton(text="Мой профиль")],
            [KeyboardButton(text="Изменить профиль")],
            [KeyboardButton(text="Удалить профиль")]
        ])    
    keyboard = ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True, input_field_placeholder="Выберите действие"
    )
    return keyboard

def admin_kb():
    kb_list = [
        [KeyboardButton(text="Все пользователи")],
        [KeyboardButton(text="Статистика")],
        [KeyboardButton(text="Удалить профили")],
        [KeyboardButton(text="Главное меню")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True)
    return keyboard

async def check_user_exists(telegram_id: int) -> bool:
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT EXISTS(SELECT 1 FROM users WHERE telegram_id = %s)", (telegram_id,))
    exists = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return exists

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    is_registered = await check_user_exists(message.from_user.id)
    if is_registered:
        await message.answer("Рады видеть вас снова! Выберите действие:", reply_markup=user_kb(message.from_user.id))
    else:
        await message.answer("Добро пожаловать! Для использования бота необходимо зарегистрироваться!", reply_markup=user_kb(message.from_user.id))


# USER KB
@dp.message(F.text == "Регистрация")
async def start_registration(message: types.Message, state: FSMContext):
    if await check_user_exists(message.from_user.id):
        await message.answer("Вы уже зарегистрированы!")
        return
        
    await message.answer("Введите ваше имя:")
    await state.set_state(Registration.waiting_name)

@dp.message(Registration.waiting_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Теперь введите ваш возраст:")
    await state.set_state(Registration.waiting_age)

@dp.message(Registration.waiting_age)
async def process_age(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
        if age <= 0 or age > 120:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректный возраст (1-120)")
        return

    user_data = await state.get_data()
    
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO users (telegram_id, name, age)
            VALUES (%s, %s, %s)
            """,
            (message.from_user.id, user_data['name'], age)
        )
        conn.commit()
        await message.answer("Регистрация успешно завершена!", reply_markup=user_kb(message.from_user.id))
    except Exception as e:
        await message.answer(f"Ошибка при регистрации: {str(e)}")
    finally:
        cursor.close()
        conn.close()
        await state.clear()

@dp.message(F.text =="Мой профиль")
async def show_profile(message: types.Message):
    if not await check_user_exists(message.from_user.id):
        await message.answer("Вы не зарегистрированы!")
        return
        
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT name, age FROM users WHERE telegram_id = %s", (message.from_user.id,))
    user_data = cursor.fetchone()
    cursor.close()
    conn.close()
    
    await message.answer(f"Ваш профиль:\nИмя: {user_data[0]}\nВозраст: {user_data[1]}")

@dp.message(F.text == "Изменить профиль")
async def edit_profile_start(message: types.Message, state: FSMContext):
    if not await check_user_exists(message.from_user.id):
        await message.answer("Сначала необходимо зарегистрироваться!")
        return
    
    await message.answer("Введите новое имя:")
    await state.set_state(ProfileEdit.waiting_name)

@dp.message(ProfileEdit.waiting_name)
async def edit_name(message: types.Message, state: FSMContext):
    await state.update_data(new_name=message.text)
    await message.answer("Теперь введите новый возраст:")
    await state.set_state(ProfileEdit.waiting_age)

@dp.message(ProfileEdit.waiting_age)
async def edit_age(message: types.Message, state: FSMContext):
    try:
        new_age = int(message.text)
        if new_age <= 0 or new_age > 100:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректный возраст (1-100)")
        return

    user_data = await state.get_data()
    new_name = user_data['new_name']

    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE users 
            SET name = %s, age = %s 
            WHERE telegram_id = %s
            """,
            (new_name, new_age, message.from_user.id)
        )
        conn.commit()
        await message.answer("Профиль успешно обновлен!", reply_markup=user_kb(message.from_user.id))
    except Exception as e:
        await message.answer(f"Произошла ошибка при обновлении профиля: {str(e)}")
    finally:
        cursor.close()
        conn.close()
        await state.clear()

#ADMIN KB
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Доступ запрещен")
        return
    await message.answer("Панель администратора", reply_markup=admin_kb())

@dp.message(F.text == "Все пользователи")
async def get_all_users(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, age FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    
    response = "Список пользователей:\n\n"
    for user in users:
        response += f"ID: {user[0]}, Имя: {user[1]}, Возраст: {user[2]}\n"
    
    await message.answer(response)

@dp.message(F.text == "Статистика")
async def get_statistics(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT AVG(age) FROM users")
    avg_age = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()
    
    stats = f" Статистика:\n\n"
    stats += f" Всего пользователей: {total_users}\n"
    stats += f" Средний возраст: {round(avg_age if avg_age else 0, 1)}"
    
    await message.answer(stats)

@dp.message(F.text == "Главное меню")
async def return_to_main(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Главное меню", reply_markup=user_kb(message.from_user.id))

@dp.message(F.text == "Удалить профиль")
async def start_delete_profile(message: types.Message, state: FSMContext):
    if not await check_user_exists(message.from_user.id):
        await message.answer("Профиль не найден!")
        return
        
    kb = [
        [KeyboardButton(text="Да, удалить профиль")],
        [KeyboardButton(text="Нет, отменить")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    
    await message.answer("Вы уверены, что хотите удалить свой профиль?", reply_markup=keyboard)
    await state.set_state(UserDelete.confirm_delete)

@dp.message(UserDelete.confirm_delete)
async def confirm_delete_profile(message: types.Message, state: FSMContext):
    if message.text == "Да, удалить профиль":
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "DELETE FROM users WHERE telegram_id = %s",
                (message.from_user.id,)
            )
            conn.commit()
            await message.answer("Ваш профиль успешно удален!", reply_markup=user_kb(message.from_user.id))
        except Exception as e:
            await message.answer(f"Ошибка при удалении профиля: {str(e)}")
        finally:
            cursor.close()
            conn.close()
    else:
        await message.answer("Удаление профиля отменено", reply_markup=user_kb(message.from_user.id))
    
    await state.clear()


async def main() -> None:
    bot = Bot(token = TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('End session')