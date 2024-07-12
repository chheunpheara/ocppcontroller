import asyncio
from websockets.server import serve
import json


async def message(websocket):
    sms = await websocket.recv()
    data = json.loads(sms)
    for i, v in data.items():
        # print(f'Trx: {i}, Amount: {v["amount"]}')
        print(f"{v['sampled_value'][0]['value']} {v['sampled_value'][0]['unit']}")
        


async def main():
    async with(serve(message, 'localhost', 3100)):
        print('Running server on http://localhost:3100')
        await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())