from threading import Thread
import time

from ckan.tests import *
from ckan import model
from ckan.lib.helpers import json

class OurConsumer(Thread):
    def __init__ (self, conn):
        Thread.__init__(self)
        self.result = None
        self.conn = conn

    def run(self):
        from carrot.messaging import Consumer
        conn = self.conn
        consumer = Consumer(connection=conn, queue="feed",
                            exchange=EXCHANGE, routing_key="importer")

        def import_feed_callback(message_data, message):
            feed_url = message_data["import_feed"]
            print "GOT SOMETHING"
            self.result = "Got feed import message for: %s" % feed_url
            # something importing this feed url
            # import_feed(feed_url)
            message.ack()
           
        consumer.register_callback(import_feed_callback)
        consumer.wait() # Go into the consumer loop.       

class RecordingConsumer(Thread):
    '''As a consumer, this thread creates a queue and records what is put
    on it.
    '''
    def __init__ (self, conn, queue='recorder', exchange=model.EXCHANGE,
                  routing_key='*'):
        Thread.__init__(self)
        self.result = None
        self.conn = conn
        self.consumer_options = {
            queue:queue, exchange:model.EXCHANGE, routing_key:routing_key}
        self.queued = []

    def run(self):
        from carrot.messaging import Consumer
        conn = self.conn
        consumer = Consumer(connection=self.conn, **self.consumer_options)

        def callback(message_data, message):
            self.queued.append((message_data, message))
            print "MESSAGE DATA", message_data
            print "MESSAGE", message
            message.ack()
           
        consumer.register_callback(callback)
        consumer.wait() # Go into the consumer loop.       

      
class TestQueue(TestController):
    def test_basic(self):
        # create connection
        consumer = OurConsumer(model.get_conn())
        consumer.daemon = True # so destroyed automatically
        consumer.start()


        # send message
        from carrot.messaging import Publisher
        publisher = Publisher(connection=model.get_conn(),
                              exchange=model.EXCHANGE, routing_key="importer")
        publisher.send({"import_feed": "http://cnn.com/rss/edition.rss"})
        publisher.close()

        time.sleep(0.1)

        for i in range(10):
            print consumer.result

class TestPackageEditMessage(object):
    @classmethod
    def setup_class(self):
        model.Session.remove()

    @classmethod
    def teardown_class(self):
        model.Session.remove()
        model.repo.rebuild_db()

    def get_conn(self):
        from carrot.connection import BrokerConnection
        return BrokerConnection(hostname="localhost", port=5672,
                                userid="guest", password="guest",
                                virtual_host="/",
#                                backend_cls='carrot.backends.pyamqplib.Backend',
                                backend_cls='carrot.backends.queue.Backend',
                                )

    def test_new_package(self):
        # create connection
        consumer = RecordingConsumer(model.get_conn())
        consumer.daemon = True # so destroyed automatically
        consumer.start()

        # create package
        name = u'testpkg'
        rev = model.repo.new_revision()        
        pkg = model.Package(name=name)
        model.Session.add(pkg)
        model.repo.commit_and_remove()

        time.sleep(0.1)

        assert len(consumer.queued) == 1, consumer.queued
        payload, header = consumer.queued[0]
        assert payload['name'] == name, payload
        import pdb; pdb.set_trace()
