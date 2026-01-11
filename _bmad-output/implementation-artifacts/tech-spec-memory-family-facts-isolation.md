---
title: 'Memory для сбора фактов о семье с изоляцией между семьями'
slug: 'memory-family-facts-isolation'
created: '2026-01-11'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Agno Memory', 'Python 3.11+', 'SQLite', 'DeepSeek API', 'python-telegram-bot>=20.0']
files_to_modify: ['main.py', 'telegram_bot.py', 'core_logic/__init__.py']
files_to_create: ['core_logic/memory_utils.py']
code_patterns: ['Agno Automatic Memory', 'Family ID computation', 'Memory type detection', 'Debug messages', 'Memory usage in planning', 'ContextVar for telegram_id']
test_patterns: ['pytest', 'Memory retrieval tests', 'Family ID computation tests', 'Memory isolation tests', 'Memory usage in conflict checking tests']
---

# Tech-Spec: Memory для сбора фактов о семье с изоляцией между семьями

**Created:** 2026-01-11

## Overview

### Problem Statement

Текущий бот не запоминает факты о семье (рабочие часы, распорядок детей, предпочтения) и не использует их при планировании. Нет изоляции данных между семьями — все пользователи видят общий календарь, но memories должны быть изолированы. При планировании событий агент не учитывает сохраненные факты, особенно при проверке конфликтов (например, не учитывает рабочие часы или время сна детей).

Нужна базовая инфраструктура Memory с понятием семьи и изоляцией для:
1. Автоматического сбора фактов о семье из диалога
2. Использования сохраненных фактов при планировании событий
3. Изоляции memories между разными семьями

### Solution

Интегрировать Agno Automatic Memory (`enable_user_memories=True`) с поддержкой персональной (`user_id`) и семейной (`team_id` = `family_id`) памяти:

1. **Интеграция Agno Automatic Memory** для автоматического сбора фактов:
   - Персональная память (`user_id` = `telegram_id`) - рабочие часы, личные предпочтения
   - Семейная память (`team_id` = `family_id`) - распорядок детей, регулярные события, общие предпочтения
   - `family_id` вычисляется на лету из `partner_telegram_id`

2. **Изоляция между семьями** - каждая семья имеет уникальный `family_id`, memories изолированы

3. **Использование Memory при планировании** - агент использует сохраненные memories при создании событий и проверке конфликтов (учет рабочих часов, распорядка детей)

4. **Отладочные сообщения** - показывать, в какую память сохраняется информация (персональная/семейная) для отладки

### Scope

**In Scope:**

- Интеграция Agno Automatic Memory (`enable_user_memories=True`) в существующего агента
- Функция вычисления `family_id` на лету из `partner_telegram_id`
- Функция получения информации о пользователе и семье
- Инструкции агенту для определения типа памяти (персональная vs семейная)
- Отладочные сообщения о сохранении в память (отдельной строкой)
- Передача `user_id` и `team_id` в `agent.arun()`
- Использование Memory при планировании событий (чтение memories при создании событий)
- Использование Memory при проверке конфликтов (учет рабочих часов, распорядка детей)
- Изоляция memories между семьями (проверка, что `family_id` используется правильно)
- Инструкции агенту для использования Memory при планировании и проверке конфликтов

**Out of Scope:**

- Рекомендации активностей на выходные (отдельная спеку)
- Мультиагентная архитектура (отдельная спеку)
- Анализ истории календаря для автоматического определения интересов (на будущее)
- Опрос интересов при первом использовании (отдельная спеку)

## Context for Development

### Codebase Patterns

**Текущие паттерны:**

- **Agno Agent**: Используется `Agent` из `agno.agent` с `DeepSeek` моделью
- **Database**: SQLite через `SqliteDb` из `agno.db.sqlite`, также используется для хранения истории диалогов
- **User Model**: Таблица `users` с полями `telegram_id`, `partner_telegram_id`, `name`
- **Context Variables**: Используется `ContextVar` для передачи `telegram_id` в tools (`agents_wrappers.py`)
- **Telegram Bot**: Async обработчики через `python-telegram-bot>=20.0`
- **Session Management**: Используется `session_versions` в `bot_data` для изоляции диалогов
- **Agent Run**: `agent.arun()` с параметрами `user_id` и `session_id` для изоляции
- **Conflict Checking**: `check_availability()` в `core_logic/calendar_tools.py` проверяет конфликты по времени через `get_conflicting_events_global()`
- **Event Scheduling**: `schedule_event()` использует `check_availability()` перед созданием события

**Новые паттерны:**

