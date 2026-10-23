"""Gradio UI: chat on the left, pending bookings and the Confirm button on the right.

Confirming is a button press handled by plain code, not something the model can do.
The model can only start a booking; a person approves it.
"""

from __future__ import annotations

from typing import Any

import gradio as gr

from .assistant import Assistant
from .store import BookingError, FareStore

NO_PENDING = "No bookings waiting for confirmation."


def pending_table(store: FareStore) -> list[list[Any]]:
    return [[b.ref, b.passenger, b.city.title(), f"${b.price_usd:,}"] for b in store.pending()]


def pending_refs(store: FareStore) -> list[str]:
    return [b.ref for b in store.pending()]


def confirm_booking(store: FareStore, ref: str | None) -> str:
    if not ref:
        return "Choose a booking to confirm."
    try:
        booking = store.confirm(ref)
    except BookingError as exc:
        return str(exc)
    return (
        f"Confirmed {booking.ref}: {booking.passenger} to {booking.city.title()}, "
        f"${booking.price_usd:,} return."
    )


def cancel_booking(store: FareStore, ref: str | None) -> str:
    if not ref:
        return "Choose a booking to cancel."
    try:
        booking = store.cancel(ref)
    except BookingError as exc:
        return str(exc)
    return f"Cancelled {booking.ref}."


def build_ui(assistant: Assistant, store: FareStore, *, title: str = "FlightAI") -> gr.Blocks:
    def refresh() -> tuple[list[list[Any]], Any]:
        refs = pending_refs(store)
        return pending_table(store), gr.update(choices=refs, value=refs[-1] if refs else None)

    async def respond(message: str, history: list[dict[str, Any]]):
        if not message.strip():
            return "", history, *refresh()
        reply = await assistant.reply(history, message)
        history = [
            *history,
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply.text},
        ]
        return "", history, *refresh()

    def on_confirm(ref: str | None):
        status = confirm_booking(store, ref)
        return status, *refresh()

    def on_cancel(ref: str | None):
        status = cancel_booking(store, ref)
        return status, *refresh()

    with gr.Blocks(title=title) as ui:
        gr.Markdown(f"# {title} support\nAsk about fares, or book a return flight.")
        with gr.Row():
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(height=480, label="Chat")
                message = gr.Textbox(
                    label="Your message", placeholder="How much is a flight to Tokyo?"
                )
            with gr.Column(scale=2):
                table = gr.Dataframe(
                    headers=["Ref", "Passenger", "City", "Fare"],
                    value=pending_table(store),
                    label="Waiting for your confirmation",
                    interactive=False,
                )
                refs = pending_refs(store)
                choice = gr.Dropdown(
                    choices=refs,
                    value=refs[-1] if refs else None,
                    label="Booking",
                    allow_custom_value=False,
                )
                with gr.Row():
                    confirm = gr.Button("Confirm booking", variant="primary")
                    cancel = gr.Button("Cancel booking")
                status = gr.Markdown(NO_PENDING if not refs else "")

        message.submit(respond, [message, chatbot], [message, chatbot, table, choice])
        confirm.click(on_confirm, [choice], [status, table, choice])
        cancel.click(on_cancel, [choice], [status, table, choice])
    return ui
