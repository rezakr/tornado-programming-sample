## Code Challenge for Dojo Madness

This is my try at solving the challenge program set by Dojo Madness at (here)[https://gist.github.com/eguven/63b05f4c4c4cba459740553e22404d93 ]

* Requirements: Python3.6


### Problem [python developer]

Write a **non-blocking** [Tornado](http://www.tornadoweb.org/) application according to the following info.

* consume messages (content type "application/json") from [RabbitMQ](https://www.rabbitmq.com/) and store them in [MongoDB](https://www.mongodb.com/)
* provide websocket endpoint that publishes incoming messages to websocket clients _as they arrive_ from RabbitMQ
* the routing key format is `{collection}.{_id}` denoting MongoDB collection and document `_id` eg. a message with routing key `foo.bar` should be inserted in collection "foo" with document \_id "bar"
* no assumptions should be made on the type or validity of the routing key, whatever MongoDB accepts is valid

#### Bonus

* [Bonus] Websocket clients can subscribe to a collection and will only receive the messages with matching routing keys
* [Bonus] RabbitMQ cleanup (if necessary) before app shutdown
* [Bonus] docker-compose config that launches the dependencies as well as the tornado app

#### Notes

* [motor](https://motor.readthedocs.io/) is the recommended asynchronous client library for MongoDB
* you can use [rmq_publisher.py](https://gist.github.com/eguven/b5c6aa8c8eff638466efdcfcf6e1bc8c) for quick testing
* you can assume default auth scheme for RabbitMQ and MongoDB
* a well structured project is expected

### Notice

* Solution can be provided through a Github repo
* Please do not share this problem definition
* Please delete your repo after evaluation