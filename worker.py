import asyncio
import logging
import websockets
from datetime import datetime, timedelta
from dbManager import JsonDB, Query

from ocpp.routing import on
from ocpp.v16 import ChargePoint as cp, call_result, call
from ocpp.v16.enums import (
    Action,
    RegistrationStatus,
    RemoteStartStopStatus,
    ResetType,
    ChargingProfilePurposeType,
    ChargingProfileKindType,
    ChargingRateUnitType,
    CancelReservationStatus
)
from websockets.legacy.server import WebSocketServerProtocol
from pydantic import BaseModel, field_validator
from typing import Any
from fastapi import Depends
from ocpp.v16.enums import Action, ChargePointErrorCode, ChargePointStatus
import random

logging.basicConfig(level=logging.INFO)


class ConfigurationView(BaseModel):
    key: str
    value: Any

    @field_validator("value")
    @classmethod
    def validate_value(cls, value):
        """
        :param value:
        :return:
        """
        return value.lower()

class Instance(object):
    objects = {}

class ChargePoint(cp):
    def __init__(self, charger_id, connection, response_timeout=30):
        super().__init__(charger_id, connection, response_timeout)
        self.charger_id = charger_id
        self.trx = random.randint(11111111, 99999999)
        self.connection = connection


    @on(Action.BootNotification)
    async def on_boot_notification(self_, charger_id, reason, **kwargs):
        return call_result.BootNotification(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=RegistrationStatus.accepted,
        )

    # @after(Action.BootNotification)
    # async def after_boot_notification(self_, **kwargs):
    #     logging.info(f"Sending configurations (configurations={self_.charge_point.configurations})")
    #     for conf in self_.charge_point.configurations:
    #         payload = ConfigurationView(key=conf.key, value=conf.value).model_dump()
    #         try:
    #             response = await self_.call(ChangeConfigurationPayload(**payload))
    #             logging.info(f"Sent {ChangeConfigurationPayload(**payload)} (response={response})")
    #         except TimeoutError:
    #             logging.warning(
    #                 f"Exceeded timeout when sending {ChangeConfigurationPayload(**payload)}"
    #             )

    @on(Action.StatusNotification)
    async def on_status_notification(
            self_,
            connector_id: int = Depends(lambda connector_id: connector_id),
            error_code: ChargePointErrorCode = Depends(lambda error_code: error_code),
            status: ChargePointStatus = Depends(lambda status: status),
            **kwargs
    ):
        logging.info(
            f"Accepted '{Action.StatusNotification}' "
            f"(connector_id={connector_id}, "
            f"error_code={error_code}, "
            f"status={status}, "
            f"charge_point_id={self_.charger_id}, "
            f"kwargs={kwargs})"
        )

        model = JsonDB()
        ChargeBox = Query()
        q = model.db.search(ChargeBox.name == self_.charger_id)
        if len(q) > 0:
            connectors = q[0]['connectors']
            if f'connector_{connector_id}' in connectors:
                connectors[f'connector_{connector_id}']['status'] = status 
            else:
                connectors[f'connector_{connector_id}'] = {
                    'status': status,
                    'trx': '',
                    'power': 0,
                    'id': connector_id
                }
            model.db.update({'connectors': connectors})
        else:
            data = {
                'name': self_.charger_id,
                'connectors': {
                    f'connector_{connector_id}': {
                        'status': status,
                        'trx': '',
                        'power': 0,
                        'id': connector_id
                    }
                }
            }
            model.db.insert(data)


        return call_result.StatusNotification()
    

    @on(Action.Authorize)
    async def on_authorize(self_, id_tag):
        return call_result.Authorize(id_tag_info={'status': RegistrationStatus.accepted})
    

    @on(Action.StartTransaction)
    async def on_start_transaction(self_, connector_id, id_tag, meter_start, timestamp, reserveration_id = None):
        logging.info(f'Transaction ID: {id_tag}')
        model = JsonDB()
        ChargeBox = Query()
        q = model.db.search(ChargeBox.name == self_.charger_id)
        connectors = q[0]['connectors']
        connectors[f'connector_{connector_id}']['trx'] = id_tag
        connectors[f'connector_{connector_id}']['meter_start'] = meter_start
        model.db.update({'connectors' : connectors})
        return call_result.StartTransaction(transaction_id=int(id_tag), id_tag_info={'status': 'Accepted'})
    

    @on(Action.StopTransaction)
    async def on_stop_transaction(self_, transaction_id, reason, timestamp, meter_stop):
        return call_result.StopTransaction()
    

    @on(Action.MeterValues)
    async def on_meter_value(self_, connector_id, transaction_id, meter_value):
        from Transactions.Q import Queue
        import json
        result = call_result.MeterValues()
        q = Queue('ChargingProgress')
        q.publish(routing_key='ChargingProgress', body=json.dumps({
            'meter': meter_value[0],
            'channel': transaction_id,
            'connector_id': connector_id,
            'charge_box': self_.charger_id
        }))
        # q.close()
        return result
    

    @on(Action.DataTransfer)
    async def on_data_transfer(self_, vendor_id, message_id, data):
        return call_result.DataTransfer(status='Accepted')
    

    @on(Action.Heartbeat)
    async def on_heart_beat(self_, **kwargs):
        return call_result.Heartbeat(current_time=datetime.now().isoformat())


