// Параметры нагрузочного теста. Всё, что меняется от запуска к запуску,
// задаётся ключами k6:  k6 run -e RATE=8 -e DURATION=30s load/tests/mixed.test.js

const env = (name, fallback) =>
  __ENV[name] !== undefined && __ENV[name] !== "" ? __ENV[name] : fallback;

// Адрес сервиса и учётная запись (под ней же сняты замеры первого задания)
export const BASE = env("BASE", "http://localhost:8080");
export const USER = env("APP_USER", "demo");
export const PASSWORD = env("APP_PASSWORD", "demo");

// Ступень: частота в запросах в секунду и длительность
export const RATE = parseFloat(env("RATE", "2"));
export const DURATION = env("DURATION", "30s");

// Порог испытания (подраздел 2.1 методички): p95 < 500 мс и ошибок < 1 %
export const LIMIT_MS = parseInt(env("LIMIT_MS", "500"), 10);
export const MAX_ERROR_RATE = 0.01;

// Объём рабочего наполнения: диапазоны номеров для запросов (seed.py work)
export const READERS = parseInt(env("READERS", "3000"), 10);
export const COPIES = parseInt(env("COPIES", "30000"), 10);
export const PAGE_SIZE = 20; // как в замерах первого задания (bench/run.py)

// Самая тяжёлая операция по замерам первого задания (таблица 5 отчёта)
export const HEAVY = env("HEAVY", "list_middle_page");

// Профиль нагрузки: операции контракта (кроме входа) и их вес, сумма 100.
// Названия совпадают со строками таблицы замеров первого задания.
export const PROFILE = [
  { name: "list_first_page", weight: 25 },  // основной экран библиотекаря, открывается после каждого действия
  { name: "list_middle_page", weight: 5 },  // листание истории выдач, до середины доходят редко
  { name: "list_overdue", weight: 15 },     // ежедневный обзор должников
  { name: "list_by_reader", weight: 10 },   // справка по читателю на стойке выдачи
  { name: "loan_card", weight: 20 },        // проверка выдачи перед возвратом и выдачей
  { name: "issue", weight: 10 },            // основная операция читального зала
  { name: "return", weight: 10 },           // пара к выдаче: книга возвращается после чтения
  { name: "summary", weight: 5 },           // смотрит заведующий несколько раз в день
];

const total = PROFILE.reduce((sum, op) => sum + op.weight, 0);
if (total !== 100) {
  throw new Error(`Сумма весов профиля должна быть 100, сейчас ${total}`);
}
