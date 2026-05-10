"""
MoodLog - Персональный дневник настроения и саморефлексии
Консольное приложение для отслеживания эмоционального состояния
"""

import sqlite3
import logging
import os
import json
import csv
import zipfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ------------------------- Конфигурация -------------------------
load_dotenv()
DB_PATH = os.getenv("DB_PATH", "mood.db")

logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

# ------------------------- Инициализация БД -------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mood_entries (
            date TEXT PRIMARY KEY,
            mood_score INTEGER NOT NULL,
            stress_level INTEGER NOT NULL,
            sleep_quality TEXT NOT NULL,
            events TEXT,
            tags TEXT,
            quote TEXT
        )
    ''')
    conn.commit()
    conn.close()
    logging.info("База данных инициализирована")

# ------------------------- Вспомогательные функции -------------------------
def get_date():
    while True:
        date_str = input("Дата (YYYY-MM-DD) или Enter для сегодня: ").strip()
        if not date_str:
            return datetime.now().strftime("%Y-%m-%d")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except ValueError:
            print("Ошибка: неверный формат")

def get_rating(prompt, min_val=1, max_val=10):
    while True:
        try:
            val = int(input(prompt))
            if min_val <= val <= max_val:
                return val
            print(f"Ошибка: от {min_val} до {max_val}")
        except ValueError:
            print("Ошибка: введите число")

def get_sleep():
    print("Качество сна: 1-плохой, 2-средний, 3-хороший")
    while True:
        choice = input("Выберите (1/2/3): ").strip()
        if choice == "1":
            return "плохой"
        elif choice == "2":
            return "средний"
        elif choice == "3":
            return "хороший"
        print("Ошибка: введите 1, 2 или 3")

# ------------------------- Ввод/редактирование записи -------------------------
def create_or_edit_entry():
    date = get_date()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mood_entries WHERE date = ?", (date,))
    existing = cursor.fetchone()
    
    if existing:
        print(f"\nЗапись на {date} уже существует. Редактирование (Enter - не менять)")
    
    print("\n--- Ввод данных ---")
    
    # Настроение
    if existing:
        mood_str = input(f"Настроение (1-10) [было {existing[1]}]: ").strip()
        mood = int(mood_str) if mood_str else existing[1]
    else:
        mood = get_rating("Настроение (1-10): ")
    
    # Стресс
    if existing:
        stress_str = input(f"Стресс (1-10) [было {existing[2]}]: ").strip()
        stress = int(stress_str) if stress_str else existing[2]
    else:
        stress = get_rating("Стресс (1-10): ")
    
    # Сон
    if existing:
        sleep_choice = input(f"Сон [было {existing[3]}] изменить? (+/нет): ").strip()
        sleep = get_sleep() if sleep_choice == "+" else existing[3]
    else:
        sleep = get_sleep()
    
    # События
    if existing:
        events = input(f"События: ").strip()
        if not events:
            events = existing[4]
    else:
        events = input("События дня: ").strip()
    
    # Теги
    if existing:
        tags = input(f"Теги [было {existing[5]}]: ").strip()
        if not tags:
            tags = existing[5]
    else:
        tags = input("Теги (через запятую): ").strip()
    
    # Цитата
    if existing:
        quote = input(f"Цитата: ").strip()
        if not quote:
            quote = existing[6]
    else:
        quote = input("Цитата дня (можно пропустить): ").strip()
    
    if existing:
        cursor.execute('''
            UPDATE mood_entries 
            SET mood_score=?, stress_level=?, sleep_quality=?, events=?, tags=?, quote=?
            WHERE date=?
        ''', (mood, stress, sleep, events, tags, quote, date))
        logging.info(f"Обновлена запись за {date}")
        print(f"✅ Запись за {date} обновлена")
    else:
        cursor.execute('''
            INSERT INTO mood_entries (date, mood_score, stress_level, sleep_quality, events, tags, quote)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (date, mood, stress, sleep, events, tags, quote))
        logging.info(f"Создана запись за {date}")
        print(f"✅ Запись за {date} создана")
    
    conn.commit()
    conn.close()

