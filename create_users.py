"""Скрипт для создания пользователей в базе данных."""

import os
import sys
import argparse
from dotenv import load_dotenv
from core_logic.database import init_database, create_user, get_user_by_telegram_id, update_user
from core_logic.schemas import User

load_dotenv()

DB_FILE = os.getenv("DB_FILE", "family_calendar.db")


def create_users(telegram_id_1: int, name_1: str, telegram_id_2: int, name_2: str):
    """Создает пользователей в базе данных."""
    # Инициализируем БД
    init_database(DB_FILE)
    
    print("Создание пользователей в базе данных...")
    print("=" * 50)
    
    # Проверяем, не существуют ли уже пользователи
    existing_user_1 = get_user_by_telegram_id(DB_FILE, telegram_id_1)
    existing_user_2 = get_user_by_telegram_id(DB_FILE, telegram_id_2)
    
    if existing_user_1:
        print(f"\n⚠️ Пользователь с Telegram ID {telegram_id_1} уже существует, обновляем...")
        user_1 = User(
            id=existing_user_1.id,
            telegram_id=telegram_id_1,
            name=name_1,
            partner_telegram_id=telegram_id_2,
        )
        update_user(DB_FILE, user_1)
        print(f"✅ Пользователь {name_1} обновлен")
    else:
        # Создаем первого пользователя
        user_1 = User(
            telegram_id=telegram_id_1,
            name=name_1,
            partner_telegram_id=telegram_id_2,
        )
        try:
            create_user(DB_FILE, user_1)
            print(f"✅ Пользователь {name_1} создан (Telegram ID: {telegram_id_1})")
        except Exception as e:
            print(f"❌ Ошибка при создании пользователя {name_1}: {e}")
            return
    
    if existing_user_2:
        print(f"\n⚠️ Пользователь с Telegram ID {telegram_id_2} уже существует, обновляем...")
        user_2 = User(
            id=existing_user_2.id,
            telegram_id=telegram_id_2,
            name=name_2,
            partner_telegram_id=telegram_id_1,
        )
        update_user(DB_FILE, user_2)
        print(f"✅ Пользователь {name_2} обновлен")
    else:
        # Создаем второго пользователя
        user_2 = User(
            telegram_id=telegram_id_2,
            name=name_2,
            partner_telegram_id=telegram_id_1,
        )
        try:
            create_user(DB_FILE, user_2)
            print(f"✅ Пользователь {name_2} создан (Telegram ID: {telegram_id_2})")
        except Exception as e:
            print(f"❌ Ошибка при создании пользователя {name_2}: {e}")
            return
    
    print("\n" + "=" * 50)
    print("✅ Пользователи успешно созданы/обновлены!")
    print(f"   {name_1} (Telegram ID: {telegram_id_1}) ↔ {name_2} (Telegram ID: {telegram_id_2})")
    print("\nТеперь можно перезапустить бота.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Создание пользователей в базе данных")
    parser.add_argument("--telegram-id-1", type=int, help="Telegram ID первого пользователя")
    parser.add_argument("--name-1", type=str, help="Имя первого пользователя")
    parser.add_argument("--telegram-id-2", type=int, help="Telegram ID второго пользователя")
    parser.add_argument("--name-2", type=str, help="Имя второго пользователя")
    
    args = parser.parse_args()
    
    # Если параметры не переданы, запрашиваем интерактивно
    if not all([args.telegram_id_1, args.telegram_id_2]):
        print("Использование:")
        print("  python3 create_users.py --telegram-id-1 123456789 --name-1 'Имя1' --telegram-id-2 987654321 --name-2 'Имя2'")
        print("\nИли запустите интерактивно:")
        try:
            print("\nПервый пользователь (например, муж):")
            telegram_id_1 = int(input("Введите Telegram ID первого пользователя: ").strip())
            name_1 = input("Введите имя первого пользователя: ").strip() or "Пользователь 1"
            
            print("\nВторой пользователь (например, жена):")
            telegram_id_2 = int(input("Введите Telegram ID второго пользователя: ").strip())
            name_2 = input("Введите имя второго пользователя: ").strip() or "Пользователь 2"
        except (EOFError, ValueError, KeyboardInterrupt):
            print("\n❌ Ошибка ввода. Используйте параметры командной строки.")
            sys.exit(1)
    else:
        telegram_id_1 = args.telegram_id_1
        name_1 = args.name_1 or "Пользователь 1"
        telegram_id_2 = args.telegram_id_2
        name_2 = args.name_2 or "Пользователь 2"
    
    try:
        create_users(telegram_id_1, name_1, telegram_id_2, name_2)
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

