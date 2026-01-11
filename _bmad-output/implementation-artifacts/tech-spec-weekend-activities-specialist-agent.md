---
title: 'Специалист по развлечениям - агент для поиска и предложения активностей'
slug: 'weekend-activities-specialist-agent'
created: '2026-01-11'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
depends_on: ['tech-spec-memory-family-facts-isolation.md']
tech_stack: ['Agno Agent', 'Agno Toolkits (Web Scraping)', 'Python 3.11+', 'SQLite', 'DeepSeek API', 'python-telegram-bot>=20.0', 'Pydantic>=2.0.0', 'SQLAlchemy>=2.0.0']
files_to_modify: ['main.py', 'core_logic/schemas.py', 'core_logic/__init__.py', 'db/models.py', 'core_logic/memory_utils.py']
files_to_create: ['agents/weekend_activities_specialist.py', 'core_logic/activity_filtering.py', 'core_logic/activity_parsing.py', 'core_logic/activity_storage.py', 'run_weekend_specialist.py']
files_to_modify_later: ['telegram_bot.py']  # После создания роутера
code_patterns: ['Agno Agent', 'Agno Toolkits', 'Memory integration', 'Activity filtering', 'ContextVar for telegram_id', 'Pydantic models', 'Agent factory pattern', 'Family ID isolation']
test_patterns: ['pytest', 'AsyncMock', 'Agent creation tests', 'Source parsing tests', 'Filtering tests', 'Memory integration tests', 'Mock fixtures']
---

# Tech-Spec: Специалист по развлечениям - агент для поиска и предложения активностей

**Created:** 2026-01-11

## Dependencies

**⚠️ ВАЖНО: Эта спека зависит от выполнения `tech-spec-memory-family-facts-isolation.md`**

Перед началом работы над этой спеку необходимо реализовать:

1. **Memory инфраструктура** (`tech-spec-memory-family-facts-isolation.md`):
   - Файл `core_logic/memory_utils.py` с функциями:
     - `get_family_id(telegram_id, partner_telegram_id)` - вычисление `family_id`
     - `get_user_and_family_info(db_file, telegram_id)` - получение информации о пользователе и семье
   - Интеграция Agno Automatic Memory (`enable_user_memories=True`) в агента
   - Передача `user_id` и `team_id` в `agent.arun()`

2. **Используемые функции из Memory спеки**:
   - `get_user_and_family_info()` - для получения `family_id` при сохранении активностей
   - `agent.get_user_memories()` - для получения предпочтений из Memory (через `get_user_preferences_from_memory()`)

## Overview

### Key Requirement: Создание отдельного агента

**⚠️ КРИТИЧЕСКИ ВАЖНО: Эта спека требует создания отдельного специализированного агента `WeekendActivitiesSpecialist`.**

Это не расширение существующего агента, а создание нового агента с:
- Отдельным файлом: `agents/weekend_activities_specialist.py`
- Отдельными инструкциями и tools
- Отдельной функцией создания: `create_weekend_activities_specialist_agent(db_file) -> Agent`
- Интеграцией в `main.py` для создания при запуске приложения

Агент будет работать параллельно с существующим `Family Planner` агентом и готов к использованию роутером в будущем.

### Problem Statement

Пользователи хотят получать персонализированные предложения активностей на выходные, но текущий бот не умеет искать и фильтровать активности. 

**Требуется создать отдельного специализированного агента** `WeekendActivitiesSpecialist`, который будет:

1. **Сохраняет интересные события** - когда пользователь форвардит сообщение из Telegram канала или отправляет URL/текст, агент определяет по смыслу, что это интересное событие, парсит и сохраняет информацию об активности
2. **Предлагает сохраненные активности** - по запросу "достань сохраненки" или "надо придумать планы на выходные" агент ищет в сохраненных активностях на указанную дату
3. **Фильтрует по предпочтениям** - учитывает интересы семьи, возраст детей, локацию, бюджет из Memory
4. **Интегрируется с роутером** - готов к работе в мультиагентной архитектуре, где роутер будет передавать запросы

Текущий бот умеет только создавать события из естественного языка, но не предлагает варианты активностей и не использует внешние источники.

### Solution

**Создать отдельного специализированного агента** "Специалист по развлечениям" (`WeekendActivitiesSpecialist`) с упрощенной архитектурой:

1. **Отдельный агент `WeekendActivitiesSpecialist`** - новый агент в файле `agents/weekend_activities_specialist.py` с:
   - Собственными инструкциями (`SPECIALIST_INSTRUCTIONS`)
   - Собственными tools (`parse_forwarded_activity`, `get_saved_activities`)
   - Собственной моделью и настройками (DeepSeek, `enable_user_memories=True`)
   - Создается через функцию `create_weekend_activities_specialist_agent(db_file)` в `main.py`
2. **Обработка форвардов и URL** - когда пользователь форвардит сообщение из Telegram или отправляет URL/текст, агент использует LLM для определения по смыслу, что это интересное событие, парсит сообщение/URL через Web Scraping toolkit (Firecrawl) и сохраняет в БД
3. **Кеш сохраненных активностей** - таблица `parsed_activities` в БД для хранения спарсенных активностей (лимит 100 активностей на семью)
4. **Два сценария работы**:
   - Пользователь форвардит/отправляет URL → агент определяет по смыслу интересное событие → парсим и сохраняем в БД
   - Пользователь просит планы → ищем в сохраненных активностях на указанную дату, фильтруем по предпочтениям из Memory
5. **Фильтрация по Memory** - использование предпочтений из Memory (интересы, возраст детей, локация, бюджет) для фильтрации активностей. Если Memory пуста, агент спрашивает предпочтения у пользователя
6. **Форматирование предложений** - структурированный ответ с до 3 активностей, каждое с коротким описанием

### Scope

**In Scope:**

