"""Сеть в процессе тестов: наружу нельзя, локальный сервер — можно.

Механизм общий для обеих брифовых команд (pytest и unittest discover): он ставится один раз
в процессе тестов и закрывает внешние адреса — и на уровне сокета, и на уровне транспорта httpx.
Попытка выйти наружу даёт явную ошибку вместо сетевого запроса.

Локальные адреса (loopback) остаются доступными: тестам нужен свой сервер и TestClient.
"""
import os
import socket
import sys

TEST_MODE_ENV = 'LLM_GATEWAY_TEST_MODE'

_installed = False
_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex
_getaddrinfo = socket.getaddrinfo


def test_mode() -> bool:
    """Процесс тестов: раннер задаёт его явно (переменная окружения) или он распознаётся по раннеру."""
    if os.environ.get(TEST_MODE_ENV, '').strip():
        return True
    if 'pytest' in sys.modules:
        return True
    # `python -m unittest` выполняет unittest.__main__ в пространстве __main__: в sys.modules его нет
    spec = getattr(sys.modules.get('__main__'), '__spec__', None)
    runner = str(getattr(spec, 'name', '') or '')
    return runner.startswith('unittest') or runner.startswith('pytest')


def is_local_host(host) -> bool:
    """Хост локальный: loopback (127.0.0.0/8, ::1, localhost) и пустой хост."""
    if host is None:
        return True
    name = str(host).strip().lower()
    if not name or name in ('localhost', '::1', '0:0:0:0:0:0:0:1'):
        return True
    return name.startswith('127.')


def is_local(address) -> bool:
    """Адрес локальный: loopback и unix-сокеты (путь)."""
    if isinstance(address, str):
        return True
    if not isinstance(address, tuple) or not address:
        return False
    return is_local_host(address[0])


def _refuse(target):
    raise AssertionError('Тест попытался выйти в сеть: ' + str(target))


def install() -> None:
    """Закрывает внешние адреса: сокеты, разрешение имён и транспорт httpx. Локальные — работают."""
    global _installed
    if _installed:
        return

    def connect(self, address, *args, **kwargs):
        if not is_local(address):
            _refuse(address)
        return _connect(self, address, *args, **kwargs)

    def connect_ex(self, address, *args, **kwargs):
        if not is_local(address):
            _refuse(address)
        return _connect_ex(self, address, *args, **kwargs)

    def getaddrinfo(host, port, *args, **kwargs):
        if not is_local_host(host):
            _refuse(host)
        return _getaddrinfo(host, port, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = getaddrinfo

    import httpx

    async_handle = httpx.AsyncHTTPTransport.handle_async_request
    sync_handle = httpx.HTTPTransport.handle_request

    async def handle_async_request(self, request):
        if not is_local_host(request.url.host):
            _refuse(request.url)
        return await async_handle(self, request)

    def handle_request(self, request):
        if not is_local_host(request.url.host):
            _refuse(request.url)
        return sync_handle(self, request)

    httpx.AsyncHTTPTransport.handle_async_request = handle_async_request
    httpx.HTTPTransport.handle_request = handle_request
    _installed = True


def install_if_test_mode() -> bool:
    """Ставит защиту, если процесс тестовый. В студии сеть не трогаем."""
    if not test_mode():
        return False
    install()
    return True
