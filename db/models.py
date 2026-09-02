import enum
from sqlalchemy import (BigInteger, String, Date, Time, Integer, ForeignKey, DateTime, func, Boolean, Enum as SAEnum)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class UserRole(enum.Enum):
    PENDING = "pending"
    EMPLOYEE = "employee"
    DRIVER = "driver"
    ADMIN = "admin"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100))
    username: Mapped[str | None] = mapped_column(String(50))
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.PENDING)

    created_bookings: Mapped[list["Booking"]] = relationship(back_populates="creator", foreign_keys='Booking.user_id')
    assigned_bookings: Mapped[list["Booking"]] = relationship(back_populates="driver", foreign_keys='Booking.driver_id')


class Booking(Base):
    __tablename__ = 'bookings'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.telegram_id'))
    driver_id: Mapped[int | None] = mapped_column(ForeignKey('users.telegram_id'))
    passenger_name: Mapped[str | None] = mapped_column(String(100))
    booking_date: Mapped[Date] = mapped_column(Date)
    booking_type: Mapped[str] = mapped_column(String(20), default='timed')
    comment: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default='pending_driver')
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    creator: Mapped["User"] = relationship(back_populates="created_bookings", foreign_keys=[user_id])
    driver: Mapped["User | None"] = relationship(back_populates="assigned_bookings", foreign_keys=[driver_id])
    waypoints: Mapped[list["Waypoint"]] = relationship(back_populates="booking", cascade="all, delete-orphan")
    participants: Mapped[list["SharedTripParticipant"]] = relationship(
        back_populates="booking",
        cascade="all, delete-orphan"
    )
    allow_sharing: Mapped[bool] = mapped_column(Boolean, default=False, server_default='f')


class Waypoint(Base):
    __tablename__ = 'waypoints'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey('bookings.id'))
    point_type: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(255))
    arrival_time: Mapped[Time | None] = mapped_column(Time)
    departure_time: Mapped[Time | None] = mapped_column(Time)
    wait_minutes: Mapped[int | None] = mapped_column(Integer)
    order_num: Mapped[int] = mapped_column(Integer)
    booking: Mapped["Booking"] = relationship(back_populates="waypoints")


class SharedTripParticipant(Base):
    __tablename__ = 'shared_trip_participants'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey('bookings.id'))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.telegram_id'))
    status: Mapped[str] = mapped_column(String(20), default='pending')
    booking: Mapped["Booking"] = relationship(back_populates="participants")
    user: Mapped["User"] = relationship()