- **Agno Automatic Memory**: `enable_user_memories=True` для автоматического сбора фактов
- **Family ID Computation**: Вычисление `family_id` на лету из `partner_telegram_id`
- **Memory Type Detection**: Определение типа памяти (персональная/семейная) на основе контекста сообщения
- **Debug Messages**: Отладочные сообщения о сохранении в память (временно для отладки)
- **Memory Usage in Planning**: Использование memories при планировании и проверке конфликтов

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `main.py` | Создание агента. Функция `create_family_planner_agent()` создает `Agent` с `db=SqliteDb()`. Нужно добавить `enable_user_memories=True`. Агент создается один раз и переиспользуется. |
| `telegram_bot.py` | Обработка сообщений. Функция `handle_message()` вызывает `agent.arun()` с `user_id=str(telegram_id)` и `session_id`. Нужно получать информацию о пользователе через `get_user_by_telegram_id()` и передавать `team_id=family_id` в `agent.arun()`. Используется `ContextVar` для передачи `telegram_id` в tools. |
| `core_logic/database.py` | Работа с БД. Функция `get_user_by_telegram_id(db_file, telegram_id)` возвращает `Optional[User]`. Модель `User` содержит `partner_telegram_id: Optional[int]`. Используется SQLAlchemy репозиторий `UserRepository`. |
| `core_logic/schemas.py` | Pydantic модели. Модель `User` содержит поля: `telegram_id`, `partner_telegram_id`, `name`. Модель `AvailabilityResult` содержит `is_available: bool` и `conflicting_events: List[CalendarEvent]`. |
| `core_logic/calendar_tools.py` | Функции календаря. `check_availability(start_time, duration_minutes)` проверяет конфликты через `get_conflicting_events_global()` - только события в БД. `schedule_event()` использует `check_availability()` перед созданием. Нужно добавить использование Memory при проверке конфликтов (учет рабочих часов, распорядка детей). |
| `agents_wrappers.py` | Обертки инструментов. Используется `ContextVar _CURRENT_TG_ID` для передачи `telegram_id` в tools. Функция `_get_current_telegram_id()` получает ID из контекста. Обертки `check_availability()` и `schedule_event()` используют этот паттерн. |
| `tests/test_database.py` | Тесты БД. Использует pytest с фикстурами для создания временной БД. |
| `tests/test_telegram_bot.py` | Тесты бота. Использует pytest с `AsyncMock` для тестирования async handlers. |

### Technical Decisions

1. **Agno Automatic Memory vs Agentic Memory**: Выбран Automatic Memory (`enable_user_memories=True`) для простоты и надежности. Агент автоматически извлекает и сохраняет факты без ручного управления.

2. **Family ID Computation**: Вычисляется на лету из `partner_telegram_id` без добавления поля в БД. Формат: `family_{min_telegram_id}_{max_telegram_id}` для обеспечения одинакового `family_id` у обоих партнеров.

3. **Memory Type Detection**: Агент определяет тип памяти на основе контекста сообщения:
   - Персональная (`user_id`): упоминания "я", "мне", "мой", рабочие часы, личные предпочтения
   - Семейная (`team_id`): упоминания "мы", "наш", "семья", распорядок детей, общие события

4. **Debug Messages**: Показывать отладочные сообщения отдельной строкой `[ОТЛАДКА: Сохранено в персональную/семейную память]` для начала, потом убрать.

5. **User ID and Team ID in Agent Run**: Передавать `user_id=str(telegram_id)` и `team_id=family_id` в `agent.arun()` (если поддерживается). Если `team_id` не поддерживается напрямую, использовать fallback: после вызова `agent.arun()` получить семейные memories через `agent.get_user_memories(team_id=family_id)` и передать их в контекст агента через `agent_input` или инструкции. Если пользователь не найден в БД, Memory не будет работать для этого пользователя.

6. **Memory Usage in Planning**: Агент должен использовать memories при планировании:
   - При создании события учитывать рабочие часы из Memory
   - При проверке конфликтов учитывать распорядок детей (например, не предлагать события во время сна)
   - Использовать `agent.get_user_memories()` для получения memories перед планированием

7. **Memory Isolation**: Каждая семья имеет уникальный `family_id`, memories изолированы через `team_id` в Agno Memory. При запросе memories фильтровать по `user_id` и `team_id`.

8. **Conflict Checking with Memory**: При проверке конфликтов учитывать не только события в календаре, но и факты из Memory (рабочие часы, время сна детей). Агент должен использовать `agent.get_user_memories()` перед вызовом `check_availability()` и учитывать эти факты при планировании. **Важно**: Агент не должен автоматически отклонять события из-за Memory - только информировать пользователя о возможном конфликте и предлагать варианты. Пользователь сам решает, как поступить. Например, если пользователь работает до 18:00 и просит создать событие на 17:00, агент должен сказать: "Учитывая, что вы работаете до 18:00, событие на 17:00 может быть неудобным. Создать событие или перенести на другое время?"

