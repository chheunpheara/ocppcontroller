from Transactions.Q import Queue
from websockets.sync.client import connect
from dbManager import JsonDB, Query

q = Queue('ChargingProgress')

def callback(ch, method, properties, body):
    import json
    data = body.decode()
    _data = json.loads(data)
    with connect(f"ws://localhost:3000/ws/channel/response-{_data['channel']}") as websocket:
        model = JsonDB()
        ChargeBox = Query()
        q = model.db.search(ChargeBox.name == _data['charge_box'])
        connector_id = _data['connector_id']
        connectors = q[0]['connectors']
        _data['meter_start'] =  connectors[f'connector_{connector_id}']['meter_start']
        data = json.dumps(_data)
        websocket.send(json.dumps({'response': data}))
        ch.basic_ack(delivery_tag = method.delivery_tag)


q.consume(callback=callback)
q.close()