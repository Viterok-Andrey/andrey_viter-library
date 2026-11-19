// Подготовка перед нагрузкой: вход и сведения о данных, нужные для правдоподобных запросов.
import http from "k6/http";
import { BASE, PAGE_SIZE } from "../config.js";
import { login, authHeaders } from "./auth.js";

export function prepareData() {
  const data = { token: login() };
  const params = { headers: authHeaders(data), tags: { operation: "setup" } };

  // сколько всего выдач: от этого зависит «середина» списка и номера карточек
  const first = http.get(`${BASE}/api/loans?page=1&size=${PAGE_SIZE}`, params);
  data.total = first.json("total");
  data.middlePage = Math.max(Math.floor(data.total / PAGE_SIZE / 2), 1); // как в bench/run.py

  // выдачи, которые сейчас на руках: именно их принимают при возврате
  data.pool = [];
  for (let page = 1; page <= 100; page++) {
    const response = http.get(`${BASE}/api/loans?status=on_hands&size=100&page=${page}`, params);
    const items = response.json("items") || [];
    items.forEach((item) => data.pool.push(item.id));
    if (items.length === 0 || page * 100 >= response.json("total")) break;
  }
  return data;
}
