from collections import namedtuple

import serial.tools.list_ports as lp

from feed import find_port

P = namedtuple("P", "device description hwid")
ACPI = r"ACPI\PNP0501"


def fake(monkeypatch, ports):
    monkeypatch.setattr(lp, "comports", lambda: ports)


def test_cp210x_found(monkeypatch):
    fake(monkeypatch, [P("COM1", "Communications Port", ACPI),
                       P("COM5", "Silicon Labs CP210x USB to UART Bridge (COM5)", "USB VID:PID=10C4:EA60")])
    assert find_port() == "COM5"


def test_ch340_found(monkeypatch):
    fake(monkeypatch, [P("COM7", "USB-SERIAL CH340 (COM7)", "USB VID:PID=1A86:7523")])
    assert find_port() == "COM7"


def test_ch9102_found_by_vidpid_only(monkeypatch):
    fake(monkeypatch, [P("COM8", "USB Serial Device (COM8)", "USB VID:PID=1A86:55D4")])
    assert find_port() == "COM8"


def test_cp210x_preferred_over_other_bridges(monkeypatch):
    fake(monkeypatch, [P("COM3", "USB-SERIAL CH340", "USB VID:PID=1A86:7523"),
                       P("COM9", "CP210x", "USB VID:PID=10C4:EA60")])
    assert find_port() == "COM9"


def test_single_unknown_usb_serial_port_is_used(monkeypatch):
    fake(monkeypatch, [P("COM4", "USB Serial Device (COM4)", "USB VID:PID=ABCD:0001")])
    assert find_port() == "COM4"


def test_no_usb_ports_gives_none(monkeypatch):
    fake(monkeypatch, [P("COM1", "Communications Port", ACPI)])
    assert find_port() is None
    fake(monkeypatch, [])
    assert find_port() is None