# ------------------------- Просмотр записей -------------------------
def view_entries():
    period = input("Период: week/month/all: ").strip().lower()
    
    if period == "week":
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        query = "SELECT * FROM mood_entries WHERE date >= ? ORDER BY date"
        params = (start_date,)
    elif period == "month":
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        query = "SELECT * FROM mood_entries WHERE date >= ? ORDER BY date"
        params = (start_date,)
    else:
        query = "SELECT * FROM mood_entries ORDER BY date"
        params = ()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query, params)
    entries = cursor.fetchall()
    conn.close()
    
    if not entries:
        print("\n📭 Нет записей")
        return
    
    print("\n" + "="*60)
    for entry in entries:
        print(f"\n📅 {entry[0]}")
        print(f"   Настроение: {entry[1]}/10  |  Стресс: {entry[2]}/10  |  Сон: {entry[3]}")
        print(f"   Теги: {entry[5]}")
        if entry[4]:
            print(f"   События: {entry[4][:100]}...")
        print("-"*40)

# ------------------------- ASCII-графики -------------------------
def draw_bar(value, max_val=10, width=20):
    """Рисует текстовую полосу"""
    filled = int((value / max_val) * width)
    return "█" * filled + "░" * (width - filled)

def show_mood_chart():
    """График изменения настроения"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT date, mood_score FROM mood_entries ORDER BY date DESC LIMIT 14")
    entries = cursor.fetchall()
    conn.close()
    
    if not entries:
        print("\n📭 Нет данных для графика")
        return
    
    print("\n--- ИЗМЕНЕНИЕ НАСТРОЕНИЯ ---")
    for date, mood in reversed(entries):
        bar = draw_bar(mood)
        print(f"{date}: {mood:2} {bar}")

def show_tag_distribution():
    """Распределение тегов за последние 30 дней"""
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT tags FROM mood_entries WHERE date >= ? AND tags != ''", (start_date,))
    entries = cursor.fetchall()
    conn.close()
    
    tag_count = {}
    for (tags_str,) in entries:
        for tag in tags_str.split(','):
            tag = tag.strip()
            if tag:
                tag_count[tag] = tag_count.get(tag, 0) + 1
    
    if not tag_count:
        print("\n📭 Нет тегов за последние 30 дней")
        return
    
    total = sum(tag_count.values())
    print("\n--- РАСПРЕДЕЛЕНИЕ ТЕГОВ (последние 30 дней) ---")
    for tag, count in sorted(tag_count.items(), key=lambda x: x[1], reverse=True):
        percent = (count / total) * 100
        bar = draw_bar(percent, max_val=100, width=15)
        print(f"{tag:10}: {bar} {percent:.1f}%")

# ------------------------- Статистика и инсайты -------------------------
def get_average_stats():
    """Среднее настроение и стресс за выбранный период"""
    period = input("Период: week/month/all: ").strip().lower()
    
    if period == "week":
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == "month":
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    else:
        start_date = "2000-01-01"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT AVG(mood_score), AVG(stress_level) 
        FROM mood_entries 
        WHERE date >= ?
    ''', (start_date,))
    avg_mood, avg_stress = cursor.fetchone()
    conn.close()
    
    if avg_mood is None:
        print("\n📭 Нет данных")
        return
    
    print(f"\n📊 Среднее настроение: {avg_mood:.1f}/10")
    print(f"📊 Средний уровень стресса: {avg_stress:.1f}/10")

def generate_insights():
    """Персональные инсайты: сравнение с тегами"""
    tag = input("Введите тег для анализа (например 'отдых'): ").strip().lower()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT mood_score, tags FROM mood_entries WHERE tags != ''")
    entries = cursor.fetchall()
    conn.close()
    
    with_tag = []
    without_tag = []
    
    for mood, tags_str in entries:
        if tag in tags_str.lower():
            with_tag.append(mood)
        else:
            without_tag.append(mood)
    
    if not with_tag:
        print(f"\n📭 Нет записей с тегом '{tag}'")
        return
    
    avg_with = sum(with_tag) / len(with_tag)
    avg_without = sum(without_tag) / len(without_tag) if without_tag else 0
    diff = avg_with - avg_without
    
    print(f"\n💡 ИНСАЙТ:")
    print(f"   Дни с тегом '{tag}': среднее настроение {avg_with:.1f}")
    print(f"   Дни без тега '{tag}': среднее настроение {avg_without:.1f}")
    
    if diff > 0:
        print(f"   ➕ Тег '{tag}' повышает настроение на {diff:.1f} балла")
    elif diff < 0:
        print(f"   ➖ Тег '{tag}' понижает настроение на {abs(diff):.1f} балла")
    else:
        print(f"   ➖ Тег '{tag}' не влияет на настроение")

# ------------------------- Экспорт/импорт -------------------------
def export_to_csv():
    """Экспорт в CSV"""
    filename = f"mood_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT date, mood_score, stress_level, sleep_quality, tags FROM mood_entries")
    entries = cursor.fetchall()
    conn.close()
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["дата", "настроение", "стресс", "сон", "теги"])
        writer.writerows(entries)
    
    print(f"✅ Экспортировано в {filename}")
    logging.info(f"Экспорт CSV: {filename}")

def export_to_zip():
    """Экспорт всех данных в ZIP-архив"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"mood_export_{timestamp}.zip"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mood_entries")
    entries = cursor.fetchall()
    conn.close()
    
    # Подготовка для JSON
    entries_list = []
    for entry in entries:
        entries_list.append({
            "date": entry[0],
            "mood_score": entry[1],
            "stress_level": entry[2],
            "sleep_quality": entry[3],
            "events": entry[4],
            "tags": entry[5],
            "quote": entry[6]
        })
    
    with zipfile.ZipFile(zip_name, 'w') as zipf:
        # JSON
        zipf.writestr("mood_entries.json", json.dumps(entries_list, ensure_ascii=False, indent=2))
        # CSV
        csv_content = "date,mood_score,stress_level,sleep_quality,tags\n"
        for e in entries:
            csv_content += f"{e[0]},{e[1]},{e[2]},{e[3]},{e[5]}\n"
        zipf.writestr("mood_entries.csv", csv_content)
        # База данных
        zipf.write(DB_PATH, "backup.sqlite")
    
    print(f"✅ Экспортировано в {zip_name}")
    logging.info(f"Экспорт ZIP: {zip_name}")