## Implementation Plan

### Tasks

- [ ] Task 1: Создать функцию вычисления `family_id`
  - File: `core_logic/memory_utils.py` (новый файл)
  - Action: Создать функцию `get_family_id(telegram_id: int, partner_telegram_id: Optional[int]) -> str` которая вычисляет `family_id` на основе `telegram_id` и `partner_telegram_id`
  - Logic: Если `partner_telegram_id` есть и не None, использовать `family_{min_id}_{max_id}` (где min и max - это минимальный и максимальный из двух telegram_id), иначе `family_{telegram_id}`
  - Notes: Функция должна быть чистой (pure function), без побочных эффектов. Использовать `min()` и `max()` для обеспечения одинакового `family_id` у обоих партнеров. Если `partner_telegram_id` равен None или 0, возвращать `family_{telegram_id}`.

- [ ] Task 2: Создать функцию получения информации о пользователе и семье
  - File: `core_logic/memory_utils.py`
  - Action: Создать функцию `get_user_and_family_info(db_file: str, telegram_id: int) -> tuple[Optional[User], Optional[str]]` которая:
    1. Получает пользователя из БД через `get_user_by_telegram_id(db_file, telegram_id)` с обработкой ошибок
    2. Если пользователь не найден, возвращает `(None, None)`
    3. Если пользователь найден, вычисляет `family_id` через `get_family_id(telegram_id, user.partner_telegram_id if user.partner_telegram_id else None)`
    4. Если у пользователя нет `partner_telegram_id`, `family_id` будет `family_{telegram_id}` (один пользователь = одна семья)
    5. Возвращает кортеж `(user, family_id)`
  - Notes: Использует `get_user_by_telegram_id()` из `core_logic.database`. Обработать исключения БД (логировать и возвращать `(None, None)`). Если пользователь найден, всегда возвращать `family_id` (даже если партнера нет - тогда `family_id = family_{telegram_id}`).

- [ ] Task 3: Включить Agno Automatic Memory в агента
  - File: `main.py`
  - Action: В функции `create_family_planner_agent()` добавить параметр `enable_user_memories=True` в создание `Agent`
  - Notes: Agno автоматически создаст таблицу `agno_memories` в БД при первом использовании. Таблица будет создана в той же БД, что указана в `SqliteDb(db_file=db_file)`.

- [ ] Task 4: Добавить инструкции агенту для определения типа памяти
  - File: `main.py`
  - Action: Добавить в `AGENT_INSTRUCTIONS` новые инструкции о памяти и конфиденциальности:
    - Если пользователь говорит о личных предпочтениях или рабочем расписании (использует "я", "мне", "мой"), сохранять как персональную память (`user_id`)
    - Если пользователь говорит о семейных фактах, детях, общих событиях (использует "мы", "наш", "семья"), сохранять как семейную память (`team_id`)
    - После сохранения показывать отладочное сообщение отдельной строкой: `[ОТЛАДКА: Сохранено в персональную память]` или `[ОТЛАДКА: Сохранено в семейную память]`
    - При планировании использовать как персональную, так и семейную память, но не раскрывать персональные данные партнера без явного разрешения
  - Notes: Инструкции должны быть четкими и понятными для LLM. Добавить примеры использования местоимений для определения типа памяти.

- [ ] Task 5: Передавать `user_id` и `team_id` при вызове агента
  - File: `telegram_bot.py`
  - Action: В функции `handle_message()` перед вызовом `agent.arun()`:
    1. Импортировать функции из `core_logic.memory_utils`: `get_user_and_family_info`
    2. Импортировать `DB_FILE` из `core_logic.calendar_tools` (уже импортирован в файле)
    3. Получить информацию о пользователе и семье через `get_user_and_family_info(DB_FILE, telegram_user_id)`
    4. Извлечь `user` и `family_id` из кортежа
    5. Если пользователь найден (`user` не None), передать `user_id=str(telegram_user_id)` и `team_id=family_id` (если `family_id` не None) в `agent.arun()`
    6. Если `agent.arun()` не поддерживает параметр `team_id`, использовать fallback: после вызова `agent.arun()` получить семейные memories через `agent.get_user_memories(team_id=family_id)` и передать их в контекст агента через инструкции
    7. Передать `user_id` и `team_id` в контекст агента через добавление в `agent_input`: `f"Сообщение пользователя: {user_message}\nКонтекст: user_id={user_id_str}, team_id={family_id}"` (или через отдельный параметр, если поддерживается)
  - Notes: Если пользователь не найден в БД, использовать только `user_id`, Memory не будет работать для этого пользователя. Проверить поддержку `team_id` в `agent.arun()` - если не поддерживается, использовать fallback через `agent.get_user_memories(team_id=family_id)` и передачу в контекст через инструкции или `agent_input`.

