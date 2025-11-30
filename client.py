import socket
import threading
import os
import time
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.progress import Progress

console = Console()

# -------------------- CONFIG --------------------
SERVER_IP = "127.0.0.1"     # change to server’s IP if remote
SERVER_PORT = 5001
BUFFER_SIZE = 4096
SEPARATOR = "<SEPARATOR>"

if not os.path.exists("received_files"):
    os.makedirs("received_files")

# -------------------- RECEIVE DATA --------------------
def receive_data(sock):
    global ping_start
    while True:
        try:
            data = sock.recv(BUFFER_SIZE).decode()
            if not data:
                break

            command, *info = data.split(SEPARATOR)

            if command == "TEXT":
                if info[0] == "PING_RESPONSE":
                    latency = (time.time() - ping_start) * 1000
                    console.print(f"[green]🏓 Ping response received! Latency: {latency:.2f} ms[/green]")
                else:
                    console.print(f"[bold cyan][SERVER][/bold cyan]: {info[0]}")

            elif command == "FILE":
                filename, filesize = info
                filesize = int(filesize)
                filepath = os.path.join("received_files", filename)

                console.print(Panel.fit(
                    f"Receiving file: [green]{filename}[/green] ({filesize} bytes)",
                    title="File Transfer", style="bold blue"
                ))

                with open(filepath, "wb") as f, Progress() as progress:
                    task = progress.add_task(f"[cyan]Receiving {filename}...", total=filesize)
                    bytes_received = 0
                    while bytes_received < filesize:
                        chunk = sock.recv(BUFFER_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_received += len(chunk)
                        progress.update(task, advance=len(chunk))

                console.print(f"[bold green]✔ File received successfully:[/bold green] {filename}\n")

        except Exception as e:
            console.print(f"[red][ERROR][/red] {e}")
            break


# -------------------- SEND FILE --------------------
def send_file(sock, filepath):
    if not os.path.exists(filepath):
        console.print("[red][!][/red] File not found.")
        return

    filesize = os.path.getsize(filepath)
    filename = os.path.basename(filepath)
    header = f"FILE{SEPARATOR}{filename}{SEPARATOR}{filesize}"
    sock.send(header.encode())

    with open(filepath, "rb") as f, Progress() as progress:
        task = progress.add_task(f"[green]Sending {filename}...", total=filesize)
        while True:
            bytes_read = f.read(BUFFER_SIZE)
            if not bytes_read:
                break
            sock.sendall(bytes_read)
            progress.update(task, advance=len(bytes_read))
    console.print(f"[bold green]✔ Sent file:[/bold green] {filename}")


# -------------------- SEND MESSAGE --------------------
def send_data(sock):
    global ping_start
    console.print(Panel.fit(
        "Type your messages below.\nUse [yellow]/file <path>[/yellow] to send files.\nUse [yellow]/ping[/yellow] to test connection latency.",
        title="Client Console", style="bold cyan"
    ))
    while True:
        msg = Prompt.ask("[bold magenta]You[/bold magenta]")
        if msg.lower().startswith("/file"):
            try:
                _, filepath = msg.split(" ", 1)
                send_file(sock, filepath)
            except ValueError:
                console.print("[red]Usage: /file <path>[/red]")
        elif msg.lower() == "/ping":
            ping_start = time.time()
            sock.send(f"TEXT{SEPARATOR}PING_REQUEST".encode())
        else:
            sock.send(f"TEXT{SEPARATOR}{msg}".encode())


# -------------------- MAIN --------------------
if __name__ == "__main__":
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((SERVER_IP, SERVER_PORT))
        console.print(Panel.fit(
            f"Connected to server at [green]{SERVER_IP}:{SERVER_PORT}[/green]",
            title="Connection Successful", style="bold green"
        ))

        # STEP 1️⃣ — Ask once for name and email (for welcome mail)
        console.print(Panel.fit(
            "Welcome! Please enter your details for verification.\nYou’ll receive a thank-you email shortly.",
            title="Client Registration", style="bold cyan"
        ))
        name = Prompt.ask("[cyan]Enter your name[/cyan]")
        email = Prompt.ask("[cyan]Enter your email address[/cyan]")

        # Send introduction details to server
        intro_message = f"INTRO{SEPARATOR}{name}{SEPARATOR}{email}"
        s.send(intro_message.encode())

        console.print("[green]📨 Sending your info to the server... You'll get a confirmation email soon.[/green]\n")

        # STEP 2️⃣ — Start normal communication threads
        threading.Thread(target=receive_data, args=(s,), daemon=True).start()
        send_data(s)

    except ConnectionRefusedError:
        console.print("[red]❌ Cannot connect to server. Make sure the server is running.[/red]")
    except Exception as e:
        console.print(f"[red]⚠ Error: {e}[/red]")
