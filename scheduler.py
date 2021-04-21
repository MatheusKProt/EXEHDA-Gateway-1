import json
import time

from main import mcron
from main.driver.init import start as driver_start
from utils import get_configs, get_date, log


class Scheduler:
	def __init__(self, subscribe_stack, publish_stack):
		mcron.init_timer()
		mcron.remove_all()

		self.subscribe_stack = subscribe_stack
		self.publish_stack = publish_stack
		self.scheduler()

	def callback(self, driver, cb_type, uuid, pin = None, write = None, **kwargs):
		def wrapper(callback_id = None, current_time = None, callback_memory = None):
			try:
				device = driver_start(driver, pin, write)
				device.run()
				data = {"uuid": uuid, "data": str(device.read), "type": cb_type, "gathered_at": get_date()}

				if kwargs:
					data.update(kwargs)

				self.publish_stack.insert(json.dumps(data))
			except Exception as e:
				log("Scheduler-callback: {}".format(e))
		return wrapper
	
	def init_driver(self, device):
		driver = device['driver']
		pin = device['pin'] if 'pin' in device else None
		if driver == "temperature":
			driver_start(driver, pin, None).run()

	def scheduler(self):
		configs = get_configs()
		for device in configs['devices']:
			if device['status'] == True and 'operation_time' in device:
				period = device['operation_time']['period']
				if type(period) is int and period is not 0:
					period_steps = set(device['operation_time']['period_steps'])
					pin = device['pin'] if 'pin' in device else None
					self.init_driver(device)
					mcron.insert(period, period_steps, device['uuid'], self.callback(device['driver'], "publication", device['uuid'], pin))
				else:
					log("Scheduler: period of " + device['driver'] + " driver is invalid")
	def start(self):
		print("Gateway operando!")
		configs = get_configs()
		configs.update({"type": "identification", "gathered_at": get_date()})
		self.publish_stack.insert(json.dumps(configs))

		while True:
			try:
				while self.subscribe_stack.length() > 0:
					data = json.loads(self.subscribe_stack.get())
					self.subscribe_stack.delete()
					if 'type' in data:
						subscription_type = data['type']
						configs = get_configs()

						if subscription_type == "operation":
							if 'uuid' in data and 'identifier' in data:
								device = None
								for d in configs['devices']:
									if d['uuid'] == data['uuid']:
										device = d
										break
								if not device:
									break

								if device['status'] == True:
									pin = device['pin'] if 'pin' in device else None
									action = data['action'] if 'action' in data else None

									cb = self.callback(device['driver'], "operation_reply", device['uuid'], pin, action, identifier=data['identifier'])
									cb()
								else:
									data = {"uuid": device['uuid'], "data": "driver_not_enabled", "type": "operation_reply", "gathered_at": get_date(), "identifier": data['identifier']}
									self.publish_stack.insert(json.dumps(data))
							else:
								log("Scheduler: json 'uuid' or 'identifier' field not found")
						elif subscription_type == "acknowledgement":
							configs.update({"type": "identification", "gathered_at": get_date()})
							self.publish_stack.insert(json.dumps(configs))
						else:
							log("Scheduler: subscription type error")
					else:
						log("Scheduler: json 'type' field not found")
				time.sleep(0.5)
			except Exception as e:
				log("Scheduler: {}".format(e))
				self.subscribe_stack.delete()
