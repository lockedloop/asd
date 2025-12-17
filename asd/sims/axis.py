"""AXI-Stream simulation utilities for cocotb testbenches.

This module provides reusable Driver, Monitor, and Scoreboard classes
that wrap cocotbext-axi for ergonomic AXI-Stream verification.
"""

import random
from collections import deque
from collections.abc import Generator
from typing import Any, Literal

import cocotb
from cocotb.triggers import with_timeout
from cocotbext.axi import AxiStreamBus, AxiStreamFrame, AxiStreamSink, AxiStreamSource


def _make_duty_cycle_generator(duty_cycle: float) -> Generator[bool, None, None]:
    """Generate pause pattern for given duty cycle.

    Args:
        duty_cycle: Float between 0.0 and 1.0 where 1.0 means always active.

    Yields:
        True to pause (stall), False to continue.
    """
    while True:
        yield random.random() >= duty_cycle


class Driver:
    """Wraps cocotbext-axi AxiStreamSource for driving AXIS transactions.

    Provides an ergonomic interface for sending data on an AXI-Stream bus
    with optional duty cycle control for traffic shaping.
    """

    def __init__(
        self,
        dut: Any,
        bus: str | AxiStreamBus,
        clock: Any,
        reset: Any = None,
        reset_active_level: bool = True,
    ) -> None:
        """Initialize the AXIS driver.

        Args:
            dut: Device under test (cocotb handle)
            bus: AXI-Stream bus prefix string or AxiStreamBus instance
            clock: Clock signal
            reset: Reset signal (optional)
            reset_active_level: True if reset is active-high, False if active-low
        """
        if isinstance(bus, str):
            bus = AxiStreamBus.from_prefix(dut, bus)
        self._source = AxiStreamSource(
            bus,
            clock,
            reset,
            reset_active_level=reset_active_level,
        )
        self._clock = clock

    async def send(self, data: bytes | AxiStreamFrame) -> None:
        """Send data on the AXIS bus.

        Args:
            data: Bytes or AxiStreamFrame to send
        """
        if isinstance(data, bytes):
            frame = AxiStreamFrame(tdata=data)
        else:
            frame = data
        await self._source.send(frame)

    async def send_frame(self, data: bytes) -> None:
        """Send a complete frame (with tlast asserted).

        This is a convenience alias for send() with bytes.

        Args:
            data: Bytes to send as a complete frame
        """
        await self.send(data)

    async def wait_idle(self) -> None:
        """Wait until all pending transfers complete."""
        await self._source.wait()

    def set_duty_cycle(self, duty_cycle: float) -> None:
        """Set the duty cycle for traffic shaping.

        Controls how often the driver asserts tvalid. A duty cycle of 1.0
        means tvalid is always asserted when data is available. Lower values
        introduce idle cycles between transfers.

        Args:
            duty_cycle: Float between 0.0 and 1.0 (1.0 = always valid)
        """
        if duty_cycle >= 1.0:
            self._source.clear_pause_generator()
        else:
            self._source.set_pause_generator(_make_duty_cycle_generator(duty_cycle))


class Monitor:
    """Wraps cocotbext-axi AxiStreamSink for capturing AXIS transactions.

    Provides an ergonomic interface for receiving data from an AXI-Stream bus
    with optional duty cycle control for backpressure simulation.
    """

    def __init__(
        self,
        dut: Any,
        bus: str | AxiStreamBus,
        clock: Any,
        reset: Any = None,
        reset_active_level: bool = True,
    ) -> None:
        """Initialize the AXIS monitor.

        Args:
            dut: Device under test (cocotb handle)
            bus: AXI-Stream bus prefix string or AxiStreamBus instance
            clock: Clock signal
            reset: Reset signal (optional)
            reset_active_level: True if reset is active-high, False if active-low
        """
        if isinstance(bus, str):
            bus = AxiStreamBus.from_prefix(dut, bus)
        self._sink = AxiStreamSink(
            bus,
            clock,
            reset,
            reset_active_level=reset_active_level,
        )
        self._clock = clock

    async def recv(self, timeout_ns: int | None = None) -> bytes:
        """Receive data from the AXIS bus.

        Args:
            timeout_ns: Timeout in nanoseconds (None for no timeout)

        Returns:
            Received bytes (tdata only)

        Raises:
            cocotb.result.SimTimeoutError: If timeout expires
        """
        frame = await self.recv_raw(timeout_ns)
        return bytes(frame.tdata)

    async def recv_frame(self, timeout_ns: int | None = None) -> bytes:
        """Receive a complete frame (waits for tlast).

        This is equivalent to recv() since cocotbext-axi frames
        are delineated by tlast by default.

        Args:
            timeout_ns: Timeout in nanoseconds (None for no timeout)

        Returns:
            Received frame bytes
        """
        return await self.recv(timeout_ns)

    async def recv_raw(self, timeout_ns: int | None = None) -> AxiStreamFrame:
        """Receive a complete frame with all metadata.

        Returns the full AxiStreamFrame including tdata, tkeep, tid, tdest, tuser.

        Args:
            timeout_ns: Timeout in nanoseconds (None for no timeout)

        Returns:
            Full AxiStreamFrame with all sideband signals

        Raises:
            cocotb.result.SimTimeoutError: If timeout expires
        """
        if timeout_ns is not None:
            frame = await with_timeout(
                self._sink.recv(),
                timeout_ns,
                timeout_unit="ns",
            )
        else:
            frame = await self._sink.recv()
        return frame

    def empty(self) -> bool:
        """Check if receive queue is empty."""
        return bool(self._sink.empty())

    def count(self) -> int:
        """Return number of frames in receive queue."""
        return int(self._sink.count())

    def set_duty_cycle(self, duty_cycle: float) -> None:
        """Set the duty cycle for backpressure control.

        Controls how often the monitor asserts tready. A duty cycle of 1.0
        means tready is always asserted. Lower values introduce backpressure
        by stalling tready.

        Args:
            duty_cycle: Float between 0.0 and 1.0 (1.0 = always ready)
        """
        if duty_cycle >= 1.0:
            self._sink.clear_pause_generator()
        else:
            self._sink.set_pause_generator(_make_duty_cycle_generator(duty_cycle))