- [ ] Task 6: Добавить инструкции агенту для использования Memory при планировании
  - File: `main.py`
  - Action: Добавить в `AGENT_INSTRUCTIONS` инструкции о использовании Memory при планировании:
    - Перед созданием события использовать `agent.get_user_memories(user_id=user_id)` и `agent.get_user_memories(team_id=team_id)` для получения сохраненных фактов (если `user_id` и `team_id` доступны в контексте)
    - Учитывать рабочие часы из Memory при планировании (например, если пользователь работает до 18:00, не предлагать события до этого времени)
    - Учитывать распорядок детей из Memory при проверке конфликтов (например, если ребенок спит с 13:00 до 15:00, не предлагать события в это время)
    - При проверке конфликтов через `check_availability()` учитывать не только события в календаре, но и факты из Memory
    - Если обнаружен конфликт между Memory (например, рабочие часы) и запросом пользователя, подсказать пользователю о конфликте и спросить, как поступить (например: "Учитывая, что вы работаете до 18:00, событие на 17:00 может быть неудобным. Создать событие или перенести на другое время?")
    - Пользователь сам решает, как поступить при конфликтах - агент только информирует и предлагает варианты
  - Notes: Инструкции должны быть конкретными с примерами. Агент должен понимать, как извлекать информацию из memories (рабочие часы, время сна детей) и использовать её при планировании. Важно: агент не должен автоматически отклонять события из-за Memory - только информировать пользователя и предлагать варианты.

- [ ] Task 7: Экспортировать новые функции через `__init__.py`
  - File: `core_logic/__init__.py`
  - Action: Добавить экспорт функций из `memory_utils.py`:
    - `get_family_id`
    - `get_user_and_family_info`
  - Notes: Сохранить обратную совместимость с существующими экспортами. Использовать `from core_logic.memory_utils import get_family_id, get_user_and_family_info`.

### Acceptance Criteria

**AC1: Family ID Computation**
- Given: Пользователь с `telegram_id=123` и `partner_telegram_id=456`
- When: Вызывается `get_family_id(123, 456)`
- Then: Возвращается `"family_123_456"` (одинаковый для обоих партнеров, независимо от порядка вызова)

**AC2: Family ID Without Partner**
- Given: Пользователь с `telegram_id=123` и `partner_telegram_id=None`
- When: Вызывается `get_family_id(123, None)`
- Then: Возвращается `"family_123"`

**AC3: User and Family Info Retrieval**
- Given: Пользователь существует в БД с `telegram_id=123` и `partner_telegram_id=456`
- When: Вызывается `get_user_and_family_info(db_file, 123)`
- Then: Возвращается кортеж `(User(...), "family_123_456")` где User содержит правильные данные

**AC4: User Not Found**
- Given: Пользователь с `telegram_id=999` не существует в БД
- When: Вызывается `get_user_and_family_info(db_file, 999)`
- Then: Возвращается кортеж `(None, None)`

**AC5: Memory Integration**
- Given: Агент создан с `enable_user_memories=True`
- When: Пользователь говорит "Я работаю с 9 до 18"
- Then: Информация сохраняется в персональную память (`user_id`), показывается отладочное сообщение `[ОТЛАДКА: Сохранено в персональную память]` отдельной строкой

**AC6: Family Memory**
- Given: Пользователь с `partner_telegram_id` говорит "Сын спит с 13 до 15"
- When: Агент обрабатывает сообщение
- Then: Информация сохраняется в семейную память (`team_id` = `family_id`), показывается отладочное сообщение `[ОТЛАДКА: Сохранено в семейную память]` отдельной строкой

**AC7: Memory Usage in Planning**
- Given: В Memory сохранено "Пользователь работает с 9 до 18"
- When: Пользователь просит создать событие на 10:00
- Then: Агент учитывает рабочие часы из Memory, информирует пользователя о возможном конфликте и спрашивает, как поступить (создать событие или перенести)

**AC8: Memory Usage in Conflict Checking**
- Given: В Memory сохранено "Сын спит с 13:00 до 15:00"
- When: Пользователь просит создать событие на 14:00
- Then: Агент учитывает время сна из Memory, информирует пользователя о возможном конфликте и спрашивает, как поступить (создать событие или перенести)