- **Создание отдельного агента `WeekendActivitiesSpecialist`**:
  - Новый файл `agents/weekend_activities_specialist.py` с функцией `create_weekend_activities_specialist_agent(db_file) -> Agent`
  - Агент с собственными инструкциями, tools и настройками
  - Интеграция в `main.py` - создание агента при запуске приложения
  - Готовность к использованию роутером в будущем
- Таблица `parsed_activities` в БД для кеширования спарсенных активностей из форвардов (лимит 100 активностей на семью, проверка дубликатов по `source_url` + `family_id`)
- Обработка форвардов сообщений и URL - агент использует LLM для определения по смыслу, что это интересное событие (не требуется точное совпадение текста "интересное событие")
- Парсинг одного сообщения/URL - извлечение информации об активности (название, дата, цена, локация, описание, фото) через Web Scraping toolkit Firecrawl (рекомендуемый)
- Валидация URL перед парсингом (проверка формата URL)
- Timeout 60 секунд для операций парсинга URL
- Функции фильтрации активностей по предпочтениям из Memory (интересы, возраст детей, локация, бюджет) - случайный порядок применения фильтров
- Интеграция с Memory для получения предпочтений семьи - если Memory пуста, агент спрашивает предпочтения у пользователя
- Структурированный формат ответа агента (до 3 активностей с полями: название, дата/время, цена, локация, описание, фото)
- Два инструмента для агента:
  - `parse_forwarded_activity()` - парсинг форварда/URL и сохранение в БД (с проверкой дубликатов и валидацией `family_id`)
  - `get_saved_activities()` - получение сохраненных активностей на указанную дату (с лимитом 100 на семью)
- Инструкции агенту для работы с двумя сценариями:
  - Обработка форвардов/URL - агент определяет по смыслу, что это интересное событие, использует `parse_forwarded_activity()`
  - Поиск в сохраненных активностях - использует `get_saved_activities()` с фильтрацией по предпочтениям из Memory
- Поддержка запросов от роутера (через `agent.arun()` с параметрами)

**Out of Scope:**

- Роутер для маршрутизации запросов (отдельная спеку)
- Интеграция с Telegram ботом на первом этапе (тестирование через AgentOS, интеграция будет после создания роутера)
- Автоматическое определение сложности событий (пока не определено, оставить для будущего)
- Автоматические предложения по расписанию (только по запросу на первом этапе)
- Создание событий в календаре (специалист только предлагает, планировщик создает)
- Массовый парсинг Telegram каналов и Instagram аккаунтов (на будущее)
- Поиск в Яндекс.Афише (убрано, оставлены только форварды и веб-ссылки)
- Agno Workflows для парсинга (упрощенная архитектура без workflow)
- Джоба по расписанию для обновления кеша (на будущее)
- Парсинг вложенных страниц (только прямая страница по URL, без перехода по ссылкам)

## Context for Development

### Codebase Patterns

**Текущие паттерны:**

- **Agno Agent**: Используется `Agent` из `agno.agent` с `DeepSeek` моделью. Агенты создаются через функции `create_*_agent()` в `main.py`, создаются один раз и переиспользуются (не в циклах).
- **Database**: SQLite через `SqliteDb` из `agno.db.sqlite`, также используется для хранения истории диалогов. SQLAlchemy ORM модели в `db/models.py`.
- **User Model**: Таблица `users` с полями `telegram_id`, `partner_telegram_id`, `name`. SQLAlchemy модель `User` в `db/models.py`, Pydantic модель в `core_logic/schemas.py`.
- **Context Variables**: Используется `ContextVar` для передачи `telegram_id` в tools (`agents_wrappers.py`). Паттерн: `_set_current_telegram_id()` перед вызовом tool, `_reset_current_telegram_id()` после.
- **Telegram Bot**: Async обработчики через `python-telegram-bot>=20.0`. Используется `agent.arun()` с параметрами `user_id` и `session_id` для изоляции.
- **Session Management**: Используется `session_versions` в `bot_data` для изоляции диалогов. Формат `session_id`: `f"telegram_{telegram_id}_v{version}"`.
- **Agent Run**: `agent.arun()` с параметрами `user_id` и `session_id` для изоляции. Async метод для работы в async контексте Telegram бота.
- **Memory Integration**: Используется Agno Automatic Memory (`enable_user_memories=True`) для сбора фактов о семье. Memory хранится в той же БД, что и история диалогов (таблица `agno_memories` создается автоматически Agno).
- **Tools Pattern**: Все tools оборачиваются в `agents_wrappers.py` для строгой валидации входных данных (ISO форматы для дат/времени). Tools принимают только валидные форматы, возвращают понятные ошибки.
- **Pydantic Models**: Используется `BaseModel` с `Field` для валидации данных. Модели в `core_logic/schemas.py` для бизнес-логики, SQLAlchemy модели в `db/models.py` для БД.
- **Testing**: Используется pytest с `AsyncMock` для async функций. Фикстуры для моков (`mock_update`, `mock_context`, `mock_agent`). Тесты в директории `tests/`.

**Новые паттерны:**

