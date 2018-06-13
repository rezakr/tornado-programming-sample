import motor
from tornado import gen
from tornado.log import gen_log
from pymongo.errors import InvalidName


class MongoConnector(object):
	db = None

	def _parse_options(self, options):
		if options is None:
			options = {}
		# options['name_space'] = options.get()

	def __init__(self, database_name, mongo_address=None, options=None):
		self.database_name = database_name
		if mongo_address is None:
			mongo_address = 'mongodb://localhost:27017'
		self.db = motor.motor_tornado.MotorClient(mongo_address)[database_name]
		self._parse_options(options)

	def check_collection_name(self, collection_name):
		''' Can use collection instance as well, but then this function needs to be
		async. The criteria didn't say anything about "waiting on a response from DB"
		'''
		if not collection_name or ".." in collection_name:
			raise InvalidName("collection names cannot be empty")
		if collection_name[0] == "." or collection_name[-1] == ".":
			raise InvalidName("collecion names must not start or end with '.'")
		if "$" in collection_name and not collection_name.startswith("oplog.$main"):
			raise InvalidName("collection names must not contain '$'")
		if collection_name.startswith("service."):
			raise InvalidName("collection names cannot start with service")
		if "\x00" in collection_name:
			raise InvalidName(
				"collection names must not contain the null character")
		return True

	def get_doc_info(self, routing_key):
		# The right most part of the routing_key should be the document
		collection, document = routing_key.rsplit('.', 1)
		# len(data) + "." + collection should not be more than 120
		if len(self.database_name + collection) > 121:
			raise Exception("Collection name is too long, max is 120 bytes")

		self.check_collection_name(collection)

		result = {
			'collection': collection,
			'document': document
		}

		return result

	@gen.coroutine
	def save(self, collection, document, data):
		coll = self.db[collection]
		# Copy and add _id to document
		new_data = data.copy()
		new_data["_id"] = document
		gen_log.info("Document {0} was saved in {1}".format(document, collection))
		yield coll.insert_one(new_data)

	@gen.coroutine
	def write_message(self, message):
		self.save(**message)

	def has_subscribed_to(self, collection_name):
		# Can check to see if mongo should save this collection
		return True

	@gen.coroutine
	def create_collection(self, collection):
		if collection not in self.db.collection_names():
			yield self.db.create_collection(
				collection,
				capped=True,
				size=1000)

	@gen.coroutine
	def get_collections(self):
		yield self.db.collection_names()
