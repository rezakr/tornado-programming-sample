import handlers

urls = [
	(r"/", handlers.MainHandler),
	(r"/feed", handlers.FeedHandler),
	(r'/ws', handlers.FeedWebSocketHandler),
]