- **Отдельный специализированный агент**: Создание `WeekendActivitiesSpecialist` как отдельного агента с собственными инструкциями. Следует паттерну `create_*_agent()` из `main.py`. Агент создается один раз и переиспользуется.
- **Agno Toolkits Integration**: Использование готовых toolkits из Agno. Web Scraping toolkit **Firecrawl** (рекомендуемый) для парсинга URL. Импорт: `from agno.tools.firecrawl import FirecrawlTools`. Добавление в `tools=[]` при создании агента.
- **Forwarded Message Handling**: Обработка форвардов сообщений и URL. Агент использует LLM для определения по смыслу, что это интересное событие (не требуется точное совпадение текста "интересное событие").
- **Single Message/URL Parsing**: Парсинг одного сообщения или URL для извлечения информации об активности. Использование Firecrawl для парсинга URL (timeout 60 секунд, без парсинга вложенных страниц), извлечение текста из форварда для парсинга. Валидация URL перед парсингом.
- **Activity Cache**: Таблица `parsed_activities` в БД для хранения спарсенных активностей из форвардов. Поля: `id`, `title`, `datetime`, `price`, `location`, `description`, `photo_url`, `source_url`, `source_type`, `parsed_at`, `family_id` (для изоляции между семьями). Лимит 100 активностей на семью. Проверка дубликатов по `source_url` + `family_id` (уникальный индекс).
- **Activity Filtering**: Фильтрация активностей по предпочтениям из Memory перед предложением пользователю. Использование функций из `core_logic/activity_filtering.py` для фильтрации по интересам, возрасту детей, локации, бюджету.
- **Structured Activity Format**: Структурированный формат данных для активностей (Pydantic модель `Activity` в `core_logic/schemas.py`). Модель используется для валидации данных при парсинге и фильтрации.
- **Three Scenarios**: Три сценария работы агента:
  1. Форвард сообщения/URL → парсим и сохраняем
  2. Запрос поиска → идем в Яндекс.Афишу
  3. Запрос планов → сначала ищем в сохраненных, если нет → предлагаем поиск в Яндекс.Афише

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `main.py` | Создание основного агента через функцию `create_family_planner_agent()`. Паттерн: функция возвращает `Agent`, агент создается один раз и переиспользуется. Нужно добавить функцию `create_weekend_activities_specialist_agent()` для создания специалиста по развлечениям. Используется `DeepSeek` модель, `SqliteDb` для истории диалогов. |
| `agents_wrappers.py` | Обертки инструментов. Паттерн использования `ContextVar` для передачи `telegram_id` в tools. Все tools оборачиваются для строгой валидации входных данных (ISO форматы для дат/времени). |
| `core_logic/database.py` | Работа с БД через SQLAlchemy репозитории. Используется `get_user_by_telegram_id()` для получения информации о пользователе. |
| `core_logic/memory_utils.py` | Функции для работы с Memory (будет создана в `tech-spec-memory-family-facts-isolation.md`). Используется `get_user_and_family_info()` для получения информации о семье и `family_id`. Нужно добавить функцию `get_user_preferences_from_memory()` для извлечения предпочтений (интересы, возраст детей, локация, бюджет) из Memory. |
| `core_logic/schemas.py` | Pydantic модели для валидации данных. Используется `BaseModel` с `Field` для валидации. Нужно добавить модель `Activity` для структурирования данных об активностях с полями: `title`, `datetime`, `price`, `location`, `description`, `photo_url`, `source_url`, `source_type`. |
| `core_logic/__init__.py` | Экспорт функций из `core_logic`. Нужно добавить экспорт новых функций из `activity_filtering.py` и `activity_parsing.py`. |
| `db/models.py` | SQLAlchemy ORM модели. Используется `Base = declarative_base()`. Таблицы: `users`, `events`, `event_participants`. Нужно добавить таблицу `parsed_activities` для кеширования спарсенных активностей. |
| `telegram_bot.py` | Обработка сообщений Telegram. Используется `agent.arun()` с параметрами `user_id` и `session_id`. Паттерн: `ContextVar` для передачи `telegram_id` в tools через `_set_current_telegram_id()`. Нужно добавить обработку форвардов сообщений - определение форварда через `update.message.forward_from` или `update.message.forward_from_chat`. |
| `tests/test_telegram_bot.py` | Тесты бота. Используется pytest с `AsyncMock` для async функций, фикстуры для моков (`mock_update`, `mock_context`, `mock_agent`). |

### Technical Decisions

1. **Отдельный агент vs модуль**: Выбран отдельный агент для лучшей изоляции логики и готовности к мультиагентной архитектуре с роутером.

2. **Agno Toolkits vs собственные парсеры**: Использование готового Agno Toolkit **Firecrawl** (рекомендуемый Web Scraping toolkit) для парсинга URL вместо написания собственных парсеров. Это ускоряет разработку и использует проверенные решения.

3. **Activity Cache в БД**: Спарсенные активности из форвардов сохраняются в таблицу `parsed_activities` в БД. Таблица содержит поля: `id`, `title`, `datetime`, `price`, `location`, `description`, `photo_url`, `source_url`, `source_type`, `parsed_at`, `family_id`. `family_id` используется для изоляции активностей между семьями. Это позволяет быстро получать сохраненные активности без повторного парсинга.

4. **Memory Integration**: Использование уже реализованной Memory из `tech-spec-memory-family-facts-isolation.md` для получения предпочтений семьи (интересы, возраст детей, локация, бюджет). Агент получает предпочтения через функцию `get_user_preferences_from_memory()` (которая использует `agent.get_user_memories()`) перед фильтрацией. **Зависимость**: Memory спека должна быть реализована перед этой спеку.

5. **Activity Format**: Структурированный формат данных для активностей (Pydantic модель `Activity`) с полями: `title`, `datetime`, `price`, `location`, `description`, `photo_url`, `source_url`, `source_type`. Сложность пока не включена (оставить для будущего).

6. **Filtering Logic**: Фильтрация активностей по предпочтениям из Memory (случайный порядок применения фильтров):
   - По интересам (матчинг ключевых слов в описании/названии)
   - По возрасту детей (если указан возраст в активности, проверять соответствие)
   - По локации (матчинг локации активности с предпочтениями)
   - По бюджету (если указана цена, проверять соответствие бюджету)
   - Если Memory пуста, агент спрашивает предпочтения у пользователя перед фильтрацией

7. **Response Format**: Агент возвращает до 3 активностей с коротким описанием (1-2 предложения). Формат ответа структурированный для удобства обработки роутером.

8. **Router Integration**: Агент готов к работе с роутером - принимает запросы через `agent.arun()` с параметрами `user_id` и `team_id` для получения предпочтений из Memory.

