import tornado.options
import tornado.ioloop
import tornado.web

import settings
from urls import urls

from pika_connector import PikaConnector
from mongo_connector import MongoConnector


def make_app():
	return tornado.web.Application(urls, debug=True)


def main():
	tornado.options.options['logging'] = "INFO"
	tornado.options.parse_command_line()

	io_loop = tornado.ioloop.IOLoop.instance()

	app = make_app()

	# MongoConnector is our mongodb connector
	mongo_connector = MongoConnector(
		'test_database', mongo_address=settings.MONGO_ADDRESS)
	app.mongo_connector = mongo_connector
	# PikaConnector is our rabbitmq consumer
	app.pika_connector = PikaConnector(
		io_loop, mongo_connector, rabbitmq_address=settings.RABBITMQ_ADDRESS)
	app.pika_connector.run()

	try:
		app.listen(8888)
		io_loop.start()

	except KeyboardInterrupt:
		app.pika_connector.stop()


if __name__ == '__main__':
	main()
