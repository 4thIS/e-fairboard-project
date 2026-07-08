import asyncio

from app.transport.virtual import virtual_pair


async def test_write_on_a_is_read_on_b():
    a, b = virtual_pair()
    await a.write(b"\x01\x02")
    assert await b.read() == b"\x01\x02"


async def test_duplex_both_directions():
    a, b = virtual_pair()
    await a.write(b"ping")
    await b.write(b"pong")
    assert await b.read() == b"ping"
    assert await a.read() == b"pong"


async def test_read_waits_until_data():
    a, b = virtual_pair()

    async def delayed_write():
        await asyncio.sleep(0.01)
        await a.write(b"x")

    task = asyncio.create_task(delayed_write())
    assert await asyncio.wait_for(b.read(), timeout=1.0) == b"x"
    await task
