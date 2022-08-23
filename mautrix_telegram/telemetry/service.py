# mautrix-telegram - A Matrix-Telegram puppeting bridge
# Copyright (C) 2021 Tulir Asokan
# Copyright (C) 2022 New Vector Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
from __future__ import annotations

from typing import TYPE_CHECKING
import logging
import time

from attr import dataclass

from mautrix.client import ClientAPI
from mautrix.errors import MNotFound
from mautrix.types import EventType, RoomID, SerializableAttrs, SerializerError

from .types import TELEMETRY_TYPE, TelemetryData, TelemetryDataRMAU, TelemetryEvent

if TYPE_CHECKING:
    from ..__main__ import TelegramBridge

TELEMETRY_BASE_TYPE_NAME = f"{TELEMETRY_TYPE}.telemetry"
TELEMETRY_ROOM_TYPE_NAME = f"{TELEMETRY_BASE_TYPE_NAME}.storage.room"
TELEMETRY_EVENT_TYPE_NAME = f"{TELEMETRY_BASE_TYPE_NAME}.activity"

TelemetryEventType = EventType.find(TELEMETRY_EVENT_TYPE_NAME, EventType.Class.MESSAGE)


@dataclass
class TelemetryRoomAccountDataEventContent(SerializableAttrs):
    room_id: RoomID


class TelemetryService:
    log: logging.Logger = logging.getLogger("mau.telemetry")
    _instance_id: str
    _hostname: str
    _matrix_client: ClientAPI

    _endpoint: str | None = None
    _retry_count: int | None = None
    _retry_interval: int | None = None

    _telemetry_room_id: RoomID | None = None

    def __init__(self, bridge: TelegramBridge, instance_id: str) -> None:
        self._instance_id = instance_id
        self._hostname = bridge.az.domain
        self._matrix_client = bridge.az.intent

        self._endpoint = bridge.config["telemetry._endpoint"]
        self._retry_count = bridge.config["telemetry._endpoint"]
        self._retry_interval = bridge.config["telemetry._endpoint"]

    async def _load_storage_room(self) -> RoomID:
        if self._telemetry_room_id:
            return self._telemetry_room_id

        try:
            account_data = TelemetryRoomAccountDataEventContent.deserialize(
                await self._matrix_client.get_account_data(TELEMETRY_ROOM_TYPE_NAME)
            )
            room_id = account_data.room_id
        except (MNotFound, SerializerError):
            room_id = await self._matrix_client.create_room(
                creation_content={"type": TELEMETRY_ROOM_TYPE_NAME}
            )
            await self._matrix_client.set_account_data(
                TELEMETRY_ROOM_TYPE_NAME, TelemetryRoomAccountDataEventContent(room_id)
            )
        self._telemetry_room_id = room_id
        return room_id

    async def send_telemetry(
        self, active_users: int, current_ms: float = time.time() * 1000
    ) -> None:
        payload = TelemetryEvent(
            self._instance_id,
            self._hostname,
            int(current_ms),
            TelemetryData(
                TelemetryDataRMAU(
                    allUsers=active_users,
                )
            ),
        )
        self.log.debug(f"Sending telemetry: {payload}")

        try:
            room_id = await self._load_storage_room()
            await self._matrix_client.send_message_event(room_id, TelemetryEventType, payload)
        except:
            self.log.exception("Failed to record telemetry in Matrix")
