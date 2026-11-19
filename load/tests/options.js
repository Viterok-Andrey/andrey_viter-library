// Общие настройки ступени: открытая модель, порог, пороги-счётчики по операциям.
import { RATE, DURATION, LIMIT_MS, MAX_ERROR_RATE, PROFILE } from "../config.js";

export function stepOptions() {
  // Открытая модель: k6 подаёт запросы с заданной частотой, не дожидаясь ответов.
  // Частота < 1 в секунду задаётся так же: rate за timeUnit в 10 с.
  const thresholds = {
    // Порог испытания: только запросы нагрузки, вход и подготовка не входят
    "http_req_duration{kind:load}": [`p(95)<${LIMIT_MS}`],
    "http_req_failed{kind:load}": [`rate<${MAX_ERROR_RATE}`],
  };
  // Условие max>=0 всегда верно: пороги нужны только для того, чтобы k6
  // выдал отдельные числа по каждой операции (какая именно уходит за порог).
  for (const op of PROFILE) {
    thresholds[`http_req_duration{operation:${op.name}}`] = ["max>=0"];
  }
  return {
    scenarios: {
      step: {
        executor: "constant-arrival-rate",
        rate: Math.max(Math.round(RATE * 10), 1),
        timeUnit: "10s",
        duration: DURATION,
        preAllocatedVUs: Math.max(20, Math.ceil(RATE * 4)),
        maxVUs: Math.max(100, Math.ceil(RATE * 20)), // не хватит - будут dropped_iterations
      },
    },
    thresholds,
    setupTimeout: "120s",
    summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
  };
}
