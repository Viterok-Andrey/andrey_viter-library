// Испытание смешанным профилем. Пример:
//   k6 run -e RATE=8 -e DURATION=30s load/tests/mixed.test.js
import { prepareData } from "../flows/setup.js";
import { mixedStep } from "../scenarios/mixed.js";
import { stepOptions } from "./options.js";

export const options = stepOptions();

export function setup() {
  return prepareData();
}

export default function (data) {
  mixedStep(data);
}
