# AutoMarket Korea — backend (FastAPI)

Серверная часть каталога автомобилей. Это первый этап: API запускается и проверяется
локально. Android-приложение (APK) пока не подключается.

## Что умеет

- `GET /health` — состояние сервера и базы данных.
- `GET /cars` — каталог: пагинация, поиск, фильтры, сортировка, проверка параметров.
- `GET /cars/{id}` — подробности: фото, история цены, источник, даты проверки.
- `GET /sources` — источники и их честный статус.
- `POST /admin/sources/{key}/import` — запуск импорта (нужен ключ администратора).
- Командная строка: `python -m app.cli ...` (создать базу, показать источники, запустить импорт).

## Чего пока нет (и об этом честно сказано в API)

- **Нет подключённых реальных источников.** Пока не заданы `LOCAL_FEED_PATH` или
  `LICENSED_FEED_URL`, `/sources` показывает `not_configured`, а каталог пуст.
  Никакой «синхронизации» без источника не происходит.
- **Нет парсинга (скрапинга) сайтов.** Только файлы и API, на использование которых у вас
  есть права. Лицензию и условия провайдера вы проверяете сами.
- Файл `data/sample_listings.json` содержит **выдуманные тестовые записи** (в названии
  пометка `[ТЕСТ]`). Он нужен только чтобы проверить, что импорт работает.
- Миграции базы (Alembic) не подключены: таблицы создаются автоматически при запуске.
  Перед боевым запуском на PostgreSQL их стоит добавить.
- Импорт из API рассчитан на формат из раздела ниже. Постраничную загрузку у провайдера
  и другой формат полей нужно делать отдельным адаптером.

## Требования

- Windows 10, PowerShell.
- Python 3.11 или новее (у вас 3.13 из Microsoft Store).
- Интернет нужен только для установки пакетов и для страницы `/docs` (Swagger).

## Установка (один раз)

    cd "C:\Dev\AutoMarketKorea\backend"
    & "$env:LOCALAPPDATA\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\python.exe" -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    Copy-Item .env.example .env

Активировать окружение не нужно: везде используется `.\.venv\Scripts\python.exe`.

Ключ администратора (случайная строка) создаётся так, затем вставьте её в `.env`
в строку `ADMIN_API_KEY=`:

    $b = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); ([BitConverter]::ToString($b) -replace '-','').ToLower()
    notepad .env

Файл `.env` не публикуйте и не отправляйте в чат: он в `.gitignore`.

## Тесты

    cd "C:\Dev\AutoMarketKorea\backend"
    .\.venv\Scripts\python.exe -m pytest

Тесты используют базу в памяти и подменяют сеть, интернет и реальные источники не нужны.

## Запуск сервера

    cd "C:\Dev\AutoMarketKorea\backend"
    .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload

Откройте в браузере `http://127.0.0.1:8000/docs`: там можно нажимать «Try it out»
у каждого эндпоинта. Остановка сервера: `Ctrl+C`.

Быстрая проверка из PowerShell:

    Invoke-RestMethod http://127.0.0.1:8000/health

Если русский текст в ответах PowerShell выглядит искажённым, это особенность вывода
Windows PowerShell 5.1, а не ошибка API. Смотрите ответы в браузере на `/docs`.

## Проверка импорта на тестовом файле

1. В `.env` укажите `LOCAL_FEED_PATH=data/sample_listings.json`
2. Остановите сервер и запустите заново (или выполните команду ниже, сервер можно не останавливать,
   но тогда перезапустите его, чтобы статус источника обновился).
3. Запустите импорт:

       .\.venv\Scripts\python.exe -m app.cli import local_file

   Ожидаемый результат: создано 4, некорректных 1 (одна запись намеренно с ошибкой).
4. Откройте `http://127.0.0.1:8000/cars` и `http://127.0.0.1:8000/sources`.

Тот же импорт можно запустить через API (заголовок `X-Admin-Key` со значением из `.env`):

    Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/admin/sources/local_file/import -Headers @{ "X-Admin-Key" = "ВАШ_КЛЮЧ" }

Другие команды:

    .\.venv\Scripts\python.exe -m app.cli sources
    .\.venv\Scripts\python.exe -m app.cli import --all

