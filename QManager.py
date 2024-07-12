import pika
from pika.credentials import PlainCredentials
import pika.delivery_mode
from constants import (
    RABBITMQ_HOST,
    RABBITMQ_PASS,
    RABBITMQ_PORT,
    RABBITMQ_USER
)

class Queue:
    
    def __init__(self, queue_name: str, durable: bool = True) -> None:
        self.queue_name = queue_name
        self.rabbit_mquser = RABBITMQ_USER
        self.rabbit_mqpass = RABBITMQ_PASS
        self.rabbit_mqport = RABBITMQ_PORT
        self.rabbit_mqhost = RABBITMQ_HOST

        self.conn = pika.BlockingConnection(pika.ConnectionParameters(
            host=self.rabbit_mqhost,
            port=self.rabbit_mqport,
            credentials=PlainCredentials(username=self.rabbit_mquser, password=self.rabbit_mqpass)
        ))

        self.channel = self.conn.channel()
        self.channel.queue_declare(queue_name, durable=durable)

    def close(self):
        self.conn.close()
        return self
    

class Publisher(Queue):
    def __init__(self, queue_name: str, durable: bool = True) -> None:
        super().__init__(queue_name, durable)

    def publish(self, routing_key: str, body: any, **kwargs):
        self.channel.basic_publish(
            exchange='',
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent),
            **kwargs
        )

        return self
    

class Subscriber(Queue):
    def __init__(self, queue_name: str, durable: bool = True) -> None:
        super().__init__(queue_name, durable)

    def consume(self, callback):
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(self.queue_name, on_message_callback=callback)
        return self
    

    def start(self):
        self.channel.start_consuming()
        return self

    