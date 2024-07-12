from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from worker import ChargePoint, CSMS, Instance
from typing import Optional
from datetime import datetime, timedelta
import random
from dashboard import dashboard as DashboardRouter
from dbManager import JsonDB, Query

app = FastAPI(title='EV Remote Controller API')

app.include_router(DashboardRouter)


app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StartRemoteTrxModel(BaseModel):
    charge_box_name: str
    connector_id: int
    trx: int


class StopRemoteTrxModel(BaseModel):
    trx: int


class ReserveModel(BaseModel):
    user_id: str
    charge_box_name: str = 'cp-006'
    connector_id: int


class ChargingProfile(BaseModel):
    trx: Optional[int] = None
    connector_id: int
    charge_box: str = 'cp-006'


class ClearChargingProfile(BaseModel):
    charge_box: str = 'cp-006'
    connector_id: int
    profile_id: int = 100


class ReserveModel(BaseModel):
    connector_id: int = 1
    reservation_id: int
    charge_box: str = 'cp-006'


class CancelReservationModel(BaseModel):
    charge_box: str = 'cp-006'
    connector_id: int = 1
    reservation_id: int

REMOTE_TAG = ['Remote Transaction']
@app.post('/start-remote-transaction', tags=REMOTE_TAG)
async def start_remote_transaction(req: StartRemoteTrxModel, cp: CSMS = Depends(CSMS)):
    return await cp.start_remote_transaction(req.trx, req.charge_box_name, req.connector_id)


@app.post('/stop-remote-transaction', tags=REMOTE_TAG)
async def stop_remote_transaction(req: StopRemoteTrxModel, cp: CSMS = Depends(CSMS)):
    return await cp.stop_remote_transaction(charger_box='cp-006', transaction_id=req.trx)


class StopRemoteTrxAutoModel(BaseModel):
    charge_box: str
    connector_id: int
    transaction_id: int

@app.post('/stop-remote-transaction-auto', tags=REMOTE_TAG)
async def stop_remote_transaction(req: StopRemoteTrxAutoModel, cp: CSMS = Depends(CSMS)):
    return await cp.stop_remote_transaction(charger_box=req.charge_box, transaction_id=req.transaction_id)


@app.post('/book', tags=REMOTE_TAG)
async def reserve_now(req: ReserveModel, cp: CSMS = Depends(CSMS)):
    reserve_id = random.randint(111111, 999999)
    res = await cp.reserve(
        connector_id=req.connector_id,
        expiry_date=(datetime.now() + timedelta(minutes=1)).isoformat(),
        id_tag=str(reserve_id),
        reservation_id=reserve_id,
        charge_box=req.charge_box
    )
    return {'response': await res, 'reservation_id': reserve_id}


@app.post('/cancel-booking', tags=REMOTE_TAG)
async def cancel_reservation(req: CancelReservationModel, cp: CSMS = Depends(CSMS)):
    return await cp.cancel_reservation(
        charge_box=req.charge_box,
        reserveration_id=req.reservation_id,
        connector_id=req.connector_id
    )


# @app.post('/set-charging-profile', tags=['Profile'])
# async def set_charging_profile(req: ChargingProfile, cp: CSMS = Depends(CSMS)):
#     transaction_id = req.trx if req.trx else None
#     return await cp.set_charging_profile(
#         charge_box=req.charge_box,
#         connector_id=req.connector_id,
#         transaction_id=transaction_id
#     )


# @app.post('/clear-charging-profile', tags=['Profile'])
# async def clear_charging_profile(req: ClearChargingProfile, cp: CSMS = Depends(CSMS)):
#     return await cp.clear_charging_profile(
#         charge_box=req.charge_box,
#         connector_id=req.connector_id,
#         profile_id=req.profile_id
#     )


# @app.post('/reset', tags=REMOTE_TAG)
# async def reset_charge_box(cp: CSMS = Depends(CSMS)):
#     return await cp.reset('cp-006')


@app.get('/chargebox/{charger}/{connector}', tags=['Demo Page'])
async def get_chargebox_status(charger: str, connector: int):
    model = JsonDB()
    ChargeBox = Query()
    q = model.db.search(ChargeBox.name == charger)
    result = q[0]['connectors'][f'connector_{connector}']
    return result


class ConfigurationModel(BaseModel):
    charge_box: str

@app.post('/configuration', tags=['Configuration'])
async def get_configuration(req: ConfigurationModel, cp: CSMS = Depends(CSMS)):
    return await cp.get_configuration(req.charge_box)


class ChangeConfigurationModel(BaseModel):
    charge_box: str
    key: str
    value: Optional[str|int]

@app.post('/change-configuration', tags=['Configuration'])
async def change_configuration(req: ChangeConfigurationModel, cp: CSMS = Depends(CSMS)):
    return await cp.change_configuration(charge_box=req.charge_box, key=req.key, value=req.value)


class SocketAdapter:
    def __init__(self, websocket: WebSocket):
        self._ws = websocket

    async def recv(self) -> str:
        return await self._ws.receive_text()

    async def send(self, msg) -> str:
        await self._ws.send_text(msg)


@app.websocket('/ws/{client_id}')
async def websocket_handler(websocket: WebSocket, client_id: str):
    await websocket.accept(subprotocol='ocpp1.6')
    cp = ChargePoint(client_id, SocketAdapter(websocket))
    Instance.objects[client_id] = cp
    try:
        await cp.start()
    except Exception as e:
        print(e)


@app.websocket('/ws/channel/{channel}')
async def ev_channel_handler(websocket: WebSocket, channel: str):
    import json
    pref, channel = channel.split('-')
    await websocket.accept()
    if pref == 'request' and channel not in Instance.objects:
        Instance.objects[channel] = websocket

    data = await websocket.receive_json()
    data['channel'] = channel
    if pref == 'response' and channel in Instance.objects:
        await Instance.objects[channel].send_json(json.loads(data['response']))
        
