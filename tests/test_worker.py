import time
from sdr_studio.worker import ReceiverWorker


def test_worker_simulates_and_stops_cleanly():
    frames, messages, ended = [], [], []
    rx = ReceiverWorker('Demo (geen hardware)', 145_500_000, 2_400_000,
                        'NFM', -90, .5, None,
                        lambda *args: frames.append(args),
                        messages.append, lambda: ended.append(True))
    rx.start()
    time.sleep(.25)
    rx.command('frequency', 145_600_000)
    rx.command('mode', 'AM')
    rx.command('scan', [{'frequency': 145_500_000, 'mode': 'NFM'}])
    time.sleep(.25)
    rx.stop()
    rx.join(timeout=3)
    assert not rx.is_alive()
    assert ended
    assert frames
    assert not any('FOUT:' in m for m in messages)
