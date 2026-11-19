// Смысловые проверки ответов: код ответа и состав тела.
// Сбой проверки не считается ошибкой HTTP, он виден в метрике checks.
import { check } from "k6";

function body(response) {
  try {
    return response.json();
  } catch (e) {
    return null;
  }
}

export function checkList(response, name) {
  return check(
    response,
    {
      [`${name}: status 200`]: (r) => r.status === 200,
      [`${name}: есть список и общее число`]: (r) => {
        const b = body(r);
        return b !== null && Array.isArray(b.items) && typeof b.total === "number";
      },
    },
    { operation: name, kind: "load" }
  );
}

export function checkCard(response, id) {
  return check(
    response,
    {
      "loan_card: status 200": (r) => r.status === 200,
      "loan_card: карточка нужной выдачи со связанными записями": (r) => {
        const b = body(r);
        return b !== null && b.id === id && !!b.reader && !!b.copy && !!b.book;
      },
    },
    { operation: "loan_card", kind: "load" }
  );
}

// Отказы по правилам варианта (409) допустимы и в ошибки не идут.
export function checkIssue(response) {
  return check(
    response,
    {
      "issue: 201 с выдачей или 409 по правилу": (r) => {
        const b = body(r);
        if (r.status === 201) return b !== null && typeof b.id === "number";
        return r.status === 409 && b !== null && typeof b.detail === "string";
      },
    },
    { operation: "issue", kind: "load" }
  );
}

export function checkReturn(response) {
  return check(
    response,
    {
      "return: 200 с закрытой выдачей или 409 по правилу": (r) => {
        const b = body(r);
        if (r.status === 200) return b !== null && b.status === "returned";
        return r.status === 409 && b !== null && typeof b.detail === "string";
      },
    },
    { operation: "return", kind: "load" }
  );
}

export function checkSummary(response) {
  return check(
    response,
    {
      "summary: status 200": (r) => r.status === 200,
      "summary: счётчики и топ книг": (r) => {
        const b = body(r);
        return b !== null && typeof b.on_hands === "number" && Array.isArray(b.top_books);
      },
    },
    { operation: "summary", kind: "load" }
  );
}
