from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, Callable, Literal, overload

from anyio import create_task_group

from reactpy.core.types import EventHandlerFunc, EventHandlerType


@overload
def event(
    function: Callable[..., Any],
    *,
    stop_propagation: bool = ...,
    prevent_default: bool = ...,
) -> EventHandler: ...


@overload
def event(
    function: Literal[None] = ...,
    *,
    stop_propagation: bool = ...,
    prevent_default: bool = ...,
) -> Callable[[Callable[..., Any]], EventHandler]: ...


def event(
    function: Callable[..., Any] | None = None,
    *,
    stop_propagation: bool = False,
    prevent_default: bool = False,
) -> EventHandler | Callable[[Callable[..., Any]], EventHandler]:
    """A decorator for constructing an :class:`EventHandler`.

    While you're always free to add callbacks by assigning them to an element's attributes

    .. code-block:: python

        element = reactpy.html.button({"onClick": my_callback})

    You may want the ability to prevent the default action associated with the event
    from taking place, or stopping the event from propagating up the DOM. This decorator
    allows you to add that functionality to your callbacks.

    .. code-block:: python

        @event(stop_propagation=True, prevent_default=True)
        def my_callback(*data):
            ...

        element = reactpy.html.button({"onClick": my_callback})

    Parameters:
        function:
            A function or coroutine responsible for handling the event.
        stop_propagation:
            Block the event from propagating further up the DOM.
        prevent_default:
            Stops the default actional associate with the event from taking place.
    """

    def setup(function: Callable[..., Any]) -> EventHandler:
        return EventHandler(
            to_event_handler_function(function, positional_args=True),
            stop_propagation,
            prevent_default,
        )

    if function is not None:
        return setup(function)
    else:
        return setup


class EventHandler:
    """Turn a function or coroutine into an event handler

    Parameters:
        function:
            The function or coroutine which handles the event.
        stop_propagation:
            Block the event from propagating further up the DOM.
        prevent_default:
            Stops the default action associate with the event from taking place.
        target:
            A unique identifier for this event handler (auto-generated by default)
    """

    __slots__ = (
        "__weakref__",
        "function",
        "prevent_default",
        "stop_propagation",
        "target",
    )

    def __init__(
        self,
        function: EventHandlerFunc,
        stop_propagation: bool = False,
        prevent_default: bool = False,
        target: str | None = None,
    ) -> None:
        self.function = to_event_handler_function(function, positional_args=False)
        self.prevent_default = prevent_default
        self.stop_propagation = stop_propagation
        self.target = target

    def __eq__(self, other: Any) -> bool:
        undefined = object()
        for attr in (
            "function",
            "prevent_default",
            "stop_propagation",
            "target",
        ):
            if not attr.startswith("_"):
                if not getattr(other, attr, undefined) == getattr(self, attr):
                    return False
        return True

    def __repr__(self) -> str:
        public_names = [name for name in self.__slots__ if not name.startswith("_")]
        items = ", ".join([f"{n}={getattr(self, n)!r}" for n in public_names])
        return f"{type(self).__name__}({items})"


def to_event_handler_function(
    function: Callable[..., Any],
    positional_args: bool = True,
) -> EventHandlerFunc:
    """Make a :data:`~reactpy.core.proto.EventHandlerFunc` from a function or coroutine

    Parameters:
        function:
            A function or coroutine accepting a number of positional arguments.
        positional_args:
            Whether to pass the event parameters a positional args or as a list.
    """
    if positional_args:
        if asyncio.iscoroutinefunction(function):

            async def wrapper(data: Sequence[Any]) -> None:
                await function(*data)

        else:

            async def wrapper(data: Sequence[Any]) -> None:
                function(*data)

        return wrapper
    elif not asyncio.iscoroutinefunction(function):

        async def wrapper(data: Sequence[Any]) -> None:
            function(data)

        return wrapper
    else:
        return function


def merge_event_handlers(
    event_handlers: Sequence[EventHandlerType],
) -> EventHandlerType:
    """Merge multiple event handlers into one

    Raises a ValueError if any handlers have conflicting
    :attr:`~reactpy.core.proto.EventHandlerType.stop_propagation` or
    :attr:`~reactpy.core.proto.EventHandlerType.prevent_default` attributes.
    """
    if not event_handlers:
        msg = "No event handlers to merge"
        raise ValueError(msg)
    elif len(event_handlers) == 1:
        return event_handlers[0]

    first_handler = event_handlers[0]

    stop_propagation = first_handler.stop_propagation
    prevent_default = first_handler.prevent_default
    target = first_handler.target

    for handler in event_handlers:
        if (
            handler.stop_propagation != stop_propagation
            or handler.prevent_default != prevent_default
            or handler.target != target
        ):
            msg = "Cannot merge handlers - 'stop_propagation', 'prevent_default' or 'target' mismatch."
            raise ValueError(msg)

    return EventHandler(
        merge_event_handler_funcs([h.function for h in event_handlers]),
        stop_propagation,
        prevent_default,
        target,
    )


def merge_event_handler_funcs(
    functions: Sequence[EventHandlerFunc],
) -> EventHandlerFunc:
    """Make one event handler function from many"""
    if not functions:
        msg = "No event handler functions to merge"
        raise ValueError(msg)
    elif len(functions) == 1:
        return functions[0]

    async def await_all_event_handlers(data: Sequence[Any]) -> None:
        async with create_task_group() as group:
            for func in functions:
                group.start_soon(func, data)

    return await_all_event_handlers