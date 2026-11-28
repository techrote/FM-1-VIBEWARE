# SPDX-License-Identifier: MIT
"""Shared CYD controller -> actual TCP bridge -> emulated USB -> actual FM-1 CPU.
Qualification fixture only. Explicit modeled-time advances, no physical timing claim.
"""
import importlib.util
import json
from collections import deque
from pathlib import Path
from queue import Queue, Empty
import select
import socket
import subprocess
import sys
import threading
import time

CYD, SIM, EMU, XIP, OUTPUT = map(Path, sys.argv[1:])
sys.path.insert(0, str(CYD))
from bridge.midi_io import validate_midi_bytes
from bridge.protocol import LineDecoder, encode_frame
from bridge.server import BridgeServer

spec = importlib.util.spec_from_file_location(
    "native_bridge_test", CYD / "tests/bridge/test_native_integration.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
NativeCore = mod.NativeCore


class EmulatedUSB:
    """Bounded synchronous test adapter; not a production USB/Mido backend."""
    connected = True
    detail = "Actual FM-1 firmware in pinned emulator USB model"

    def __init__(self):
        self.process = subprocess.Popen([str(EMU), str(XIP)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, text=True, bufsize=1)
        self.lines = Queue(maxsize=8)
        self.pending = deque()
        self.sent = []
        self.reader = threading.Thread(target=self.read_stdout, daemon=True)
        self.reader.start()
        assert self.read() == "ready"

    def read_stdout(self):
        for line in self.process.stdout:
            self.lines.put(line.strip(), timeout=10)

    def read(self):
        try:
            return self.lines.get(timeout=60)
        except Empty as exc:
            raise AssertionError("emulator adapter did not reply") from exc

    def command(self, line):
        self.process.stdin.write(line + "\n")
        self.process.stdin.flush()
        return self.read().split()

    def send(self, data):
        message = validate_midi_bytes(data)
        assert len(self.sent) < 128
        self.sent.append(message)
        reply = self.command("send " + " ".join(f"{b:02x}" for b in message))
        assert reply[0] == "midi", reply
        assert len(self.pending) < 128
        self.pending.append(validate_midi_bytes(int(b, 16) for b in reply[1:]))

    def receive(self):
        result = list(self.pending)
        self.pending.clear()
        return result

    def tick(self, now):
        del now  # model time is controlled explicitly, not wall time

    def advance(self, ms):
        reply = self.command(f"advance {ms}")
        assert reply[0] == "pcm", reply
        result = {"samples": int(reply[1]), "nonzero": int(reply[2]), "hash": reply[3]}
        assert result["samples"] > 0
        return result

    def close(self):
        try:
            if self.process.poll() is None:
                self.process.stdin.write("quit\n")
                self.process.stdin.flush()
                self.process.wait(timeout=5)
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=5)
            self.process.stdin.close()
            self.process.stdout.close()
            self.reader.join(timeout=2)


class Route:
    def __init__(self, endpoint, native):
        self.endpoint, self.native = endpoint, native
        self.clock = 0.0
        # Freeze the bridge timeout clock for the deterministic instruction-clock
        # fixture. Transport timeout is covered separately in CYDaux bridge tests.
        self.server = BridgeServer(endpoint, "fixture-token", port=0, mode="midi",
                                   profile="xenoresonator-native", name=endpoint.detail,
                                   clock=lambda: self.clock)
        self.sock = None
        self.decoder = LineDecoder()
        self.frames = deque()

    def transmit(self, frame):
        self.sock.sendall(encode_frame(frame))

    def read(self):
        deadline = time.monotonic() + 90
        while not self.frames:
            assert time.monotonic() < deadline, "TCP frame timeout"
            self.server.step(0.001)
            if select.select([self.sock], [], [], 0)[0]:
                chunk = self.sock.recv(4096)
                assert chunk, "bridge socket closed unexpectedly"
                self.frames.extend(self.decoder.feed(chunk))
        return self.frames.popleft()

    def open_socket(self):
        assert self.sock is None
        self.sock = socket.create_connection(self.server.address, timeout=5)
        self.decoder = LineDecoder()
        self.frames.clear()

    def reject_hello(self, frame):
        before = len(self.endpoint.sent)
        self.open_socket()
        self.transmit(frame)
        assert self.read()["type"] == "error"
        self.await_retired()
        assert len(self.endpoint.sent) == before, "unauthenticated MIDI reached target"

    def await_retired(self):
        for _ in range(100):
            self.server.step(0.001)
            if self.server.client is None:
                self.sock.close()
                self.sock = None
                # Drain any retired endpoint reply while no controller exists.
                self.server.step(0)
                return
        raise AssertionError("bridge failed to retire controller")

    def reject_command(self, frame):
        before = len(self.endpoint.sent)
        self.transmit(frame)
        assert self.read()["type"] == "error"
        assert len(self.endpoint.sent) == before, "bridge-rejected command reached USB"

    def target_error(self, packet, code):
        self.transmit({"type": "midi", "data": packet})
        reply = self.read()
        assert reply["type"] == "midi", reply
        data = reply["data"]
        assert data[:7] == [240, 125, 67, 89, 1, 0, 9], data
        assert data[7:13] == packet[7:13] and data[14] == code, data

    def connect(self):
        self.open_socket()
        self.transmit({"type": "hello", "protocol": 1, "token": "fixture-token"})
        hello = self.read()
        assert hello["type"] == "hello" and hello["ready"] and hello["mode"] == "midi"
        self.transmit({"type": "profile", "id": "xenoresonator-native"})

    def exchange(self):
        # Each actual CY1 request in this low-rate scenario has one reply.
        # Feed the returned bytes into the shared controller, not a second codec.
        for _ in range(16):
            outgoing, self.native.outgoing = self.native.outgoing, []
            if not outgoing:
                return self.native.state
            for data in outgoing:
                assert data[:6] == [240, 125, 67, 89, 1, 0], data
                self.transmit({"type": "midi", "data": data})
                frame = self.read()
                assert frame["type"] == "midi", frame
                self.native.command("rx " + " ".join(map(str, frame["data"])))
        raise AssertionError("controller exchange failed to settle")

    def action(self, command):
        self.native.command(command)
        return self.exchange()

    def drop(self):
        self.sock.close()
        self.sock = None
        for _ in range(100):
            self.server.step(0.001)
            if self.server.client is None:
                return
        raise AssertionError("bridge failed to retire controller")

    def close(self):
        if self.sock is not None:
            self.sock.close()
        self.server.close()


def main():
    endpoint = EmulatedUSB()
    native = None
    route = None
    try:
        native = NativeCore(SIM)
        route = Route(endpoint, native)
        # Refusals must be proven against the actual USB adapter, not a mock.
        route.reject_hello({"type": "hello", "protocol": 2, "token": "fixture-token"})
        route.reject_hello({"type": "hello", "protocol": 1, "token": "wrong-token"})
        route.reject_hello({"type": "midi", "data": [144, 48, 110]})
        route.connect()
        route.reject_command({"type": "profile", "id": "unimplemented-profile"})
        route.reject_command({"type": "midi", "data": [144, 48, 256]})
        for command in ("echo off", "profile xenoresonator-native", "transport wifi", "connect"):
            native.command(command)
        state = route.exchange()
        assert state["companionReady"] and state["sourceLabel"] == "Emulated firmware", state
        assert state["controls"][0]["value"] == 76, state
        assert state["telemetryAvailable"], state
        # The stdio Wi-Fi simulator retains its mock-link indicator. The actual
        # negotiated identity and PCM below establish emulated-firmware evidence.
        witnesses = {"identity": state["sourceLabel"], "simulatorMockIndicator": state["mockPeer"]}
        state = route.action("parameter 0 100")
        assert state["controls"][0]["value"] == 100, state
        state = route.action("parameter 2 90")
        assert state["controls"][2]["value"] == 90, state
        route.action("note 48 110")
        note = next(m for m in reversed(endpoint.sent) if m[6] == 7 and m[15] > 0)
        witnesses["strike"] = endpoint.advance(120)
        assert witnesses["strike"]["nonzero"] > 128
        state = route.action("tick 100")
        assert state["telemetryAvailable"] and state["outputPeak"] > 0, state
        route.action("panic")
        endpoint.advance(40)
        witnesses["panic"] = endpoint.advance(80)
        assert witnesses["panic"]["nonzero"] == 0, witnesses

        route.action("note 48 110")
        assert endpoint.advance(100)["nonzero"] > 128
        route.drop()
        assert endpoint.sent[-1][6] == 8, "bridge must transmit emergency CY1 panic"
        endpoint.advance(40)
        witnesses["socket_drop"] = endpoint.advance(80)
        assert witnesses["socket_drop"]["nonzero"] == 0, witnesses
        # Panic does not itself retire the firmware session: expire its lease.
        endpoint.advance(1600)
        native.command("disconnect")
        native.outgoing.clear()  # retired transport bytes must never enter new TCP
        route.connect()
        state = route.action("connect")
        assert state["companionReady"] and state["sourceLabel"] == "Emulated firmware", state
        latest_discover = next(m for m in reversed(endpoint.sent) if m[6] == 1)
        assert latest_discover[7:11] != note[7:11], "fresh session required"
        route.transmit({"type": "midi", "data": list(note)})
        stale = route.read()
        assert stale["type"] == "midi" and stale["data"][6] == 9 and stale["data"][14] == 3, stale
        witnesses["stale_session"] = endpoint.advance(80)
        assert witnesses["stale_session"]["nonzero"] == 0, witnesses
        # Version and instrument-profile refusals must not alter the active
        # target state or consume the valid controller's next sequence.
        wrong_version = list(latest_discover)
        wrong_version[4] = 2
        route.target_error(wrong_version, 2)
        wrong_profile = list(latest_discover)
        wrong_profile[14] = 1
        route.target_error(wrong_profile, 4)
        witnesses["version_profile_refusal"] = endpoint.advance(80)
        assert witnesses["version_profile_refusal"]["nonzero"] == 0
        state = route.action("tick 100")
        assert state["companionReady"] and state["telemetryAvailable"], state

        # Advance ONLY the bridge clock: target time is intentionally still
        # well inside the 1.5 s endpoint lease. This isolates TCP timeout panic
        # from a false pass caused by firmware lease expiry.
        route.action("note 52 110")
        assert endpoint.advance(100)["nonzero"] > 128
        before = len(endpoint.sent)
        route.clock += 5.9
        route.server.step(0)
        assert route.server.client is not None and len(endpoint.sent) == before
        route.clock += 0.2
        route.await_retired()
        assert len(endpoint.sent) == before + 1 and endpoint.sent[-1][6] == 8
        endpoint.advance(40)
        witnesses["bridge_timeout"] = endpoint.advance(80)
        assert witnesses["bridge_timeout"]["nonzero"] == 0

        # Re-establish a fresh session, then fail framing while a note sounds.
        endpoint.advance(1600)
        native.command("disconnect")
        native.outgoing.clear()
        route.connect()
        state = route.action("connect")
        assert state["companionReady"] and state["telemetryAvailable"], state
        route.action("note 55 110")
        assert endpoint.advance(100)["nonzero"] > 128
        before = len(endpoint.sent)
        route.sock.sendall(b'{"type":"ping","id":1,"id":2}\\n')
        assert route.read()["type"] == "error"
        route.await_retired()
        assert len(endpoint.sent) == before + 1 and endpoint.sent[-1][6] == 8
        endpoint.advance(40)
        witnesses["malformed_frame"] = endpoint.advance(80)
        assert witnesses["malformed_frame"]["nonzero"] == 0
        witnesses["bridge_refusals"] = ["protocol", "token", "preauth MIDI",
                                        "unknown profile", "out-of-range MIDI"]
        report = {"status": "PASS", "route": "shared controller / authenticated localhost TCP / actual emulated USB / actual firmware CPU",
                  "physical": "NOT RUN", "timing": "instruction-clock, explicit modeled advances",
                  "messages": len(endpoint.sent), "witnesses": witnesses}
        OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))
    finally:
        if route is not None:
            route.close()
        if native is not None:
            native.close()
        endpoint.close()


if __name__ == "__main__":
    main()
