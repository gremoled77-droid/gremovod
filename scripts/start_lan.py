"""Запуск студии для домашней сети (телефон по Wi-Fi). Пароль и адрес берутся из .env.lan (не в git).

Слушает 0.0.0.0:8000 и отдаёт собранный интерфейс (frontend/dist) с того же порта.
Запросы не с этого компьютера требуют пароль (см. backend/remote_access.py).
Адрес телефона: http://<IP компьютера>:8000"""
import ipaddress
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def lan_ips():
    """Частные IPv4 компьютера (Wi-Fi, виртуальные адаптеры); 192.168.* первыми."""
    found = set()
    try:
        found.update(info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET))
    except OSError:
        pass
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(('192.0.2.1', 9))  # пакет не отправляется, нужен только выбор интерфейса
            found.add(sock.getsockname()[0])
        except OSError:
            pass
    private = [ip for ip in found if ipaddress.ip_address(ip).is_private and not ip.startswith('127.')]
    return sorted(private, key=lambda ip: (not ip.startswith('192.168.'), ip))


def main():
    env_file = ROOT / '.env.lan'
    if not env_file.is_file():
        sys.exit('Нет файла .env.lan с STUDIO_ACCESS_PASSWORD (12+ символов).')
    env = dict(os.environ)
    for line in env_file.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            env[key.strip()] = value.strip()
    ips = lan_ips()
    env['STUDIO_REMOTE_HOSTS'] = ','.join(filter(None, [env.get('STUDIO_REMOTE_HOSTS', ''), *ips]))
    if len(env.get('STUDIO_ACCESS_PASSWORD', '')) < 12:
        sys.exit('STUDIO_ACCESS_PASSWORD в .env.lan короче 12 символов.')
    if not (ROOT / 'frontend' / 'dist').is_dir():
        sys.exit('Нет frontend/dist: выполни npm run build в папке frontend.')
    print('Студия для сети: ' + ', '.join(f'http://{ip}:8000' for ip in ips) + ' (на этом компьютере: http://127.0.0.1:8000)')
    sys.exit(subprocess.call([sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '0.0.0.0', '--port', '8000', '--no-access-log'],
                             cwd=ROOT, env=env))


if __name__ == '__main__':
    main()