## Формат данных источника

JSON-файл или ответ API:

    {
      "items": [
        {
          "external_id": "ABC-123",
          "brand": "Hyundai",
          "model": "Sonata",
          "year": 2020,
          "price_krw": 18500000,
          "mileage_km": 45000,
          "fuel_type": "gasoline",
          "transmission": "automatic",
          "photos": ["https://example.com/1.jpg"],
          "listing_url": "https://example.com/listing/ABC-123",
          "status": "active"
        }
      ]
    }

Обязательны `external_id`, `brand`, `model`, `year`. Остальное необязательно.
Допустимые `fuel_type`: gasoline, diesel, lpg, hybrid, plug_in_hybrid, electric, hydrogen, other.
Допустимые `status`: active, sold, removed, unknown.
Некорректные записи пропускаются и считаются в поле `invalid`, остальные импортируются.
Повторный импорт обновляет записи по паре (источник, `external_id`), а изменение цены
сохраняется в истории цен.

## Параметры GET /cars

| Параметр | Значение |
|---|---|
| page, page_size | страница с 1, размер 1-100 (по умолчанию 20) |
| q | поиск по названию, марке, модели, комплектации (до 5 слов, все должны совпасть) |
| brand, model | точное совпадение без учёта регистра |
| fuel_type, transmission | значения из списков выше |
| status | active (по умолчанию), sold, removed, unknown, all |
| source | ключ источника, например local_file |
| year_min, year_max | 1980-2100 |
| price_min, price_max | цена в вонах |
| mileage_min, mileage_max | пробег в км |
| sort | newest, price_asc, price_desc, year_asc, year_desc, mileage_asc, mileage_desc, checked_desc |

Неверное значение даёт ответ 422 с описанием. Минимум больше максимума тоже даёт 422.

## Как подключить настоящий источник

1. Получите право на данные (договор или лицензию) и документацию API.
2. Если API отдаёт данные в формате выше: задайте в `.env` `LICENSED_FEED_URL`
   (только https), `LICENSED_FEED_API_KEY` и при необходимости
   `LICENSED_FEED_AUTH_HEADER` / `LICENSED_FEED_AUTH_SCHEME`. Ключ хранится только на сервере.
   Передавайте ключ в заголовке, а не в адресе: адреса попадают в журнал.
3. Если формат другой: создайте файл в `app/importers/` с классом-наследником
   `BaseImporter` (по образцу `http_feed.py`), который приводит ответ провайдера к формату
   выше, и добавьте его в `app/importers/registry.py`.

При сбоях сети импортёр делает до `HTTP_MAX_ATTEMPTS` попыток с растущей паузой (только для
обрывов, таймаутов и кодов 408/425/429/5xx). Если источник так и не ответил, статус
становится `unavailable`, а уже загруженные автомобили остаются в каталоге нетронутыми.

## PostgreSQL (когда понадобится)

    .\.venv\Scripts\python.exe -m pip install -r requirements-postgres.txt

В `.env` замените `DATABASE_URL` на адрес из панели провайдера (Neon, Supabase и т. п.).
Адреса `postgres://` и `postgresql://` переводятся в нужный формат автоматически.
Бесплатные тарифы меняются: проверяйте лимиты на странице провайдера и делайте
резервные копии.

## Безопасность

- Секреты (ключ администратора, ключ API провайдера) живут только в `.env` на сервере.
  В клиентский JavaScript и в приложение их класть нельзя.
- Файл `.env` в `.gitignore`.
- Админ-эндпоинт выключен, пока не задан `ADMIN_API_KEY`.
- Внешние адреса источников принимаются только по https (для localhost разрешён http).
- Журнал пишется в `logs/automarket.log`, адреса в нём без параметров запроса.

## Если что-то не работает

- `ModuleNotFoundError`: вы запустили не `.\.venv\Scripts\python.exe` или не выполнили установку.
- Порт 8000 занят: добавьте `--port 8001` к команде запуска.
- `/sources` показывает `not_configured`: это нормально, пока источник не настроен.
  Сообщение в поле `status_message` говорит, чего не хватает.
- Ошибка чтения `.env`: сохраните файл в кодировке UTF-8.