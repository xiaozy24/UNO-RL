import queue
import threading
import time
from typing import Optional, Dict, Tuple
from communicator.comm_event import CommEvent, AckEvent, to_dict_recursive

class Communicator:
    """
    Backend <-> Frontend Simple Event Bus + ACK Mechanism.
    """

    def __init__(self) -> None:
        self.btf_queue: "queue.Queue[CommEvent]" = queue.Queue()
        self.ftb_queue: "queue.Queue[CommEvent]" = queue.Queue()
        self.stc_queue: "queue.Queue[Dict]" = queue.Queue() # State to Client (for debugging/logging usually)
        self.cts_queue: "queue.Queue[Dict]" = queue.Queue()
        self.glo_queue: "queue.Queue[CommEvent]" = queue.Queue()
        
        self._ack_inbox: "queue.Queue[AckEvent]" = queue.Queue()

        self.event_counter = 0
        self.pending_acks: Dict[int, threading.Event] = {}
        self.ack_results: Dict[int, Tuple[bool, str]] = {}
        self.lock = threading.Lock()

        self._stop_event = threading.Event()

        self.ack_thread = threading.Thread(
            target=self._process_acks, name="comm-ack-thread", daemon=True
        )
        self.ack_thread.start()

    def send_to_frontend(
        self,
        event: CommEvent,
        wait_for_ack: bool = False,
        timeout: float = 30.0,
    ) -> Tuple[Optional[bool], Optional[str]]:
        """
        Send event to frontend; optionally wait for ACK.

        Returns:
            (success: bool | None, message: str | None)
            - wait_for_ack=False, returns (None, None)
            - wait_for_ack=True, returns (True/False, msg)
        """
        # wait_for_ack = False # Uncomment to force disable acks if debugging
        if not wait_for_ack:
            with self.lock:
                self.event_counter += 1
                event_id = self.event_counter
                setattr(event, "_event_id", event_id)
            event_dict = to_dict_recursive(event)
            self.stc_queue.put(event_dict)
            self.btf_queue.put(event)
            return None, None

        with self.lock:
            self.event_counter += 1
            event_id = self.event_counter
            setattr(event, "_event_id", event_id)
            ack_event = threading.Event()
            self.pending_acks[event_id] = ack_event
        
        event_dict = to_dict_recursive(event)
        self.stc_queue.put(event_dict)
        self.btf_queue.put(event)

        ack_received = ack_event.wait(timeout=timeout)

        with self.lock:
            self.pending_acks.pop(event_id, None)
            result = self.ack_results.pop(event_id, (False, "ACK timeout"))

        return result

    def send_to_backend(self, event: CommEvent):
        """Frontend sends event to Backend."""
        with self.lock:
            self.event_counter += 1
            event_id = self.event_counter
            setattr(event, "_event_id", event_id)
        
        # If it's an AckEvent, route to _ack_inbox
        if isinstance(event, AckEvent):
            self._ack_inbox.put(event)
        else:
            self.ftb_queue.put(event)

    def _process_acks(self):
        while not self._stop_event.is_set():
            try:
                ack = self._ack_inbox.get(timeout=1.0)
                with self.lock:
                    if ack.ack_event_id in self.pending_acks:
                        self.ack_results[ack.ack_event_id] = (ack.success, ack.message)
                        self.pending_acks[ack.ack_event_id].set()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in ack processing: {e}")

    def stop(self):
        self._stop_event.set()
        if self.ack_thread.is_alive():
            self.ack_thread.join()
