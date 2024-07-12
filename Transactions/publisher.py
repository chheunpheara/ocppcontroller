import random
from Q import Queue
import json

senders = []
receivers = []
transactions = {}

q = Queue('PaymentTransaction')

def create_senders(n = 10):
	for i in range(n):
		sender = random.randint(111111, 555555)
		senders.append(sender)
	return senders


def create_receivers(n = 10):
	for i in range(n):
		receiver = random.randint(666666, 999999)
		receivers.append(receiver)

	return receivers


def generate_transaction(n = 10):
	import sys
	from datetime import datetime
	if not (senders or receivers):
		return 'No sender or receiver'

	nn = input('Amt of trx: ')
	try:
		nn = int(nn)
	except ValueError:
		print('Value Error! Try again')
		sys.exit(0)

	n = nn
	count = 0
	for i in range(n):
		today = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
		for s in senders:
			for r in receivers:
				amount = round(random.uniform(random.randint(11, 999), 2), 2)
				trx = random.randint(11111111, 99999999)
				transactions = {f'{trx}': {'sender': s, 'receiver': r, 'amount': amount, 'datetime': today}}
				q.publish(
					routing_key='PaymentTransaction',
					body=json.dumps(transactions)
				)
		count += 1
	# q.close()

	print(f'Total transactions generated: {count}')



def menu():
	opts = f'1. Create Sender\n2. Create Receivers\n3. Generate Transactions'

	return opts


if __name__ == '__main__':
	import sys
	menus = menu()

	print(menus)
	try:
		while True:
			opt = input('Enter option: ')
			try:
				opt = int(opt)
			except ValueError:
				print(f'{opt} is not considered as number')
				continue

			match opt:
				case 1:
					print('Generating senders...')
					print(create_senders())
				case 2:
					print('Generating receivers...')
					print(create_receivers())
				case 3:
					print('Generating Transactions...')
					generate_transaction()
					senders = receivers = []
				case _: break
	except KeyboardInterrupt:
		# print('Exiting program')
		sys.exit(0)
