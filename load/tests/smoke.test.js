// Проверочный прогон: по одному разу каждая операция профиля. Нагрузки нет,
// числа времени в отчёт не идут. Все проверки должны быть отмечены ✓.
//   k6 run load/tests/smoke.test.js
import { prepareData } from "../flows/setup.js";
import { OPERATIONS } from "../scenarios/operations.js";
import { PROFILE } from "../config.js";

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: { checks: ["rate==1"] },
  setupTimeout: "120s",
};

export function setup() {
  return prepareData();
}

export default function (data) {
  PROFILE.forEach((op, index) => OPERATIONS[op.name](data, index + 1, index));
}
