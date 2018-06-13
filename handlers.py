import json

import tornado
import tornado.web
import tornado.websocket

from tornado.log import gen_log


class FeedHandler(tornado.web.RequestHandler):

	def get(self):
		self.render('templates/subscriber.html')


class MainHandler(tornado.web.RequestHandler):
	def get(self):
		self.write("Hello, world")


class FeedWebSocketHandler(tornado.websocket.WebSocketHandler):
	subscribed_channels = None

	def check_origin(self, origin):
		return True

	def open(self, *args, **kwargs):
		gen_log.debug("SDFSDFSDS")
		self.application.pika_connector.add_subscriber(self)
		gen_log.info("WebSocket opened")

	def on_close(self):
		gen_log.info("WebSocket closed")
		self.application.pika_connector.remove_subscriber(self)

	def has_subscribed_to(self, collection_name):
		if self.subscribed_channels is None:
			return True
		else:
			return collection_name in self.subscribed_channels

	def subscribe(self, collection_name):
		if self.subscribed_channels is None:
			self.subscribed_channels = []
		if collection_name not in self.subscribed_channels:
			self.subscribed_channels.append(collection_name)

	def unsubscribe(self, collection_name):
		if self.subscribed_channels:
			if collection_name in self.subscribed_channels:
				self.subscribed_channels.remove(collection_name)

	def update_subscriptions(self, collection_list):
		self.subscribed_channels = collection_list

	def on_message(self, message):
		message_dict = json.loads(message)
		if message_dict.get('subscribed_channels', None):
			self.update_subscriptions(message_dict['subscribed_channels'])
		gen_log.info("message: {}".format(message))
