"""Per-request context (request id) shared between middleware, logging and error handlers."""

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return request_id_var.get()


# Database round trips in this request: [count, seconds]. Set by the middleware outside production and
# reported as a Server-Timing header, so the browser's network panel shows what each call costs.
db_stats_var: ContextVar[list[float] | None] = ContextVar("db_stats", default=None)


def _install_query_timer() -> None:
    import time

    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, "before_cursor_execute")
    def _start(conn, *_args):  # type: ignore[no-untyped-def]
        if db_stats_var.get() is not None:
            conn.info.setdefault("query_start", []).append(time.perf_counter())

    @event.listens_for(Engine, "after_cursor_execute")
    def _end(conn, *_args):  # type: ignore[no-untyped-def]
        stats = db_stats_var.get()
        starts = conn.info.get("query_start")
        if stats is not None and starts:
            stats[0] += 1
            stats[1] += time.perf_counter() - starts.pop()


_install_query_timer()