9. **Two Scenarios Logic**: Агент должен уметь работать в двух сценариях:
   - **Сценарий 1 - Форвард/URL**: Когда пользователь форвардит сообщение из Telegram или отправляет URL/текст, агент использует LLM для определения по смыслу, что это интересное событие. Затем парсит сообщение/URL и сохраняет в БД (с проверкой дубликатов и валидацией `family_id`). Ответ: "Сохранил событие: [название]" или сообщение об ошибке при неудаче
   - **Сценарий 2 - Планы**: Когда пользователь просит "достань сохраненки" или "надо придумать планы на выходные", агент ищет в сохраненных активностях (`parsed_activities`) на указанную дату, фильтрует по предпочтениям из Memory (если Memory пуста, спрашивает предпочтения). Ответ: до 3 активностей с коротким описанием

## Implementation Plan

### Tasks

- [ ] Task 1: Создать Pydantic модель `Activity` для структурирования данных об активностях
  - File: `core_logic/schemas.py`
  - Action: Добавить класс `Activity(BaseModel)` с полями:
    - `title: str` - название активности
    - `datetime: Optional[datetime]` - дата и время (опционально, если не указано)
    - `price: Optional[int]` - цена в рублях (опционально)
    - `location: Optional[str]` - локация (опционально)
    - `description: Optional[str]` - описание активности
    - `photo_url: Optional[str]` - URL фото (опционально)
    - `source_url: str` - URL источника (обязательно)
    - `source_type: str` - тип источника ('telegram_forward', 'url')
  - Notes: Использовать `Field` для валидации. `datetime` должен быть `Optional[datetime]` так как не все активности имеют конкретную дату. `source_url` и `source_type` обязательны для отслеживания источника.

- [ ] Task 2: Создать SQLAlchemy модель `ParsedActivity` для таблицы в БД
  - File: `db/models.py`
  - Action: Добавить класс `ParsedActivity(Base)` с полями:
    - `id: Integer` - первичный ключ
    - `title: String` - название активности
    - `datetime: String` (ISO формат) - дата и время (опционально)
    - `price: Integer` - цена в рублях (опционально)
    - `location: String` - локация (опционально)
    - `description: String` - описание активности (опционально)
    - `photo_url: String` - URL фото (опционально)
    - `source_url: String` - URL источника (обязательно)
    - `source_type: String` - тип источника ('telegram_forward', 'url')
    - `parsed_at: DateTime` - время парсинга (default: текущее время)
    - `family_id: String` - ID семьи для изоляции (обязательно)
  - Notes: Использовать тот же паттерн, что и для других моделей в `db/models.py`. Добавить индекс на `family_id` и `datetime` для быстрого поиска. Добавить **уникальный индекс на `(source_url, family_id)`** для предотвращения дубликатов. Использовать `ISOStringDateTime` для поля `datetime` если нужно совместимость с существующим паттерном.

- [ ] Task 3: Создать функцию парсинга одного сообщения/URL
  - File: `core_logic/activity_parsing.py` (новый файл)
  - Action: Создать функцию `parse_single_activity(message_text: Optional[str], url: Optional[str], agent: Agent) -> Optional[Activity]` которая:
    1. Если передан `url`, валидирует формат URL (использовать `urllib.parse` или regex), затем использует Firecrawl toolkit для парсинга URL с timeout 60 секунд (без парсинга вложенных страниц)
    2. Если передан `message_text`, извлекает информацию из текста (название, дата, цена, локация, описание) через LLM или простой парсинг
    3. Преобразует в объект `Activity`
    4. Обрабатывает ошибки (логирует с уровнем ERROR и возвращает None с понятным сообщением об ошибке)
  - Notes: Использовать **Firecrawl** toolkit из Agno (`from agno.tools.firecrawl import FirecrawlTools`) для парсинга URL. Для текста использовать LLM для извлечения структурированных данных или простой парсинг. Функция должна быть гибкой - работать и с текстом, и с URL. Timeout 60 секунд для операций парсинга.


- [ ] Task 4: Создать функции работы с таблицей `parsed_activities` в БД
  - File: `core_logic/activity_storage.py` (новый файл)
  - Action: Создать функции:
    - `save_parsed_activity(db_file: str, activity: Activity, family_id: str) -> int` - сохранение активности в БД, возвращает ID. Перед сохранением:
      1. Валидировать `family_id` (не пустой, правильный формат `family_{id}` или `family_{id1}_{id2}`)
      2. Проверить дубликаты по `source_url` + `family_id` (если существует, вернуть существующий ID или обновить запись)
      3. Проверить лимит 100 активностей на семью (если превышен, удалить самую старую по `parsed_at`)
    - `get_saved_activities(db_file: str, family_id: str, target_date: Optional[date] = None) -> List[Activity]` - получение сохраненных активностей для семьи, опционально фильтр по дате. Ограничение: максимум 100 активностей на семью
    - `delete_parsed_activity(db_file: str, activity_id: int, family_id: str) -> bool` - удаление активности (только для своей семьи, с проверкой `family_id`)
  - Notes: Использовать SQLAlchemy репозиторий паттерн (как в `db/repositories.py`). Функции должны проверять `family_id` для изоляции между семьями. Использовать `get_user_and_family_info()` из `memory_utils.py` (реализована в `tech-spec-memory-family-facts-isolation.md`) для получения `family_id`. Добавить уникальный индекс на `(source_url, family_id)` для предотвращения дубликатов.