def backup_db():
    """Создание резервной копии БД"""
    Path("backups").mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backups/backup_{timestamp}.sqlite"
    shutil.copy2(DB_PATH, backup_name)
    print(f"✅ Резервная копия: {backup_name}")
    logging.info(f"Backup: {backup_name}")

# ------------------------- Главное меню -------------------------
def main_menu():
    while True:
        print("\n" + "="*50)
        print("         MOOD LOG")
        print("="*50)
        print("1.  Добавить/редактировать запись")
        print("2.  Просмотреть записи")
        print("3.  График настроения")
        print("4.  Распределение тегов")
        print("5.  Среднее настроение и стресс")
        print("6.  Инсайты по тегу")
        print("7.  Аналитика высшего порядка (filter/map/lambda)")
        print("8.  Экспорт в CSV")
        print("9.  Экспорт в ZIP")
        print("10. Резервное копирование")
        print("0.  Выход")
        print("-"*50)
        
        choice = input("Ваш выбор: ").strip()
        
        if choice == "1":
            create_or_edit_entry()
        elif choice == "2":
            view_entries()
        elif choice == "3":
            show_mood_chart()
        elif choice == "4":
            show_tag_distribution()
        elif choice == "5":
            get_average_stats()
        elif choice == "6":
            generate_insights()
        elif choice == "7":
            add_analytics_menu()
        elif choice == "8":
            export_to_csv()
        elif choice == "9":
            export_to_zip()
        elif choice == "10":
            backup_db()
        elif choice == "0":
            print("\nДо свидания! Хорошего дня! 🌟")
            logging.info("Приложение завершено")
            break
        else:
            print("Неверный ввод")
# ------------------------- Запуск -------------------------
# ------------------------- Функции высшего порядка, filter, lambda, замыкание -------------------------

def get_good_days():
    """Использует filter и lambda для отбора дней с настроением >= 8"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT date, mood_score, tags FROM mood_entries")
    entries = cursor.fetchall()
    conn.close()
    
    # Преобразуем в список словарей для удобства
    entries_dict = [{"date": e[0], "mood_score": e[1], "tags": e[2]} for e in entries]
    
    # Функциональный стиль: filter с lambda
    good_days = list(filter(lambda e: e['mood_score'] >= 8, entries_dict))
    
    if not good_days:
        print("\n📭 Нет дней с настроением 8+")
        return
    
    print("\n--- ХОРОШИЕ ДНИ (настроение ≥ 8) ---")
    for day in good_days:
        print(f"{day['date']}: настроение {day['mood_score']} | теги: {day['tags']}")

def show_mood_distribution():
    """Использует map для извлечения оценок настроения и sorted для сортировки"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT mood_score FROM mood_entries")
    entries = cursor.fetchall()
    conn.close()
    
    if not entries:
        print("\n📭 Нет данных")
        return
    
    # map для извлечения первого элемента кортежа
    mood_scores = list(map(lambda x: x[0], entries))
    
    # sorted для сортировки
    sorted_scores = sorted(mood_scores, reverse=True)
    
    print("\n--- РАСПРЕДЕЛЕНИЕ НАСТРОЕНИЯ (все записи) ---")
    for score in range(10, 0, -1):
        count = mood_scores.count(score)
        if count > 0:
            bar = "█" * count
            print(f"{score:2}: {bar} ({count} раз)")

