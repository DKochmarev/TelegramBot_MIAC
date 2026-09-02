from aiogram.fsm.state import State, StatesGroup


class Booking(StatesGroup):
    choosing_date = State()
    entering_start_point = State()
    entering_start_time = State()

    choosing_next_point = State()
    entering_intermediate_address = State()
    entering_intermediate_time = State()
    entering_intermediate_wait = State()

    entering_end_address = State()
    entering_end_time = State()
    confirming_booking = State()


class AllDayBooking(StatesGroup):
    choosing_date = State()
    entering_comment = State()


class ViewSchedule(StatesGroup):
    choosing_date = State()