- [ ] Task 5: Создать функции фильтрации активностей по предпочтениям
  - File: `core_logic/activity_filtering.py` (новый файл)
  - Action: Создать функции фильтрации:
    - `filter_by_interests(activities: List[Activity], interests: List[str]) -> List[Activity]` - фильтрация по интересам (матчинг ключевых слов в названии/описании)
    - `filter_by_children_age(activities: List[Activity], children_ages: List[int]) -> List[Activity]` - фильтрация по возрасту детей (если указан возраст в активности)
    - `filter_by_location(activities: List[Activity], preferred_location: Optional[str]) -> List[Activity]` - фильтрация по локации (матчинг локации)
    - `filter_by_budget(activities: List[Activity], max_budget: Optional[int]) -> List[Activity]` - фильтрация по бюджету (если указана цена)
    - `filter_activities(activities: List[Activity], preferences: dict) -> List[Activity]` - основная функция, применяющая все фильтры в случайном порядке
  - Notes: Все фильтры опциональные - если параметр не указан, не применять фильтр. Функция `filter_activities` принимает словарь `preferences` с ключами: `interests`, `children_ages`, `location`, `budget`. Применять фильтры в случайном порядке (использовать `random.shuffle()` для списка фильтров перед применением).

- [ ] Task 6: Создать функцию получения предпочтений из Memory
  - File: `core_logic/memory_utils.py` (файл будет создан в `tech-spec-memory-family-facts-isolation.md`, добавить функцию)
  - Action: Создать функцию `get_user_preferences_from_memory(agent: Agent, user_id: str, team_id: Optional[str]) -> dict` которая:
    1. Получает персональные memories через `agent.get_user_memories(user_id=user_id)`
    2. Получает семейные memories через `agent.get_user_memories(team_id=team_id)` (если `team_id` указан)
    3. Извлекает из memories: интересы, возраст детей, локацию, бюджет
    4. Возвращает словарь `{"interests": [...], "children_ages": [...], "location": "...", "budget": ...}`
    5. Если memories пусты или не найдены предпочтения, возвращает пустой словарь `{}` (агент должен спросить предпочтения у пользователя)
  - Notes: **Зависимость**: Файл `core_logic/memory_utils.py` должен быть создан в `tech-spec-memory-family-facts-isolation.md` перед выполнением этой задачи. Использовать простой парсинг текста memories для извлечения информации. На первом этапе можно использовать ключевые слова. Обрабатывать ошибки (логировать и возвращать пустой словарь). Если возвращается пустой словарь, агент должен спросить предпочтения у пользователя.

- [ ] Task 7: Создать инструмент `parse_forwarded_activity` для агента
  - File: `agents/weekend_activities_specialist.py` (новый файл)
  - Action: Создать функцию `parse_forwarded_activity(message_text: str, url: Optional[str] = None) -> dict` которая:
    1. Валидирует URL (если передан) через `urllib.parse` или regex перед парсингом
    2. Парсит сообщение/URL через `parse_single_activity()` (timeout 60 секунд)
    3. Получает `family_id` через `get_user_and_family_info()` и валидирует его (не пустой, правильный формат)
    4. Сохраняет активность в БД через `save_parsed_activity()` (с проверкой дубликатов и лимита)
    5. Возвращает словарь с результатом: `{"success": bool, "activity_id": Optional[int], "message": str}`. При ошибке: `{"success": false, "activity_id": None, "message": "Не удалось сохранить событие. Попробуйте позже."}`
  - Notes: Функция должна быть обернута для использования в качестве tool агента (с валидацией входных данных). Использовать `ContextVar` для получения `telegram_id`. Обрабатывать ошибки и возвращать понятные сообщения об ошибках пользователю. Логировать все операции с уровнем INFO/ERROR.


- [ ] Task 8: Создать инструмент `get_saved_activities` для агента
  - File: `agents/weekend_activities_specialist.py`
  - Action: Создать функцию `get_saved_activities(target_date: Optional[str] = None) -> List[Activity]` которая:
    1. Получает `family_id` через `get_user_and_family_info()` и валидирует его
    2. Если `target_date` указан, валидирует формат (ISO 'YYYY-MM-DD') и конвертирует в `date` объект. При ошибке парсинга возвращает пустой список с сообщением об ошибке
    3. Получает сохраненные активности через `get_saved_activities()` из БД (лимит 100 на семью)
    4. Получает предпочтения из Memory через `get_user_preferences_from_memory()`. Если Memory пуста, агент должен спросить предпочтения у пользователя перед фильтрацией
    5. Фильтрует по предпочтениям из Memory через `filter_activities()` (случайный порядок фильтров)
    6. Возвращает до 3 активностей (первые 3 из отфильтрованного списка)
  - Notes: Функция должна быть обернута для использования в качестве tool агента. `target_date` опциональный - если не указан, возвращать все сохраненные активности (до лимита 100). Использовать `ContextVar` для получения `telegram_id`. Обрабатывать ошибки и возвращать понятные сообщения.

- [ ] Task 9: Создать агента `WeekendActivitiesSpecialist`
  - File: `agents/weekend_activities_specialist.py`
  - Action: Создать функцию `create_weekend_activities_specialist_agent(db_file: str) -> Agent` которая:
    1. Импортирует необходимые toolkits: **Firecrawl** (`from agno.tools.firecrawl import FirecrawlTools`)
    2. Создает агента с `DeepSeek` моделью (как в `create_family_planner_agent()`)
    3. Добавляет Firecrawl toolkit в `tools=[]` (для парсинга URL)
    4. Добавляет кастомные tools в `tools=[]`: `parse_forwarded_activity`, `get_saved_activities`
    5. Настраивает `enable_user_memories=True` для работы с Memory
    6. Добавляет инструкции для агента (см. Task 10)
    7. Возвращает агента
  - Notes: Следовать паттерну `create_family_planner_agent()` из `main.py`. Использовать ту же БД (`db_file`) для истории диалогов и Memory. Агент создается один раз и переиспользуется. Использовать async версии где возможно для лучшей производительности.

