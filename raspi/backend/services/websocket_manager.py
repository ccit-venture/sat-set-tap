"""
services/websocket_manager.py — Manager koneksi WebSocket aktif.

Mengelola daftar client yang sedang terhubung dan broadcast pesan ke semua
client sekaligus. Kalau salah satu client disconnect saat broadcast,
dia dikeluarkan dari daftar tanpa crash.

Dipisah dari main.py supaya routes/websocket.py bisa import manager
tanpa circular import.
"""

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        """
        Kirim data ke semua client yang terhubung.
        Client yang sudah disconnect dikeluarkan dari daftar secara silent.
        """
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


# Satu instance global — di-import oleh routes dan background task
manager = ConnectionManager()
