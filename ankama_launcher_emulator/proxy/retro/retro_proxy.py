import logging
import socket
from dataclasses import dataclass
from threading import Thread

import socks

from ankama_launcher_emulator.server.handler import AnkamaLauncherHandler

logger = logging.getLogger()


@dataclass(eq=False)
class RetroServer(Thread):
    handler: AnkamaLauncherHandler
    port: int
    interface_ip: str | None
    socks5_host: str | None = None
    socks5_port: int | None = None
    socks5_username: str | None = None
    socks5_password: str | None = None

    def __post_init__(self):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self.interface_ip or "127.0.0.1", self.port))
        self.sock.listen(1)

    def run(self):
        logger.debug(f"[RETRO] Listening on port {self.port}")
        while True:
            conn, addr = self.sock.accept()
            Thread(target=self.handle_client, args=(conn,), daemon=True).start()

    def handle_client(self, conn: socket.socket):
        client_hash: str | None = None
        tunneling = False
        try:
            while True:
                data = conn.recv(4096)
                if not data:
                    break

                if data.startswith(b"CONNECT "):
                    header, _, pending = data.partition(b"\r\n\r\n")
                    connect_line = header.decode("ascii", errors="ignore")
                    logger.debug(
                        f"[RETRO] Cmd: {connect_line.splitlines()[0][:200]}"
                    )
                    tunneling = True
                    self._start_tunnel(conn, connect_line, pending)
                    return

                decoded_clean = data.decode("utf-8", errors="ignore").rstrip("\x00")
                if decoded_clean.startswith(
                    ("connect retro main", "auth_getGameToken")
                ):
                    logger.debug(
                        f"[RETRO] Cmd: {decoded_clean.splitlines()[0][:200]}"
                    )
                else:
                    logger.debug(f"[RETRO] {len(data)} bytes")

                if decoded_clean.startswith("connect retro main"):
                    parts = decoded_clean.split(" ")
                    if len(parts) > 0:
                        client_hash = parts[-1]
                        conn.sendall(b"connected\x00")
                        conn.sendall(f"connect {client_hash}\x00".encode("utf-8"))

                elif decoded_clean.startswith("auth_getGameToken"):
                    if client_hash:
                        token = self.handler.auth_getGameToken(client_hash, 101)
                        conn.sendall(
                            f"auth_getGameToken {token}\x00".encode("utf-8")
                        )
                    else:
                        logger.debug(
                            "[RETRO] Error: auth_getGameToken received without handshake"
                        )
        finally:
            if not tunneling:
                conn.close()

    def _start_tunnel(
        self,
        client_conn: socket.socket,
        connect_message: str,
        pending: bytes = b"",
    ):
        parts = connect_message.split(" ")
        host_port = parts[1]
        host, port_str = host_port.rsplit(":", 1)
        remote_port = int(port_str)

        logger.debug(f"[RETRO] Tunneling to {host}:{remote_port}")

        if self.socks5_host and self.socks5_port:
            remote_sock = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
            remote_sock.set_proxy(
                socks.SOCKS5,
                addr=self.socks5_host,
                port=self.socks5_port,
                username=self.socks5_username,
                password=self.socks5_password,
                rdns=True,
            )
        else:
            remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if self.interface_ip is not None:
            remote_sock.bind((self.interface_ip, 0))

        remote_sock.connect((host, remote_port))

        if pending:
            remote_sock.sendall(pending)

        def forward(src: socket.socket, dst: socket.socket):
            try:
                while True:
                    chunk = src.recv(4096)
                    if not chunk:
                        break
                    dst.sendall(chunk)
            except OSError:
                pass
            finally:
                try:
                    src.close()
                except OSError:
                    pass
                try:
                    dst.close()
                except OSError:
                    pass

        Thread(target=forward, args=(client_conn, remote_sock), daemon=True).start()
        Thread(target=forward, args=(remote_sock, client_conn), daemon=True).start()
