// Смешанный сценарий: операции идут в соотношении весов профиля нагрузки (config.js).
import exec from "k6/execution";
import { PROFILE } from "../config.js";
import { OPERATIONS } from "./operations.js";

// Каждому весу отводится свой отрезок из 100 «ячеек»; итерация попадает в ячейку по номеру.
const ranges = [];
let start = 0;
for (const op of PROFILE) {
  ranges.push({ name: op.name, start, end: start + op.weight, weight: op.weight });
  start += op.weight;
}

export function mixedStep(data) {
  const n = exec.scenario.iterationInTest;
  const block = Math.floor(n / 100);
  // 37 взаимно просто со 100: ячейки перемешаны, а не идут подряд одной операцией
  const slot = ((n % 100) * 37) % 100;
  const range = ranges.find((r) => slot >= r.start && slot < r.end);
  const seq = block * range.weight + (slot - range.start); // номер именно этой операции
  OPERATIONS[range.name](data, n, seq);
}