**AC9: Memory Isolation Between Families**
- Given: Две семьи с разными `family_id` (семья A: `family_123_456`, семья B: `family_789_101`)
- When: Пользователь из семьи A запрашивает информацию о семье
- Then: Используются только memories семьи A (`team_id=family_123_456`), memories семьи B недоступны

**AC10: Team ID in Agent Run**
- Given: Пользователь с `telegram_id=123` и `partner_telegram_id=456` отправляет сообщение
- When: Вызывается `agent.arun()` в `handle_message()`
- Then: Передаются параметры `user_id="123"` и `team_id="family_123_456"` (если поддерживается), или используется fallback через `agent.get_user_memories(team_id="family_123_456")` и передача в контекст агента

**AC11: Family ID Without Partner**
- Given: Пользователь с `telegram_id=123` существует в БД, но `partner_telegram_id=None`
- When: Вызывается `get_user_and_family_info(db_file, 123)`
- Then: Возвращается кортеж `(User(...), "family_123")` где `family_id` равен `family_{telegram_id}`

**AC12: Error Handling in User Info Retrieval**
- Given: Произошла ошибка БД при получении пользователя (например, БД недоступна)
- When: Вызывается `get_user_and_family_info(db_file, 123)`
- Then: Ошибка логируется, функция возвращает `(None, None)` без исключения

## Additional Context

### Dependencies

- **Agno Framework**: Требуется версия с поддержкой `enable_user_memories` и `agent.get_user_memories()`. Проверить совместимость с текущей версией Agno.
- **Existing Database**: Таблица `users` должна содержать `partner_telegram_id` для вычисления `family_id`. Это поле уже существует в схеме БД.
- **SQLite Database**: Та же БД, что используется для хранения событий и истории диалогов, будет использоваться для хранения memories (таблица `agno_memories` создается автоматически Agno).

### Testing Strategy

1. **Unit Tests**:
   - Тесты для `get_family_id()` - различные комбинации `telegram_id` и `partner_telegram_id`:
     - С партнером (разные порядки вызова для проверки одинакового результата: `get_family_id(123, 456)` и `get_family_id(456, 123)` должны вернуть одинаковый результат)
     - Без партнера (`partner_telegram_id=None`)
     - С None значениями
     - Edge case: когда `telegram_id` больше `partner_telegram_id` и наоборот
   - Тесты для `get_user_and_family_info()` - различные сценарии:
     - Пользователь существует с партнером
     - Пользователь существует без партнера (`partner_telegram_id=None` - должен вернуть `family_{telegram_id}`)
     - Пользователь не существует
     - Обработка ошибок БД (мокировать исключение и проверить, что функция возвращает `(None, None)` без исключения)

2. **Integration Tests**:
   - Тесты для Memory интеграции - проверка сохранения и извлечения memories:
     - Сохранение персональной памяти
     - Сохранение семейной памяти
     - Извлечение memories через `agent.get_user_memories()`
   - Тесты для изоляции memories между семьями:
     - Создание memories для двух разных семей
     - Проверка, что memories одной семьи недоступны другой
   - Тесты для использования Memory при планировании:
     - Планирование с учетом рабочих часов из Memory
     - Планирование с учетом распорядка детей из Memory

3. **Manual Testing**:
   - Проверка отладочных сообщений о сохранении в память
   - Проверка использования Memory при планировании событий
   - Проверка использования Memory при проверке конфликтов
   - Проверка изоляции между семьями (создать двух пользователей с разными партнерами)

### Notes

- **Debug Messages**: Отладочные сообщения о сохранении в память будут показаны для начала, потом убраны в отдельной задаче после отладки.
- **Agno Memory API**: Нужно проверить точный API для работы с `team_id` в Agno. Возможно, потребуется использовать `agent.get_user_memories(team_id=family_id)` вместо передачи `team_id` в `agent.arun()`.
- **Memory Extraction**: Извлечение информации из Memory (рабочие часы, время сна) на первом этапе будет простым - агент будет использовать текстовый поиск в memories. В будущем можно улучшить через структурированные memories или более сложный парсинг.
- **Conflict Checking**: Использование Memory при проверке конфликтов реализуется через инструкции агенту, а не через изменение функции `check_availability()`. Агент должен сам учитывать факты из Memory перед вызовом `check_availability()`. **Важно**: Агент не должен автоматически отклонять события из-за Memory - только информировать пользователя и предлагать варианты. Пользователь сам решает, как поступить.
- **Performance**: Agno Automatic Memory автоматически управляет memories, но при большом количестве memories может потребоваться оптимизация запросов. На первом этапе это не критично.
