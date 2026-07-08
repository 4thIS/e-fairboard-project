import asyncio

from tests.conftest import MemoryTransport


async def test_memory_transport_왕복():
    t = MemoryTransport()
    await t.open()
    assert t.opened
    await t.write(b"abc")
    assert bytes(t.tx) == b"abc"
    t.feed(b"xyz")
    assert await t.read() == b"xyz"
    await t.close()
    assert not t.opened


async def test_read는_데이터까지_대기():
    t = MemoryTransport()
    task = asyncio.create_task(t.read())
    await asyncio.sleep(0.01)
    assert not task.done()
    t.feed(b"\x01")
    assert await task == b"\x01"


def test_serial_transport_임포트만_검증():
    from app.bridge.transport import SerialTransport
    st = SerialTransport("/dev/tty.test", baud=921600)
    assert st._port == "/dev/tty.test"   # 실물 연동은 하드웨어 도착 후 통합 검증
