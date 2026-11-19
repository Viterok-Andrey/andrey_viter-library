Снято стеков: 1165

### Функции проекта по доле «total» (есть в стеке)

| Функция | Файл:строка | self, % | total, % |
|---|---|---:|---:|
| `list_loans` | app/main.py:77 | 0.2 | 67.6 |
| `connect` | app/db.py:40 | 0.1 | 51.4 |
| `list_loans` | app/repository.py:74 | 0.0 | 12.4 |
| `_run` | app/db.py:49 | 0.3 | 11.4 |
| `fetch_one` | app/db.py:68 | 0.3 | 6.0 |
| `fetch_all` | app/db.py:64 | 0.0 | 5.7 |
| `_loan_card` | app/repository.py:47 | 0.8 | 0.8 |
| `add_db_stats_headers` | app/main.py:29 | 0.0 | 0.6 |
| `verify_token` | app/auth.py:42 | 0.3 | 0.6 |
| `current_user` | app/auth.py:51 | 0.0 | 0.6 |
| `_sign` | app/auth.py:21 | 0.0 | 0.3 |

### Где стек заканчивается («self»), все модули

| Функция | Файл:строка | self, % | total, % |
|---|---|---:|---:|
| `BaseConnection._connect_gen` | psycopg/_connection_base.py:436 | 38.7 | 39.6 |
| `getaddrinfo` | socket.py:962 | 3.5 | 3.6 |
| `wait_select` | psycopg/waiting.py:254 | 3.3 | 11.3 |
| `jsonable_encoder` | fastapi/encoders.py:307 | 3.2 | 4.5 |
| `IocpProactor._poll` | asyncio/windows_events.py:825 | 3.0 | 3.4 |
| `SelectSelector._select` | selectors.py:314 | 2.8 | 2.8 |
| `BaseConnection._exec_command` | psycopg/_connection_base.py:475 | 2.1 | 2.3 |
| `Connection.close` | psycopg/connection.py:176 | 1.5 | 1.5 |
| `BaseProactorEventLoop._write_to_self` | asyncio/proactor_events.py:828 | 1.5 | 1.5 |
| `BaseCursor._maybe_prepare_gen` | psycopg/_cursor_base.py:306 | 1.2 | 4.9 |
| `BaseCursor._execute_send` | psycopg/_cursor_base.py:437 | 1.1 | 1.1 |
| `is_dataclass` | dataclasses.py:1262 | 1.0 | 1.0 |
| `_parse_conninfo` | psycopg/conninfo.py:101 | 1.0 | 1.2 |
| `dict_row.<locals>.dict_row_` | psycopg/rows.py:122 | 0.9 | 0.9 |
| `BaseCursor._select_current_result` | psycopg/_cursor_base.py:498 | 0.9 | 1.6 |
