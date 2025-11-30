import socket
import threading
import os
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.progress import Progress

console = Console()

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5001
BUFFER_SIZE = 4096
SEPARATOR = "<SEPARATOR>"

if not os.path.exists("received_files"):
    os.makedirs("received_files")

clients = []
clients_lock = threading.Lock()


# -------------------- HANDLE CLIENT --------------------
def handle_client(client_socket, client_address):
    with clients_lock:
        clients.append(client_socket)
    console.print(f"[bold green][NEW CONNECTION][/bold green] {client_address}")

    try:
        while True:
            received = client_socket.recv(BUFFER_SIZE).decode()
            if not received:
                break

            command, *info = received.split(SEPARATOR)

            if command == "TEXT":
                message = info[0]
                console.print(f"[bold cyan]{client_address}[/bold cyan] says: {message}")

            elif command == "FILE":
                filename, filesize = info
                filename = os.path.basename(filename)
                filesize = int(filesize)
                filepath = os.path.join("received_files", filename)

                console.print(Panel.fit(
                    f"[yellow]{client_address}[/yellow] is sending: [green]{filename}[/green] ({filesize} bytes)",
                    title="File Transfer", style="bold blue"
                ))

                with open(filepath, "wb") as f, Progress() as progress:
                    task = progress.add_task(f"[cyan]Receiving {filename}...", total=filesize)
                    bytes_received = 0
                    while bytes_received < filesize:
                        chunk = client_socket.recv(BUFFER_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_received += len(chunk)
                        progress.update(task, advance=len(chunk))
                console.print(f"[bold green]✔ File received:[/bold green] {filename}")

    except Exception as e:
        console.print(f"[red][ERROR][/red] {client_address} disconnected: {e}")

    finally:
        with clients_lock:
            if client_socket in clients:
                clients.remove(client_socket)
        client_socket.close()
        console.print(f"[red][DISCONNECTED][/red] {client_address}")


# -------------------- FILE SENDER --------------------
def send_file(filepath, target=None):
    if not os.path.exists(filepath):
        console.print("[red][!][/red] File not found.")
        return

    filesize = os.path.getsize(filepath)
    filename = os.path.basename(filepath)
    header = f"FILE{SEPARATOR}{filename}{SEPARATOR}{filesize}"

    targets = clients if target is None else [target]
    for client in targets:
        try:
            client.send(header.encode())
            with open(filepath, "rb") as f, Progress() as progress:
                task = progress.add_task(f"[green]Sending {filename}...", total=filesize)
                while True:
                    bytes_read = f.read(BUFFER_SIZE)
                    if not bytes_read:
                        break
                    client.sendall(bytes_read)
                    progress.update(task, advance=len(bytes_read))
            console.print(f"[bold green]✔ Sent file:[/bold green] {filename} → {client.getpeername()}")
        except Exception as e:
            console.print(f"[red][SEND ERROR][/red] {e}")


# -------------------- SERVER CONSOLE --------------------
def server_console():
    console.print(Panel.fit("Server Commands:\n"
                            "[yellow]/file <path>[/yellow] → Send file to all\n"
                            "[yellow]/fileto <index> <path>[/yellow] → Send to one\n"
                            "[yellow]/msg <text>[/yellow] → Broadcast message\n"
                            "[yellow]/clients[/yellow] → List connected clients\n",
                            title="Server Control", style="bold cyan"))
    while True:
        cmd = Prompt.ask("[bold magenta]Server[/bold magenta]").strip()

        if cmd.startswith("/fileto"):
            parts = cmd.split(" ", 2)
            if len(parts) < 3:
                console.print("[red]Usage: /fileto <index> <path>[/red]")
                continue
            idx, filepath = int(parts[1]), parts[2]
            with clients_lock:
                if idx < len(clients):
                    send_file(filepath, target=clients[idx])
                else:
                    console.print("[red]Invalid client index.[/red]")

        elif cmd.startswith("/file"):
            _, filepath = cmd.split(" ", 1)
            send_file(filepath)

        elif cmd.startswith("/msg"):
            _, text = cmd.split(" ", 1)
            message = f"TEXT{SEPARATOR}{text}"
            with clients_lock:
                for c in clients:
                    c.send(message.encode())
            console.print(f"[green][SERVER][/green]: {text}")

        elif cmd == "/clients":
            with clients_lock:
                for i, c in enumerate(clients):
                    console.print(f"[{i}] {c.getpeername()}")

        else:
            console.print("[yellow]Unknown command.[/yellow]")


# -------------------- START SERVER --------------------
def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((SERVER_HOST, SERVER_PORT))
    server_socket.listen(5)
    console.print(Panel.fit(f"Server running on [green]{SERVER_HOST}:{SERVER_PORT}[/green]",
                            title="Server Started", style="bold green"))

    threading.Thread(target=server_console, daemon=True).start()

    while True:
        client_socket, client_address = server_socket.accept()
        threading.Thread(target=handle_client, args=(client_socket, client_address), daemon=True).start()


if __name__ == "__main__":
    start_server()