- [ ] Task 10: Добавить инструкции для агента `WeekendActivitiesSpecialist`
  - File: `agents/weekend_activities_specialist.py`
  - Action: Создать константы с инструкциями:
    - `SPECIALIST_DESCRIPTION` - описание роли агента
    - `SPECIALIST_INSTRUCTIONS` - список инструкций:
      - **Сценарий 1 - Форвард/URL**: Если пользователь форвардит сообщение или отправляет URL/текст, используй LLM для определения по смыслу, что это интересное событие (не требуется точное совпадение текста "интересное событие"). Если это интересное событие, используй `parse_forwarded_activity()` для парсинга и сохранения. Ответ: "Сохранил событие: [название]" или сообщение об ошибке при неудаче
      - **Сценарий 2 - Планы**: Если пользователь просит "достань сохраненки" или "надо придумать планы на выходные", используй `get_saved_activities()` для поиска в сохраненных активностях на указанную дату. Если предпочтения из Memory пусты, спроси у пользователя его интересы, возраст детей, локацию и бюджет перед фильтрацией. Ответ: до 3 активностей с коротким описанием
      - Предлагать до 3 активностей с коротким описанием (1-2 предложения)
      - Формат ответа: список активностей с названием, датой/временем, ценой, локацией, коротким описанием
      - Не создавать события в календаре - только предлагать активности
      - При ошибках парсинга или сохранения возвращать понятное сообщение: "Не удалось сохранить событие. Попробуйте позже."
  - Notes: Инструкции должны быть четкими и понятными для LLM. Добавить примеры формата ответа для каждого сценария. Подчеркнуть, что агент должен использовать LLM для определения по смыслу, что это интересное событие.

- [ ] Task 11: ~~Добавить обработку форвардов в `telegram_bot.py`~~ (отложено до интеграции с роутером)
  - File: `telegram_bot.py` (будет реализовано после создания роутера)
  - Action: После создания роутера в мультиагентной системе:
    1. Проверить, является ли сообщение форвардом: `update.message.forward_from` или `update.message.forward_from_chat`
    2. Проверить текст сообщения на наличие "интересное событие" (регистронезависимо)
    3. Если оба условия выполнены, извлечь текст форварда и URL (если есть)
    4. Передать в роутер, который направит запрос к агенту специалиста через `agent.arun()` с контекстом о форварде
    5. Агент должен вызвать `parse_forwarded_activity()` для парсинга и сохранения
  - Notes: **На первом этапе**: Обработка форвардов будет тестироваться через agentOS с симуляцией форвардов. Интеграция с Telegram ботом произойдет после создания роутера. Обработка форвардов должна быть прозрачной для пользователя - агент сам определяет, что это форвард с "интересным событием" и обрабатывает его.

- [ ] Task 12: Добавить создание агента в `main.py`
  - File: `main.py`
  - Action: В функции `main()`:
    1. Импортировать `create_weekend_activities_specialist_agent` из `agents.weekend_activities_specialist`
    2. Создать агента специалиста через `create_weekend_activities_specialist_agent(db_file)`
    3. Сохранить агента в переменную (пока не используется, но будет нужен для роутера)
  - Notes: Агент создается один раз при запуске приложения. Пока не используется в `telegram_bot.py`, но будет использоваться роутером в будущем.

- [ ] Task 13: Обновить инициализацию БД для создания таблицы `parsed_activities`
  - File: `core_logic/database.py` или `db/models.py`
  - Action: Добавить создание таблицы `parsed_activities` при инициализации БД:
    1. Использовать SQLAlchemy `Base.metadata.create_all()` для создания таблицы
    2. Добавить уникальный индекс на `(source_url, family_id)` для предотвращения дубликатов
    3. Добавить индекс на `family_id` и `datetime` для быстрого поиска
  - Notes: Таблица создается автоматически при первом запуске, как и другие таблицы. Использовать тот же паттерн, что и для других таблиц. Уникальный индекс на `(source_url, family_id)` предотвращает дубликаты.

- [ ] Task 14: Экспортировать новые функции через `__init__.py`
  - File: `core_logic/__init__.py`
  - Action: Добавить экспорт:
    - `Activity` из `schemas.py`
    - `get_user_preferences_from_memory` из `memory_utils.py`
    - `parse_single_activity` из `activity_parsing.py`
    - `filter_activities` из `activity_filtering.py`
    - `save_parsed_activity`, `get_saved_activities` из `activity_storage.py`
  - Notes: Сохранить обратную совместимость с существующими экспортами.

- [ ] Task 15: Создать скрипт `run_weekend_specialist.py` для запуска агента через AgentOS
  - File: `run_weekend_specialist.py` (новый файл)
  - Action: Создать скрипт для запуска агента `WeekendActivitiesSpecialist` через AgentOS по инструкции https://docs.agno.com/agent-os/creating-your-first-os:
    1. Импортировать `create_weekend_activities_specialist_agent` из `agents.weekend_activities_specialist`
    2. Импортировать `AgentOS` из `agno.os` и `AsyncSqliteDb` из `agno.db.sqlite`
    3. Импортировать `DB_FILE` из `core_logic.calendar_tools` или использовать env var
    4. Создать агента через `create_weekend_activities_specialist_agent(db_file)` (использовать async БД если возможно)
    5. Создать `AgentOS` с агентом: `AgentOS(id="weekend-specialist", description="Weekend Activities Specialist Agent", agents=[agent])`
    6. Получить FastAPI app через `agent_os.get_app()`
    7. Запустить через `agent_os.serve(app="run_weekend_specialist:app", reload=True)` на порту 7777
  - Notes: Скрипт предназначен для тестирования агента через AgentOS Control Plane. Пользователь сам подключит к control plane и будет общаться через UI чат. Использовать async версии где возможно (`AsyncSqliteDb`). Следовать паттерну из документации Agno.

### Acceptance Criteria

**AC1: Activity Model Creation**
- Given: Модель `Activity` создана в `core_logic/schemas.py`
- When: Создается объект `Activity` с валидными данными
- Then: Объект успешно создается и валидируется через Pydantic

**AC2: ParsedActivity Model Creation**
- Given: Модель `ParsedActivity` создана в `db/models.py`
- When: Создается объект `ParsedActivity` с валидными данными
- Then: Объект успешно создается и сохраняется в БД

