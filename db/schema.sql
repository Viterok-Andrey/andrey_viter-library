
DROP SCHEMA IF EXISTS {{schema}} CASCADE;
CREATE SCHEMA {{schema}};
SET search_path TO {{schema}};

-- Читатели
CREATE TABLE reader (
    id          SERIAL PRIMARY KEY,
    full_name   TEXT NOT NULL,
    card_number TEXT NOT NULL        
);


CREATE TABLE book (
    id      SERIAL PRIMARY KEY,
    title   TEXT NOT NULL,
    author  TEXT NOT NULL
);


CREATE TABLE book_copy (
    id               SERIAL PRIMARY KEY,
    book_id          INTEGER NOT NULL REFERENCES book(id),
    inventory_number TEXT NOT NULL
);


CREATE TABLE loan (
    id          SERIAL PRIMARY KEY,
    reader_id   INTEGER NOT NULL REFERENCES reader(id),
    copy_id     INTEGER NOT NULL REFERENCES book_copy(id),
    issued_at   DATE NOT NULL,             
    due_date    DATE NOT NULL,              
    returned_at DATE,                           
    fine        NUMERIC(10, 2) NOT NULL DEFAULT 0   
);
