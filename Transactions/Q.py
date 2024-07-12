import pika
from pika.credentials import PlainCredentials
from constants import (
	RABBITMQ_PORT,
	RABBITMQ_HOST,
	RABBITMQ_PASS,
	RABBITMQ_USER
)

class Queue():
	def __init__(self, q):
		self.conn = pika.BlockingConnection(pika.ConnectionParameters(
			host=RABBITMQ_HOST,
			port=RABBITMQ_PORT,
			credentials=PlainCredentials(
				username=RABBITMQ_USER,
				password=RABBITMQ_PASS
			)
		))

		self.channel = self.conn.channel()
		self.channel.queue_declare(queue=q, durable=False)
		self.q = q


	def publish(self, routing_key: str, body: any, **kwargs):
		self.channel.basic_publish(
            exchange='',
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent),
            **kwargs
        )


	def consume(self, callback):
		self.channel.basic_qos(prefetch_count=100)
		self.channel.basic_consume(self.q, on_message_callback=callback)
		self.channel.start_consuming()
	

	def close(self):
		self.conn.close()
