"""Только чтение: что ремонт GA-01 сделал бы со строками llm_calls и сколько вызовов ждёт сверки.

Ничего не пишет: база открывается в режиме mode=ro. Запускать на КОПИИ рабочей базы:

    python llm_ledger_dryrun.py runtime\\llm-audit-copy.sqlite3

Условия повторяют backend/llm_guard.py::repair_legacy_money на голове 784ea0c без импорта backend.
Случай «по токенам» приблизительный: цена модели здесь не считается.
"""
import math
import sqlite3
import sys
from pathlib import Path

HOLDING = ('reserved', 'done', 'submission_unknown')
MAX_USAGE_TOKENS = 10_000_000


def readable(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def tokens_ok(value):
    return type(value) is int and 0 <= value <= MAX_USAGE_TOKENS


def main(path):
    # mode=ro: файл не создаётся и не меняется; as_uri() корректно кодирует пути Windows.
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    columns = {r['name'] for r in db.execute('PRAGMA table_info(llm_calls)')}
    has_confirmed = 'confirmed_usd' in columns
    by_status = {}
    groups = {'по оценке': [], 'по токенам (примерно)': [], 'станет unreadable': [],
              'не держит деньги, станет 0': [], 'done с неподтверждённой частью': [],
              'битые токены (ремонт не меняет, справка)': []}
    for r in db.execute('SELECT * FROM llm_calls ORDER BY created_at'):
        count, total = by_status.get(r['status'], (0, 0.0))
        by_status[r['status']] = (count + 1, total + (r['usd'] if readable(r['usd']) else 0.0))
        tokens = (r['input_tokens'], r['output_tokens'])
        if any(t is not None and not tokens_ok(t) for t in tokens):
            groups['битые токены (ремонт не меняет, справка)'].append(r)
        if not readable(r['usd']):
            if r['status'] not in HOLDING:
                groups['не держит деньги, станет 0'].append(r)
            elif readable(r['estimated_usd']) and r['estimated_usd'] > 0:
                groups['по оценке'].append(r)
            elif all(tokens_ok(t) for t in tokens) and sum(tokens) > 0:
                groups['по токенам (примерно)'].append(r)
            else:
                groups['станет unreadable'].append(r)
        elif (has_confirmed and r['status'] == 'done' and readable(r['confirmed_usd'])
              and round(r['usd'], 6) > round(r['confirmed_usd'], 6)):
            groups['done с неподтверждённой частью'].append(r)
    print('Колонка confirmed_usd:', 'есть' if has_confirmed else 'нет (миграция ещё не запускалась)')
    print('По статусам (строк, сумма читаемых usd):')
    for status, (count, total) in sorted(by_status.items()):
        print(f'  {status:20} {count:6} {total:12.6f}')
    print('Что изменит ремонт на старте:')
    for name, rows in groups.items():
        print(f'  {name:32} {len(rows)}')
        for r in rows[:10]:
            print(f'      {r["id"]} проект={r["project_id"]} статус={r["status"]} '
                  f'usd={r["usd"]!r} оценка={r["estimated_usd"]!r} создан={r["created_at"]}')
    print('Наибольшая читаемая оценка одного вызова по моделям (опора для потолка резерва):')
    for r in db.execute('SELECT model,MAX(estimated_usd) m,COUNT(*) n FROM llm_calls '
                        "WHERE typeof(estimated_usd) IN ('integer','real') AND estimated_usd>=0 "
                        "AND estimated_usd<9e999 GROUP BY model ORDER BY m DESC"):
        print(f'  {r["model"]:24} {r["m"]:10.6f}  (строк: {r["n"]})')
    print("Строки 'reserved' при остановленной студии — резервы, оставшиеся после падения процесса.")
    db.close()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Использование: python llm_ledger_dryrun.py путь_к_копии.sqlite3')
    main(sys.argv[1])