**AC3: Parse Single Activity from Message**
- Given: Текст сообщения содержит информацию об активности (название, дата, цена, локация)
- When: Вызывается `parse_single_activity(message_text=text, url=None, agent)`
- Then: Возвращается объект `Activity` с извлеченными данными

**AC4: Parse Single Activity from URL**
- Given: URL на страницу с информацией об активности
- When: Вызывается `parse_single_activity(message_text=None, url=url, agent)`
- Then: Возвращается объект `Activity` с данными, спарсенными из URL

**AC5: Save Parsed Activity to DB**
- Given: Объект `Activity` и `family_id`
- When: Вызывается `save_parsed_activity(db_file, activity, family_id)`
- Then: Активность сохраняется в таблицу `parsed_activities` с правильным `family_id` и возвращается ID

**AC6: Filter Activities by Interests**
- Given: Список активностей и интересы `["театр", "дети"]`
- When: Вызывается `filter_by_interests(activities, interests)`
- Then: Возвращаются только активности, содержащие ключевые слова "театр" или "дети" в названии/описании

**AC7: Filter Activities by Budget**
- Given: Список активностей и максимальный бюджет `5000`
- When: Вызывается `filter_by_budget(activities, max_budget)`
- Then: Возвращаются только активности с ценой <= 5000 или без указанной цены

**AC8: Get User Preferences from Memory**
- Given: В Memory сохранено "Интересы: театр, рестораны. Возраст детей: 3, 5. Локация: Москва. Бюджет: 5000"
- When: Вызывается `get_user_preferences_from_memory(agent, user_id, team_id)`
- Then: Возвращается словарь `{"interests": ["театр", "рестораны"], "children_ages": [3, 5], "location": "Москва", "budget": 5000}`

**AC9: Get Saved Activities**
- Given: В БД сохранены активности для семьи с `family_id` и датой `2026-01-15`
- When: Вызывается `get_saved_activities(target_date="2026-01-15")`
- Then: Возвращаются только активности для этой семьи на указанную дату (до лимита 100 на семью)

**AC10: Parse Forwarded Activity Tool**
- Given: Пользователь форвардит сообщение или отправляет URL с интересным событием
- When: Агент определяет по смыслу, что это интересное событие, и вызывается `parse_forwarded_activity(message_text=text, url=None)`
- Then: Активность парсится, проверяется на дубликаты, сохраняется в БД и возвращается `{"success": true, "activity_id": 1, "message": "Сохранил событие: [название]"}`. При ошибке: `{"success": false, "activity_id": None, "message": "Не удалось сохранить событие. Попробуйте позже."}`

**AC11: Validate Family ID**
- Given: Функция `save_parsed_activity()` вызывается с некорректным `family_id` (пустой или неправильный формат)
- When: Вызывается `save_parsed_activity(db_file, activity, family_id="")`
- Then: Функция возвращает ошибку валидации без сохранения в БД

**AC12: Check Duplicates**
- Given: Активность с `source_url="https://example.com/event"` и `family_id="family_123"` уже существует в БД
- When: Вызывается `save_parsed_activity()` с той же комбинацией
- Then: Функция возвращает существующий ID или обновляет запись, не создавая дубликат

**AC13: Limit 100 Activities per Family**
- Given: В БД уже 100 активностей для семьи с `family_id="family_123"`
- When: Вызывается `save_parsed_activity()` для новой активности этой семьи
- Then: Самая старая активность (по `parsed_at`) удаляется, новая сохраняется

**AC14: Validate URL Format**
- Given: Передан некорректный URL `"not-a-url"`
- When: Вызывается `parse_single_activity(url="not-a-url", message_text=None, agent)`
- Then: Функция возвращает None с логированием ошибки валидации

**AC15: Timeout for URL Parsing**
- Given: URL указывает на медленный сайт (ответ > 60 секунд)
- When: Вызывается `parse_single_activity(url=slow_url, message_text=None, agent)`
- Then: Функция возвращает None после timeout 60 секунд с логированием ошибки

**AC16: Empty Memory Handling**
- Given: Memory пуста (нет предпочтений)
- When: Вызывается `get_saved_activities()` и затем `get_user_preferences_from_memory()`
- Then: Агент спрашивает у пользователя его интересы, возраст детей, локацию и бюджет перед фильтрацией

**AC17: Agent Creation**
- Given: Функция `create_weekend_activities_specialist_agent(db_file)` создана
- When: Вызывается функция с валидным `db_file`
- Then: Возвращается объект `Agent` с правильными tools (`parse_forwarded_activity`, `get_saved_activities`) и Firecrawl toolkit

**AC18: Scenario 1 - Forwarded Activity**
- Given: Пользователь форвардит сообщение или отправляет URL с интересным событием
- When: Агент обрабатывает запрос
- Then: Агент использует LLM для определения по смыслу, что это интересное событие, вызывает `parse_forwarded_activity()` и отвечает: "Сохранил событие: [название]" или сообщение об ошибке

**AC19: Scenario 2 - Get Plans**
- Given: Пользователь просит "достань сохраненки на 15 января"
- When: Агент обрабатывает запрос
- Then: Агент вызывает `get_saved_activities(target_date="2026-01-15")`, фильтрует по предпочтениям из Memory (если Memory пуста, спрашивает предпочтения), возвращает до 3 активностей с коротким описанием

**AC20: Agent Response Format**
- Given: Агент получил предложения активностей
- When: Агент формирует ответ пользователю
- Then: Ответ содержит до 3 активностей, каждое с названием, датой/временем, ценой, локацией, коротким описанием (1-2 предложения)

## Additional Context

### Dependencies

- **Agno Framework**: Требуется версия с поддержкой Web Scraping toolkits. Проверить совместимость с текущей версией Agno (в `requirements.txt` указано `agno>=0.1.0`).
- **Agno Toolkits**: 
  - **Firecrawl** - рекомендуемый Web Scraping toolkit для парсинга URL. Импорт: `from agno.tools.firecrawl import FirecrawlTools`. Проверить документацию Agno для настройки API ключа Firecrawl (если требуется).
