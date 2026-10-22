"""Pytest-плагин BETA-02: любое исходящее соединение, кроме loopback, — ошибка и запись в отчёт.

Подключается как `-p beta02_tripwire` с `tools/` в PYTHONPATH. Платные API живут за сетью:
ноль сетевых попыток — проверяемое доказательство «ноль платных вызовов» для этого прогона.
Результат пишется в файл из BETA02_TRIPWIRE_FILE (JSON), сессия падает при попытке.
"""
import json
import os
import socket

ATTEMPTS = []
LOOPBACK = {'127.0.0.1', '::1', 'localhost', 'testserver', '0.0.0.0', ''}
_connect = socket.socket.connect
_getaddrinfo = socket.getaddrinfo


def _host(address):
    if isinstance(address, (tuple, list)) and address:
        return str(address[0])
    return str(address)


def _blocked(kind, address):
    ATTEMPTS.append({'kind': kind, 'host': _host(address)})
    raise OSError(f'BETA-02 tripwire: исходящее соединение запрещено ({kind} {_host(address)})')


def _guarded_connect(self, address):
    if self.family == getattr(socket, 'AF_UNIX', -1) or _host(address) in LOOPBACK:
        return _connect(self, address)
    return _blocked('connect', address)


def _guarded_getaddrinfo(host, *args, **kwargs):
    if host is None or str(host) in LOOPBACK:
        return _getaddrinfo(host, *args, **kwargs)
    return _blocked('dns', host)


def pytest_configure(config):
    socket.socket.connect = _guarded_connect
    socket.getaddrinfo = _guarded_getaddrinfo


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get('BETA02_TRIPWIRE_FILE')
    if path:
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump({'attempts': ATTEMPTS, 'count': len(ATTEMPTS)}, handle)
    if ATTEMPTS and session.exitstatus == 0:
        session.exitstatus = 1
