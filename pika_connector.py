from pika import adapters
import pika
from tornado.log import gen_log
import json


class PikaConnector(object):
	"""This is an example consumer that will handle unexpected interactions
	with RabbitMQ such as channel and connection closures.

	If RabbitMQ closes the connection, it will reopen it. You should
	look at the output, as there are limited reasons why the connection may
	be closed, which usually are tied to permission related issues or
	socket timeouts.

	If the channel is closed, it will indicate a problem with one of the
	commands that were issued and that should surface in the output as well.

	"""
	EXCHANGE = 'test-exchange'
	EXCHANGE_TYPE = 'fanout'
	QUEUE = 'text'

	def __init__(self, io_loop, db_connector, rabbitmq_address=None):
		"""Create a new instance of the consumer class, passing in the AMQP
		URL used to connect to RabbitMQ.

		:param str rabbitmq_address: The AMQP address to connect with

		"""
		self.io_loop = io_loop
		self.db_connector = db_connector
		self.collections = None
		self._connection = None
		self._channel = None
		self._closing = False
		self._consumer_tag = None
		# self._url = amqp_url
		self._handlers = set([])
		self.rabbitmq_address = rabbitmq_address
		# Added the database handler as a subscriber
		self.add_subscriber(db_connector)

	def connect(self):
		"""This method connects to RabbitMQ, returning the connection handle.
		When the connection is established, the on_connection_open method
		will be invoked by pika.

		:rtype: pika.SelectConnection

		"""

		# gen_log.info('Connecting to %s', self._url)

		cred = pika.PlainCredentials('guest', 'guest')
		param = pika.ConnectionParameters(
			host=self.rabbitmq_address,
			# port=5672,
			virtual_host='/',
			credentials=cred
		)

		return adapters.TornadoConnection(
			param,
			self.on_connection_open)

	def close_connection(self):
		"""This method closes the connection to RabbitMQ."""
		gen_log.info('Closing connection')
		self._connection.close()

	def add_on_connection_close_callback(self):
		"""This method adds an on close callback that will be invoked by pika
		when RabbitMQ closes the connection to the publisher unexpectedly.

		"""
		gen_log.info('Adding connection close callback')
		self._connection.add_on_close_callback(self.on_connection_closed)

	def on_connection_closed(self, connection, reason):
		"""This method is invoked by pika when the connection to RabbitMQ is
		closed unexpectedly. Since it is unexpected, we will reconnect to
		RabbitMQ if it disconnects.

		:param pika.connection.Connection connection: The closed connection obj
		:param Exception reason: exception representing reason for loss of
			connection.

		"""
		self._channel = None
		if self._closing:
			self._connection.ioloop.stop()
		else:
			gen_log.warning('Connection closed, reopening in 5 seconds: %s', reason)
			self._connection.ioloop.call_later(5, self.reconnect)

	def on_connection_open(self, unused_connection):
		"""This method is called by pika once the connection to RabbitMQ has
		been established. It passes the handle to the connection object in
		case we need it, but in this case, we'll just mark it unused.

		:type unused_connection: pika.SelectConnection

		"""
		gen_log.info('Connection opened')
		self.add_on_connection_close_callback()
		self.open_channel()

	def reconnect(self):
		"""Will be invoked by the IOLoop timer if the connection is
		closed. See the on_connection_closed method.

		"""
		if not self._closing:

			# Create a new connection
			self._connection = self.connect()

	def add_on_channel_close_callback(self):
		"""This method tells pika to call the on_channel_closed method if
		RabbitMQ unexpectedly closes the channel.

		"""
		gen_log.info('Adding channel close callback')
		self._channel.add_on_close_callback(self.on_channel_closed)

	def on_channel_closed(self, channel, reason):
		"""Invoked by pika when RabbitMQ unexpectedly closes the channel.
		Channels are usually closed if you attempt to do something that
		violates the protocol, such as re-declare an exchange or queue with
		different parameters. In this case, we'll close the connection
		to shutdown the object.

		:param pika.channel.Channel: The closed channel
		:param Exception reason: why the channel was closed

		"""
		gen_log.warning('Channel %i was closed: %s', channel, reason)
		self._connection.close()

	def on_channel_open(self, channel):
		"""This method is invoked by pika when the channel has been opened.
		The channel object is passed in so we can make use of it.

		Since the channel is now open, we'll declare the exchange to use.

		:param pika.channel.Channel channel: The channel object

		"""
		gen_log.info('Channel opened')
		self._channel = channel
		self.add_on_channel_close_callback()
		self.setup_exchange(self.EXCHANGE)

	def setup_exchange(self, exchange_name):
		"""Setup the exchange on RabbitMQ by invoking the Exchange.Declare RPC
		command. When it is complete, the on_exchange_declareok method will
		be invoked by pika.

		:param str|unicode exchange_name: The name of the exchange to declare

		"""
		gen_log.info('Declaring exchange %s', exchange_name)
		self._channel.exchange_declare(
			self.on_exchange_declareok,
			exchange_name,
			self.EXCHANGE_TYPE, auto_delete=True)

	def on_exchange_declareok(self, unused_frame):
		"""Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
		command.

		:param pika.Frame.Method unused_frame: Exchange.DeclareOk response frame

		"""
		gen_log.info('Exchange declared')
		self.setup_queue(self.QUEUE)

	def setup_queue(self, queue_name):
		"""Setup the queue on RabbitMQ by invoking the Queue.Declare RPC
		command. When it is complete, the on_queue_declareok method will
		be invoked by pika.

		:param str|unicode queue_name: The name of the queue to declare.

		"""
		gen_log.info('Declaring queue %s', queue_name)
		self._channel.queue_declare(
			self.on_queue_declareok, queue_name)

	def on_queue_declareok(self, method_frame):
		"""Method invoked by pika when the Queue.Declare RPC call made in
		setup_queue has completed. In this method we will bind the queue
		and exchange together with the routing key by issuing the Queue.Bind
		RPC command. When this command is complete, the on_bindok method will
		be invoked by pika.

		:param pika.frame.Method method_frame: The Queue.DeclareOk frame

		"""
		gen_log.info('Binding %s to %s', self.EXCHANGE, self.QUEUE)
		self._channel.queue_bind(
			self.on_bindok, self.QUEUE, self.EXCHANGE)

	def add_on_cancel_callback(self):
		"""Add a callback that will be invoked if RabbitMQ cancels the consumer
		for some reason. If RabbitMQ does cancel the consumer,
		on_consumer_cancelled will be invoked by pika.

		"""
		gen_log.info('Adding consumer cancellation callback')
		self._channel.add_on_cancel_callback(self.on_consumer_cancelled)

	def on_consumer_cancelled(self, method_frame):
		"""Invoked by pika when RabbitMQ sends a Basic.Cancel for a consumer
		receiving messages.

		:param pika.frame.Method method_frame: The Basic.Cancel frame

		"""
		gen_log.info('Consumer was cancelled remotely, shutting down: %r',
					method_frame)
		if self._channel:
			self._channel.close()

	def acknowledge_message(self, delivery_tag):
		"""Acknowledge the message delivery from RabbitMQ by sending a
		Basic.Ack RPC method for the delivery tag.

		:param int delivery_tag: The delivery tag from the Basic.Deliver frame

		"""
		gen_log.info('Acknowledging message %s', delivery_tag)
		self._channel.basic_ack(delivery_tag)

	def on_message(self, unused_channel, basic_deliver, properties, body):
		"""Invoked by pika when a message is delivered from RabbitMQ. The
		channel is passed for your convenience. The basic_deliver object that
		is passed in carries the exchange, routing key, delivery tag and
		a redelivered flag for the message. The properties passed in is an
		instance of BasicProperties with the message properties and the body
		is the message that was sent.

		:param pika.channel.Channel unused_channel: The channel object
		:param pika.Spec.Basic.Deliver: basic_deliver method
		:param pika.Spec.BasicProperties: properties
		:param str|unicode body: The message body

		"""
		# body = body.decode()
		body = json.loads(body.decode())
		gen_log.info(
			'Received message # %s from %s: %s',
			basic_deliver.delivery_tag, basic_deliver.routing_key, body)
		# self.acknowledge_message(basic_deliver.delivery_tag)
		self.process_message(body, basic_deliver)

	def on_cancelok(self, unused_frame):
		"""This method is invoked by pika when RabbitMQ acknowledges the
		cancellation of a consumer. At this point we will close the channel.
		This will invoke the on_channel_closed method once the channel has been
		closed, which will in-turn close the connection.

		:param pika.frame.Method unused_frame: The Basic.CancelOk frame

		"""
		gen_log.info('RabbitMQ acknowledged the cancellation of the consumer')
		self.close_channel()

	def stop_consuming(self):
		"""Tell RabbitMQ that you would like to stop consuming by sending the
		Basic.Cancel RPC command.

		"""
		if self._channel:
			gen_log.info('Sending a Basic.Cancel RPC command to RabbitMQ')
			self._channel.basic_cancel(self.on_cancelok, self._consumer_tag)

	def start_consuming(self):
		"""This method sets up the consumer by first calling
		add_on_cancel_callback so that the object is notified if RabbitMQ
		cancels the consumer. It then issues the Basic.Consume RPC command
		which returns the consumer tag that is used to uniquely identify the
		consumer with RabbitMQ. We keep the value to use it when we want to
		cancel consuming. The on_message method is passed in as a callback pika
		will invoke when a message is fully received.

		"""
		gen_log.info('Issuing consumer related RPC commands')
		self.add_on_cancel_callback()
		self._consumer_tag = self._channel.basic_consume(
			self.on_message,
			self.QUEUE, no_ack=True)

	def on_bindok(self, unused_frame):
		"""Invoked by pika when the Queue.Bind method has completed. At this
		point we will start consuming messages by calling start_consuming
		which will invoke the needed RPC commands to start the process.

		:param pika.frame.Method unused_frame: The Queue.BindOk response frame

		"""
		gen_log.info('Queue bound')
		self.start_consuming()

	def close_channel(self):
		"""Call to close the channel with RabbitMQ cleanly by issuing the
		Channel.Close RPC command.

		"""
		gen_log.info('Closing the channel')
		self._channel.close()

	def open_channel(self):
		"""Open a new channel with RabbitMQ by issuing the Channel.Open RPC
		command. When RabbitMQ responds that the channel is open, the
		on_channel_open callback will be invoked by pika.

		"""
		gen_log.info('Creating a new channel')
		self._connection.channel(on_open_callback=self.on_channel_open)

	def run(self):
		"""Run the example consumer by connecting to RabbitMQ.

		"""
		self._connection = self.connect()

	def process_message(self, data, method):
		'''Need to process the data. Then check with the database to see if the
		collection.document pair is valid or not. After this, the data will be
		added to result, and all subscriber will be checked and the message will
		be sent to those subscribed to this particular channel.
		'''

		try:
			result = self.db_connector.get_doc_info(method.routing_key)
		except Exception as e:
			gen_log.error("Couldn't get collection and document info: {0}".format(e))
			return
		result['data'] = data

		for subscriber in self._handlers:
			gen_log.info("message came from, {0}".format(method.routing_key))

			if subscriber.has_subscribed_to(result['collection']):
				subscriber.write_message(result)
				gen_log.info('PikaConnector: notified %s' % repr(subscriber))

	def add_subscriber(self, subscriber):
		self._handlers.add(subscriber)
		# yield result
		gen_log.info('PikaConnector: subscriber %s added' % repr(subscriber))

	def remove_subscriber(self, subscriber):
		try:
			self._handlers.remove(subscriber)
			gen_log.info('PikaConnector: subscriber %s removed' % repr(subscriber))
		except KeyError:
			pass

	def stop(self):
		"""Cleanly shutdown the connection to RabbitMQ by stopping the consumer
		with RabbitMQ. When RabbitMQ confirms the cancellation, on_cancelok
		will be invoked by pika, which will then closing the channel and
		connection.

		"""
		gen_log.info('Stopping')
		self._closing = True
		self.stop_consuming()
		# self._connection.ioloop.start()
		gen_log.info('Stopped')