- **Memory Integration**: Использование уже реализованной Memory из `tech-spec-memory-family-facts-isolation.md`. **Зависимость**: Эта спека зависит от выполнения Memory спеки. Memory будет реализована в той же БД, что и история диалогов. Используется для получения предпочтений семьи (интересы, возраст детей, локация, бюджет) через функцию `get_user_preferences_from_memory()` и для получения `family_id` через `get_user_and_family_info()`.
- **Existing Database**: Та же БД, что используется для хранения событий и истории диалогов (`data/family_calendar.db` по умолчанию, настраивается через `DB_FILE` env var). Добавляется новая таблица `parsed_activities` для кеширования спарсенных активностей.
- **Python Dependencies**: Все зависимости уже в `requirements.txt`: `agno>=0.1.0`, `pydantic>=2.0.0`, `sqlalchemy>=2.0.0`, `python-telegram-bot>=20.0`. Возможно, потребуется добавить зависимости для выбранных Web Scraping toolkits.
- **AgentOS**: Используется для тестирования агента на первом этапе. Скрипт `run_weekend_specialist.py` запускает агента через AgentOS по инструкции https://docs.agno.com/agent-os/creating-your-first-os. Пользователь сам подключит к Control Plane и будет общаться через UI чат.
- **Telegram Bot API**: Будет использоваться после создания роутера для обработки форвардов сообщений через `update.message.forward_from` и `update.message.forward_from_chat`.

### Testing Strategy

1. **Unit Tests**:
   - Тесты для парсинга одного сообщения/URL (`parse_single_activity`) - включая валидацию URL, timeout 60 секунд
   - Тесты для сохранения и получения активностей из БД (`save_parsed_activity`, `get_saved_activities`) - включая проверку дубликатов, лимита 100, валидацию `family_id`
   - Тесты для фильтрации активностей по предпочтениям (`filter_activities`) - включая случайный порядок фильтров
   - Тесты для получения предпочтений из Memory (`get_user_preferences_from_memory`) - включая обработку пустой Memory

2. **Integration Tests**:
   - Тесты для создания агента с правильными tools (`parse_forwarded_activity`, `get_saved_activities`) и Firecrawl toolkit
   - Тесты для работы агента с форвардами/URL (моки) - включая определение по смыслу через LLM
   - Тесты для работы агента с сохраненными активностями
   - Тесты для интеграции с Memory (получение предпочтений, обработка пустой Memory)
   - Тесты для двух сценариев работы агента
   - Тесты для формата ответа агента (структурированный, до 3 активностей)
   - Тесты для обработки ошибок (валидация URL, timeout, дубликаты, лимит)

3. **Manual Testing через AgentOS**:
   - **Основной способ тестирования на первом этапе**: Использование `run_weekend_specialist.py` для запуска агента через AgentOS
   - Подключение к AgentOS Control Plane через UI и общение через чат
   - Интерактивное тестирование двух сценариев работы агента:
     - Тестирование парсинга форвардов/URL (агент определяет по смыслу интересное событие)
     - Тестирование получения сохраненных активностей ("достань сохраненки на [дата]")
   - Проверка работы с Memory (передача `user_id` и `team_id` для тестирования изоляции)
   - Проверка фильтрации по предпочтениям из Memory (включая случайный порядок фильтров)
   - Проверка обработки пустой Memory (агент спрашивает предпочтения)
   - Проверка формата ответа агента (до 3 активностей с коротким описанием)
   - Проверка обработки ошибок (некорректный URL, timeout, дубликаты, лимит)

4. **Интеграция с Telegram ботом** (после создания роутера):
   - Интеграция агента в Telegram бота через роутер
   - Тестирование обработки форвардов в реальном Telegram боте
   - Тестирование всех сценариев через Telegram интерфейс

### Notes

- **Сложность событий**: Пока не определена, оставить для будущего. Можно добавить поле `complexity` в модель `Activity` позже.
- **Router Integration**: Агент готов к работе с роутером, но сам роутер будет реализован в отдельной спеку.
- **Simplified Architecture**: Упрощенная архитектура без Workflows и джоб по расписанию. Все операции выполняются по запросу пользователя. Это упрощает разработку и отладку на первом этапе.
- **Testing через AgentOS**: На первом этапе агент будет тестироваться через AgentOS с помощью отдельного скрипта `run_weekend_specialist.py` по инструкции https://docs.agno.com/agent-os/creating-your-first-os. Пользователь сам подключит к Control Plane и будет общаться через UI чат. Интеграция с Telegram ботом произойдет после создания роутера в мультиагентной системе.
- **Forwarded Messages**: Обработка форвардов будет реализована в `telegram_bot.py` после интеграции с роутером. На первом этапе тестирование через AgentOS. Агент использует LLM для определения по смыслу, что это интересное событие (не требуется точное совпадение текста).
- **URL Parsing**: Парсинг только прямой страницы по URL через Firecrawl, без парсинга вложенных страниц. Timeout 60 секунд. Валидация URL перед парсингом.
- **Activity Cache**: Сохраненные активности хранятся в БД с изоляцией по `family_id`. Лимит 100 активностей на семью (при превышении удаляется самая старая). Уникальный индекс на `(source_url, family_id)` предотвращает дубликаты. Это позволяет быстро получать сохраненные активности без повторного парсинга.
- **Performance**: Парсинг URL может быть медленным. Timeout 60 секунд для операций парсинга. Логирование всех операций с уровнем INFO/ERROR для отладки.
- **Error Handling**: Обработка ошибок при парсинге сообщений/URL - возвращать понятные сообщения пользователю ("Не удалось сохранить событие. Попробуйте позже.") и логировать ошибки с уровнем ERROR. Валидация URL и `family_id` перед операциями.
