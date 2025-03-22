from rise import rise
import time
from colorama import Fore, Style, init  # type: ignore
import sys
import threading

def thinking_bubble(stop_event):
    while not stop_event.is_set():
        for _ in range(3):
            if stop_event.is_set():
                break
            sys.stdout.write('.')
            sys.stdout.flush()
            time.sleep(0.5)
        sys.stdout.write('\b\b\b   \b\b\b')  # Erase the dots

def main():

    rise.register_rise_client()

    while True:
        # Get user input
        user_prompt = input(Fore.CYAN + "ME: " + Style.RESET_ALL)
        stop_event = threading.Event()  # Event to signal the thinking bubble to stop
        thinking_thread = threading.Thread(
            target=thinking_bubble, args=(stop_event,))
        thinking_thread.start()  # Start the thinking dots in a separate thread
        response = rise.send_rise_command(user_prompt)
        stop_event.set()  # Signal the thinking thread to stop
        thinking_thread.join()  # Wait for the thread to finish
        print(Fore.YELLOW + "RISE: " + response)


if __name__ == "__main__":
    main()
