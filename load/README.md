# Нагрузочное испытание (ДЗ 2)

Инструменты: k6 (нагрузка), psutil и `docker stats` (ресурсы), py-spy (профиль), matplotlib (графики).
Порог испытания записан в тесте (`tests/options.js`): p95 времени ответа < 500 мс и доля ошибок < 1 %.

## Подготовка (один раз)

1. Установить k6: установщик `.msi` со страницы https://github.com/grafana/k6/releases (или `winget install k6`).
   Проверка: `k6 version`. После установки терминал нужно открыть заново.
2. Из корня проекта, с активным `.venv`:

   ```powershell
   pip install -r load/requirements.txt
   pip install py-spy
   ```

## Запуск сервиса и базы

Сервис запускается **без `--reload`**, на порту 8080, в отдельном терминале:

```powershell
docker compose up -d
python seed.py work                    # рабочий объём данных
python -m uvicorn app.main:app --port 8080
```

Все остальные команды выполняются во втором терминале, из корня проекта.
Учётная запись для нагрузки задаётся в `load/config.js` (можно переопределить: `-e APP_USER=... -e APP_PASSWORD=...`).

## Структура каталога

| Путь | Назначение |
|---|---|
| `config.js` | профиль операций (веса, сумма 100), лимиты, объёмы данных |
| `flows/` | вход и подготовка данных (`setup()`) |
| `scenarios/` | операции, смешанный сценарий, тяжёлая операция |
| `validators/` | проверки ответов (`check`) |
| `tests/` | `smoke`, `mixed`, `heavy` - сценарии для `k6 run` |
| `run_steps.py` | прогон ступеней одной командой + ресурсы |
| `resources.py` | сбор CPU/памяти/соединений раз в секунду |
| `plot.py` | графики p95 и ресурсов |
| `profile.py`, `hot.py` | py-spy под нагрузкой и таблица горячих функций |

## Порядок испытания

1. Проверка сценария (все проверки должны быть зелёными):

   ```powershell
   k6 run load/tests/smoke.test.js
   ```
2. Смешанный профиль, ступени по 30 секунд, остановка на первой ступени, не выдержавшей порог:

   ```powershell
   python -m load.run_steps mixed --rates 8,32,64,128,160,192 --duration 30
   python -m load.plot mixed
   ```
3. Тяжёлая операция отдельно (по умолчанию `list_middle_page`, другая - `--heavy list_overdue`):

   ```powershell
   python -m load.run_steps heavy --rates 2,8,32,64,128 --duration 30
   python -m load.plot heavy
   ```
4. Профиль на частоте предела тяжёлой операции (`--rate` - запросов/с, `--duration` - секунд, не меньше 15):

   ```powershell
   python -m load.profile --rate 32 --duration 40
   ```
5. Опыт с настройкой: перезапустить сервис с четырьмя рабочими процессами
   (`python -m uvicorn app.main:app --port 8080 --workers 4`), повторить ступени 32, 64, 96 тяжёлой операции,
   затем вернуть запуск без `--workers`.

Перед каждой ступенью база наполняется заново (`seed.py work`), после чего скрипт ждёт, пока загрузка процессора вернётся к простою.
Контейнер базы определяется автоматически (`docker compose ps -q db`). Полезные ключи: `--merge` (добавить ступени
к уже сохранённым), `--idle-cpu` (порог «простоя», %), `--no-docker`, `--db-container ID`, `--k6 путь\к\k6.exe`.

## Результаты

`load/results/<сценарий>/`: `rate_<N>.txt` (вывод k6), `rate_<N>.json`, `rate_<N>_resources.csv`,
`steps.md` (таблица ступеней), `steps.json`, графики `*.png`.
`load/results/profile/`: `flamegraph.svg`, `profile.raw`, `hot.md`.
CPU в таблицах - в процентах **одного** ядра (200 % = два ядра заняты полностью).
w
