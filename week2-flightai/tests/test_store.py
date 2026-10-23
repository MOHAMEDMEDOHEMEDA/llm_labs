import pytest

from week2_flightai.store import BookingError


def test_fare_lookup_ignores_case_and_spacing(store):
    assert store.fare("  LONDON ") == 799
    assert store.fare("Rome") is None


def test_destinations_are_listed_in_title_case(store):
    assert store.destinations() == ["Berlin", "London", "Paris", "Sydney", "Tokyo"]


def test_booking_starts_pending_and_only_confirm_completes_it(store):
    booking = store.request_booking("Tokyo", "  Mona   Hassan ")

    assert booking.status == "pending"
    assert booking.passenger == "Mona Hassan"
    assert booking.price_usd == 1420
    assert booking.ref.startswith("FA-") and len(booking.ref) == 9
    assert store.pending() == [booking]

    confirmed = store.confirm(booking.ref)

    assert confirmed.status == "confirmed"
    assert store.pending() == []


def test_a_booking_cannot_be_confirmed_twice_or_after_cancelling(store):
    first = store.request_booking("Paris", "Ali")
    store.confirm(first.ref)
    with pytest.raises(BookingError, match="already confirmed"):
        store.confirm(first.ref)

    second = store.request_booking("Paris", "Ali")
    store.cancel(second.ref)
    with pytest.raises(BookingError, match="already cancelled"):
        store.confirm(second.ref)


@pytest.mark.parametrize(
    ("city", "passenger", "message"),
    [("Rome", "Ali", "don't fly to Rome"), ("Paris", "   ", "passenger name")],
)
def test_bad_booking_requests_are_refused(store, city, passenger, message):
    with pytest.raises(BookingError, match=message):
        store.request_booking(city, passenger)


def test_unknown_reference_is_reported(store):
    with pytest.raises(BookingError, match="No booking with reference FA-NOPE00"):
        store.confirm("FA-NOPE00")


def test_city_names_cannot_inject_sql(store):
    assert store.fare("london' OR '1'='1") is None
    assert store.destinations()  # table still intact
