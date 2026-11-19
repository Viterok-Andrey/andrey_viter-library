// Вход: выполняется один раз до нагрузки (в setup), в результаты испытания не попадает.
import http from "k6/http";
import { check } from "k6";
import { BASE, USER, PASSWORD } from "../config.js";

export function login() {
  const response = http.post(
    `${BASE}/api/login`,
    JSON.stringify({ username: USER, password: PASSWORD }),
    // тег operation: login и нет тега kind: load, поэтому вход не входит в пороги
    { headers: { "Content-Type": "application/json" }, tags: { operation: "login" } }
  );
  const ok = check(response, {
    "вход: status 200": (r) => r.status === 200,
    "вход: есть токен": (r) => !!r.json("token"),
  });
  if (!ok) {
    throw new Error(`Вход не удался (код ${response.status}): ${response.body}`);
  }
  return response.json("token");
}

export function authHeaders(data) {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${data.token}`,
  };
}
