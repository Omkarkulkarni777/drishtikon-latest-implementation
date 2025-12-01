from stt import listen
import subprocess

def main():
    print("Say a command... (read / detect / exit)")

    while True:
        cmd = listen()

        if not cmd:
            continue

        cmd = cmd.lower()

        if "read" in cmd:
            print("Launching reading module...")
            subprocess.run(["python3", "reading/read.py"])

        elif "detect" in cmd or "object" in cmd:
            print("Launching detection module...")
            subprocess.run(["python3", "yolo/detect.py"])

        elif "exit" in cmd or "quit" in cmd:
            print("Goodbye!")
            break

        else:
            print("Unknown command:", cmd)


if __name__ == "__main__":
    main()
