from __future__ import annotations

from importlib import import_module
from unittest.mock import patch

from ..addon_utils import patched_addon_state
from ..collection_utils import temporary_collection


def test_run_chunked_yields_between_batches_and_reports_progress() -> None:
    """Large work should be split and scheduled without coupling the runner to UI code."""

    with temporary_collection() as col:
        with patched_addon_state(col) as addon:
            runner = import_module(f"{addon.__name__}.sibpush.processing.chunked_runner")
            chunks: list[list[int]] = []
            progress: list[tuple[int, int]] = []
            scheduled: list[tuple[int, object]] = []
            events: list[str] = []

            def fake_single_shot(delay_ms: int, callback: object) -> None:
                scheduled.append((delay_ms, callback))

            def process_chunk(chunk: object) -> None:
                chunks.append(list(chunk))  # type: ignore[arg-type]

            with patch.object(runner.QTimer, "singleShot", side_effect=fake_single_shot):
                runner.run_chunked(
                    [1, 2, 3, 4, 5],
                    process_chunk,
                    batch_size=2,
                    pause_ms=37,
                    jitter=False,
                    on_progress=lambda processed, total: progress.append((processed, total)),
                    on_complete=lambda: events.append("complete"),
                    on_success=lambda: events.append("success"),
                )

                assert chunks == [[1, 2]]
                assert progress == [(2, 5)]
                assert [(delay, callable(callback)) for delay, callback in scheduled] == [(37, True)]

                while scheduled:
                    _, callback = scheduled.pop(0)
                    callback()  # type: ignore[operator]

            assert chunks == [[1, 2], [3, 4], [5]]
            assert progress == [(2, 5), (4, 5), (5, 5)]
            assert events == ["success", "complete"]


def test_run_chunked_calls_completion_when_processing_fails() -> None:
    """A failed batch must not report success, but cleanup must still run exactly once."""

    with temporary_collection() as col:
        with patched_addon_state(col) as addon:
            runner = import_module(f"{addon.__name__}.sibpush.processing.chunked_runner")
            events: list[str] = []

            def process_chunk(_chunk: object) -> None:
                raise RuntimeError("batch failed")

            try:
                runner.run_chunked(
                    [1],
                    process_chunk,
                    batch_size=1,
                    jitter=False,
                    on_complete=lambda: events.append("complete"),
                    on_success=lambda: events.append("success"),
                )
            except RuntimeError as error:
                assert str(error) == "batch failed"
            else:
                raise AssertionError("expected the batch failure")

            assert events == ["complete"]


def test_run_chunked_stops_before_a_stale_next_batch() -> None:
    """A caller can cancel queued work safely without invoking the success callback."""

    with temporary_collection() as col:
        with patched_addon_state(col) as addon:
            runner = import_module(f"{addon.__name__}.sibpush.processing.chunked_runner")
            processed: list[list[int]] = []
            scheduled: list[object] = []
            events: list[str] = []
            can_continue = True

            def fake_single_shot(_delay_ms: int, callback: object) -> None:
                scheduled.append(callback)

            with patch.object(runner.QTimer, "singleShot", side_effect=fake_single_shot):
                runner.run_chunked(
                    [1, 2, 3],
                    lambda chunk: processed.append(list(chunk)),  # type: ignore[arg-type]
                    batch_size=2,
                    jitter=False,
                    on_complete=lambda: events.append("complete"),
                    on_success=lambda: events.append("success"),
                    should_continue=lambda: can_continue,
                )

                can_continue = False
                assert len(scheduled) == 1
                scheduled.pop(0)()  # type: ignore[operator]

            assert processed == [[1, 2]]
            assert events == ["complete"]


def test_run_chunked_completes_empty_work_as_success() -> None:
    """Empty scans should retain a simple, synchronous completion path."""

    with temporary_collection() as col:
        with patched_addon_state(col) as addon:
            runner = import_module(f"{addon.__name__}.sibpush.processing.chunked_runner")
            events: list[str] = []

            runner.run_chunked(
                [],
                lambda _chunk: events.append("process"),
                batch_size=10,
                on_complete=lambda: events.append("complete"),
                on_success=lambda: events.append("success"),
            )

            assert events == ["success", "complete"]


if __name__ == "__main__":
    test_run_chunked_yields_between_batches_and_reports_progress()
    test_run_chunked_calls_completion_when_processing_fails()
    test_run_chunked_stops_before_a_stale_next_batch()
    test_run_chunked_completes_empty_work_as_success()
