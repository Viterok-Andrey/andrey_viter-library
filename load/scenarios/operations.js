// Одно действие пользователя = один запрос к сервису. Каждая операция помечена тегами:
//   operation - название (как в таблице замеров первого задания);
//   kind: load - запрос идёт в пороги (вход и подготовка в них не входят).
import http from "k6/http";
import { BASE, PAGE_SIZE, READERS, COPIES } from "../config.js";
import { authHeaders } from "../flows/auth.js";
import {
  checkList,
  checkCard,
  checkIssue,
  checkReturn,
  checkSummary,
} from "../validators/responses.js";

// Какие коды ответа не считаются ошибкой. Для выдачи и возврата это ещё и 409:
// «экземпляр уже на руках», «у читателя просрочка», «выдача уже закрыта».
const onlyOk = http.expectedStatuses(200);
const issueOk = http.expectedStatuses(201, 409);
const returnOk = http.expectedStatuses(200, 409);

// Одинаковые номера при каждом запуске: тест воспроизводим (Math.random в k6 не фиксируется).
function pseudoRandom(n, salt) {
  let x = (n * 2654435761 + salt * 40503) >>> 0;
  x ^= x >>> 15;
  x = Math.imul(x, 2246822519) >>> 0;
  x ^= x >>> 13;
  x = Math.imul(x, 3266489917) >>> 0;
  x ^= x >>> 16;
  return (x >>> 0) / 4294967296;
}

const pick = (n, salt, max) => 1 + Math.floor(pseudoRandom(n, salt) * max);

function params(data, name, callback) {
  return {
    headers: authHeaders(data),
    timeout: "30s",
    tags: { operation: name, kind: "load" },
    responseCallback: callback,
  };
}

function get(data, name, path) {
  return http.get(`${BASE}${path}`, params(data, name, onlyOk));
}

// n - номер итерации в испытании, seq - порядковый номер этой операции (для возврата)
export const OPERATIONS = {
  list_first_page(data) {
    const response = get(data, "list_first_page", `/api/loans?page=1&size=${PAGE_SIZE}`);
    checkList(response, "list_first_page");
  },

  list_middle_page(data) {
    const response = get(
      data, "list_middle_page", `/api/loans?page=${data.middlePage}&size=${PAGE_SIZE}`
    );
    checkList(response, "list_middle_page");
  },

  list_overdue(data) {
    const response = get(
      data, "list_overdue", `/api/loans?status=overdue&page=1&size=${PAGE_SIZE}`
    );
    checkList(response, "list_overdue");
  },

  list_by_reader(data, n) {
    const reader = pick(n, 1, READERS);
    const response = get(data, "list_by_reader", `/api/loans?reader_id=${reader}&size=${PAGE_SIZE}`);
    checkList(response, "list_by_reader");
  },

  loan_card(data, n) {
    const id = pick(n, 2, data.total);
    const response = get(data, "loan_card", `/api/loans/${id}`);
    checkCard(response, id);
  },

  issue(data, n) {
    const body = JSON.stringify({ reader_id: pick(n, 3, READERS), copy_id: pick(n, 4, COPIES) });
    const response = http.post(`${BASE}/api/loans`, body, params(data, "issue", issueOk));
    checkIssue(response);
  },

  return(data, n, seq) {
    // выдачи, бывшие на руках перед началом; когда они кончились, берётся случайная (ответ 409)
    const id = seq < data.pool.length ? data.pool[seq] : pick(n, 5, data.total);
    const response = http.post(`${BASE}/api/loans/${id}/return`, null, params(data, "return", returnOk));
    checkReturn(response);
  },

  summary(data) {
    const response = get(data, "summary", "/api/summary");
    checkSummary(response);
  },
};
