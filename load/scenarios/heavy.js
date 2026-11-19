// Одиночный сценарий: только самая тяжёлая операция (HEAVY в config.js).
import exec from "k6/execution";
import { HEAVY } from "../config.js";
import { OPERATIONS } from "./operations.js";

if (!OPERATIONS[HEAVY]) {
  throw new Error(`Неизвестная операция HEAVY=${HEAVY}. Допустимы: ${Object.keys(OPERATIONS)}`);
}

export function heavyStep(data) {
  const n = exec.scenario.iterationInTest;
  OPERATIONS[HEAVY](data, n, n);
}
