// Испытание самой тяжёлой операции (по умолчанию HEAVY=list_middle_page). Пример:
//   k6 run -e RATE=2 -e DURATION=30s load/tests/heavy.test.js
import { prepareData } from "../flows/setup.js";
import { heavyStep } from "../scenarios/heavy.js";
import { stepOptions } from "./options.js";

export const options = stepOptions();

export function setup() {
  return prepareData();
}

export default function (data) {
  heavyStep(data);
}