async def on_connect(websocket: WebSocketServerProtocol, path):
    """ For every new charge point that connects, create a ChargePoint
    instance and start listening for messages.
    """
    try:
        requested_protocols = websocket.request_headers[
            'Sec-WebSocket-Protocol']
    except KeyError:
        logging.info("Client hasn't requested any Subprotocol. "
                 "Closing Connection")
        return await websocket.close()

    if websocket.subprotocol:
        logging.info("Protocols Matched: %s", websocket.subprotocol)
    else:
        # In the websockets lib if no subprotocols are supported by the
        # client and the server, it proceeds without a subprotocol,
        # so we have to manually close the connection.
        logging.warning('Protocols Mismatched | Expected Subprotocols: %s,'
                        ' but client supports  %s | Closing connection',
                        websocket.available_subprotocols,
                        requested_protocols)
        return await websocket.close()

    charge_point_id = path.strip('/')
    cp = ChargePoint(charge_point_id, websocket)
    try:
        # pub = Publisher(charge_point_id)
        # pub.publish(charge_point_id, charge_point_id).close()
        await cp.start()
    except Exception as e:
        logging.error(f'{str(e)}')


class CSMS():
    async def start_remote_transaction(self, id_tag: str, charger_box: str, connector_id: str):
        profile = {
            'chargingProfileId': 100,
            'chargingProfileKind': ChargingProfileKindType.absolute,
            'chargingProfilePurpose': ChargingProfilePurposeType.tx_profile,
            'chargingSchedule': {
                'chargingRateUnit': ChargingRateUnitType.watts,
                'chargingSchedulePeriod': [
                    {'limit': 8.8, 'startPeriod': 0},
                ],
                'duration': 60
            },
            'transactionId': int(id_tag),
            'stackLevel': 0,
            'validFrom': datetime.now().isoformat(),
            'validTo': (datetime.now() + timedelta(minutes=5)).isoformat()
        }
        payload = call.RemoteStartTransaction(
            id_tag=str(id_tag),
            connector_id=connector_id,
            charging_profile=profile
        )
        res = await Instance.objects[charger_box].call(payload)
        if res.status == RemoteStartStopStatus.accepted:
            logging.info('Remote Transaction Started')
            return call_result.RemoteStartTransaction(status=RemoteStartStopStatus.accepted)


    async def stop_remote_transaction(self, charger_box: str, transaction_id):
        payload = call.RemoteStopTransaction(transaction_id=transaction_id)
        res = await Instance.objects[charger_box].call(payload)
        if res.status == RemoteStartStopStatus.accepted:
            logging.info('Remote Transaction has been stopped')
            return call_result.RemoteStopTransaction(status=RemoteStartStopStatus.accepted)


    async def set_charging_profile(self, charge_box: str, connector_id: int, transaction_id: int = None):
        profile = {
            'chargingProfileId': 100,
            'chargingProfileKind': ChargingProfileKindType.absolute,
            'chargingProfilePurpose': ChargingProfilePurposeType.tx_profile,
            'chargingSchedule': {
                'chargingRateUnit': ChargingRateUnitType.watts,
                'chargingSchedulePeriod': [
                    {'limit': 1, 'startPeriod': 0},
                ],
                'duration': 60
            },
            'stackLevel': 0,
            'validFrom': datetime.now().isoformat(),
            'validTo': (datetime.now() + timedelta(minutes=5)).isoformat()
        }
        if transaction_id:
            profile['transactionId'] = transaction_id

        payload = call.SetChargingProfile(
            connector_id=connector_id,
            cs_charging_profiles=profile
        )

        res = await Instance.objects[charge_box].call(payload)

        if res.status == RemoteStartStopStatus.accepted:
            logging.info(f'Charging profile has been set for {charge_box}')


    async def clear_charging_profile(self, charge_box: str, connector_id: int, profile_id: int):
        payload = call.ClearChargingProfile(
            id=profile_id,
            connector_id=connector_id,
            stack_level=0,
            charging_profile_purpose=ChargingProfilePurposeType.tx_profile
        )

        res = await Instance.objects[charge_box].call(payload)

        if res.status == RemoteStartStopStatus.accepted:
            logging.info(f'Charging profile has been cleared for {charge_box}')


    async def reserve(self, charge_box: str, connector_id: int, id_tag: str, expiry_date: str, reservation_id: str):
        payload = call.ReserveNow(
            connector_id=connector_id,
            id_tag=id_tag,
            expiry_date=expiry_date,
            reservation_id=reservation_id
        )

        res = await Instance.objects[charge_box].call(payload)
        if res.status == RemoteStartStopStatus.accepted:
            logging.info(f'Charge box: {charge_box}, Connector: {connector_id} are reserved for {reservation_id}')


    async def cancel_reservation(self, charge_box: str, connector_id: int, reserveration_id: int):
        res = await Instance.objects[charge_box].call(
            call.CancelReservation(
                reservation_id=reserveration_id
            )
        )
        if res.status == CancelReservationStatus.accepted:
            logging.info(f'Reserveration: {reserveration_id} has been canceled')
            return call_result.CancelReservation(status=CancelReservationStatus.accepted)


    async def reset(self, charge_box: str):
        payload = call.Reset(type=ResetType.soft)
        await Instance.objects[charge_box].call(payload)


    async def get_configuration(self, charge_box):
        payload = call.GetConfiguration()
        return await Instance.objects[charge_box].call(payload)
    

    async def change_configuration(self, charge_box, key, value):
        payload = call.ChangeConfiguration(key=key, value=value)
        return await Instance.objects[charge_box].call(payload)


async def main():
    server = await websockets.serve(
        on_connect,
        '0.0.0.0',
        3000,
        create_protocol=WebSocketServerProtocol,
        subprotocols=['ocpp2.0.1', 'ocpp1.6']
    )
    logging.info("WebSocket Server Started")
    await server.wait_closed()

if __name__ == '__main__':
    asyncio.run(main())