class Scoreboard:
    """Comparison scoreboard for AXI-Stream verification.

    Supports both byte-level comparison (simple) and frame-level comparison
    (with tkeep, tid, tdest, tuser metadata).
    """

    def __init__(
        self,
        name: str = "Scoreboard",
        compare_mode: Literal["bytes", "frame"] = "bytes",
    ) -> None:
        """Initialize the scoreboard.

        Args:
            name: Name for logging purposes
            compare_mode: "bytes" for tdata-only comparison,
                         "frame" for full metadata comparison
        """
        self._name = name
        self._compare_mode = compare_mode
        self._expected: deque[bytes | AxiStreamFrame] = deque()
        self._actual: deque[bytes | AxiStreamFrame] = deque()
        self._matches = 0
        self._mismatches = 0
        self._errors: list[str] = []

    def add_expected(self, data: bytes | AxiStreamFrame) -> None:
        """Add expected data to the scoreboard.

        Args:
            data: Expected bytes or AxiStreamFrame
        """
        self._expected.append(data)

    def add_actual(self, data: bytes | AxiStreamFrame) -> None:
        """Add actual data to the scoreboard and compare with expected.

        Automatically compares against the next expected value in the queue.

        Args:
            data: Actual received bytes or AxiStreamFrame
        """
        self._actual.append(data)

        if self._expected:
            expected = self._expected.popleft()
            if self._compare(data, expected):
                self._matches += 1
                cocotb.log.info(f"[{self._name}] Match: {self._format(data)}")
            else:
                self._mismatches += 1
                error_msg = (
                    f"Mismatch: expected {self._format(expected)}, " f"got {self._format(data)}"
                )
                self._errors.append(error_msg)
                cocotb.log.error(f"[{self._name}] {error_msg}")
        else:
            self._mismatches += 1
            error_msg = f"Unexpected data received: {self._format(data)}"
            self._errors.append(error_msg)
            cocotb.log.error(f"[{self._name}] {error_msg}")

    def _compare(self, actual: bytes | AxiStreamFrame, expected: bytes | AxiStreamFrame) -> bool:
        """Compare actual vs expected based on compare_mode."""
        if self._compare_mode == "bytes":
            actual_bytes = bytes(actual.tdata) if isinstance(actual, AxiStreamFrame) else actual
            expected_bytes = (
                bytes(expected.tdata) if isinstance(expected, AxiStreamFrame) else expected
            )
            return actual_bytes == expected_bytes
        else:
            # Frame mode: compare all fields
            if not isinstance(actual, AxiStreamFrame):
                actual = AxiStreamFrame(tdata=actual)
            if not isinstance(expected, AxiStreamFrame):
                expected = AxiStreamFrame(tdata=expected)

            return (
                bytes(actual.tdata) == bytes(expected.tdata)
                and actual.tkeep == expected.tkeep
                and actual.tid == expected.tid
                and actual.tdest == expected.tdest
                and actual.tuser == expected.tuser
            )

    def _format(self, data: bytes | AxiStreamFrame) -> str:
        """Format data for logging."""
        if isinstance(data, AxiStreamFrame):
            parts = [f"tdata={bytes(data.tdata).hex()}"]
            if data.tid is not None:
                parts.append(f"tid={data.tid}")
            if data.tdest is not None:
                parts.append(f"tdest={data.tdest}")
            if data.tkeep is not None:
                parts.append(f"tkeep={data.tkeep}")
            if data.tuser is not None:
                parts.append(f"tuser={data.tuser}")
            return f"Frame({', '.join(parts)})"
        return data.hex()

    def check(self) -> bool:
        """Check if all expected data was received and matched.

        Returns:
            True if all matches, no mismatches, and no pending expected data
        """
        if self._expected:
            for exp in self._expected:
                error_msg = f"Expected data not received: {self._format(exp)}"
                self._errors.append(error_msg)
                cocotb.log.error(f"[{self._name}] {error_msg}")
            self._mismatches += len(self._expected)
            self._expected.clear()

        return self._mismatches == 0

    def report(self) -> str:
        """Generate a human-readable summary report.

        Returns:
            Summary string
        """
        lines = [
            f"=== {self._name} Report ===",
            f"Matches: {self._matches}",
            f"Mismatches: {self._mismatches}",
        ]
        if self._errors:
            lines.append("Errors:")
            for error in self._errors:
                lines.append(f"  - {error}")
        lines.append(f"Status: {'PASS' if self._mismatches == 0 else 'FAIL'}")
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all state."""
        self._expected.clear()
        self._actual.clear()
        self._matches = 0
        self._mismatches = 0
        self._errors.clear()

    @property
    def matches(self) -> int:
        """Number of successful matches."""
        return self._matches

    @property
    def mismatches(self) -> int:
        """Number of mismatches."""
        return self._mismatches