# Замыкание: фабрика функций фильтрации по уровню стресса
def create_stress_filter(threshold: int):
    """Возвращает функцию-предикат для фильтрации записей по уровню стресса"""
    def stress_filter(entry):
        return entry[2] >= threshold  # entry[2] = stress_level
    return stress_filter

def filter_by_stress():
    """Демонстрирует использование замыкания create_stress_filter"""
    try:
        threshold = int(input("Минимальный уровень стресса для фильтра (1-10): "))
        if threshold < 1 or threshold > 10:
            threshold = 5
    except ValueError:
        threshold = 5
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT date, mood_score, stress_level, tags FROM mood_entries")
    entries = cursor.fetchall()
    conn.close()
    
    # Используем замыкание
    stress_filter = create_stress_filter(threshold)
    filtered = list(filter(stress_filter, entries))
    
    if not filtered:
        print(f"\n📭 Нет записей со стрессом >= {threshold}")
        return
    
    print(f"\n--- ЗАПИСИ СО СТРЕССОМ >= {threshold} ---")
    for e in filtered:
        print(f"{e[0]}: настроение {e[1]}, стресс {e[2]}, теги: {e[3]}")

def tag_impact_analysis():
    """Анализирует влияние тега на настроение (с использованием lambda)"""
    tag = input("Введите тег для анализа: ").strip().lower()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT mood_score, tags FROM mood_entries WHERE tags != ''")
    entries = cursor.fetchall()
    conn.close()
    
    if not entries:
        print("\n📭 Нет данных с тегами")
        return
    
    # Функциональный стиль: filter с lambda для отбора записей с тегом
    with_tag = list(filter(lambda e: tag in e[1].lower(), entries))
    without_tag = list(filter(lambda e: tag not in e[1].lower(), entries))
    
    if not with_tag:
        print(f"\n📭 Нет записей с тегом '{tag}'")
        return
    
    # map для извлечения оценок настроения
    mood_with = list(map(lambda x: x[0], with_tag))
    mood_without = list(map(lambda x: x[0], without_tag)) if without_tag else [5]
    
    avg_with = sum(mood_with) / len(mood_with)
    avg_without = sum(mood_without) / len(mood_without)
    diff = avg_with - avg_without
    
    print(f"\n📊 АНАЛИЗ ВЛИЯНИЯ ТЕГА '{tag}':")
    print(f"   Дней с тегом: {len(mood_with)}, среднее настроение: {avg_with:.1f}")
    print(f"   Дней без тега: {len(mood_without)}, среднее настроение: {avg_without:.1f}")
    
    if diff > 1:
        print(f"   ✅ Тег '{tag}' ПОВЫШАЕТ настроение на {diff:.1f} балла")
    elif diff < -1:
        print(f"   ⚠️ Тег '{tag}' ПОНИЖАЕТ настроение на {abs(diff):.1f} балла")
    else:
        print(f"   ➖ Тег '{tag}' незначительно влияет на настроение")

def add_analytics_menu():
    """Добавляем новые пункты в меню (временно, потом обновим главное меню полностью)"""
    print("\n--- ДОПОЛНИТЕЛЬНАЯ АНАЛИТИКА ---")
    print("1. Хорошие дни (настроение ≥ 8)")
    print("2. Распределение настроения (все оценки)")
    print("3. Фильтр по уровню стресса")
    print("4. Анализ влияния тега")
    print("0. Назад")
    
    choice = input("Выбор: ").strip()
    if choice == "1":
        get_good_days()
    elif choice == "2":
        show_mood_distribution()
    elif choice == "3":
        filter_by_stress()
    elif choice == "4":
        tag_impact_analysis()
if __name__ == "__main__":
    init_db()
    main_menu()