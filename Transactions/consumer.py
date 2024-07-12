from Q import Queue
from websockets.sync.client import connect

q = Queue('PaymentTransaction')

def callback(ch, method, properties, body):
    with connect('ws://localhost:3100') as websocket:
        websocket.send(body)

        ch.basic_ack(delivery_tag = method.delivery_tag)
        print(f'{body}')


q.consume(callback=callback)
q.close()