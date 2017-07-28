# -*- coding: utf-8 -*-

import json
import pika
import threading
import time
from time import sleep
import traceback
import logging,logging.config

logging.config.fileConfig("logging.conf")
logger = logging.getLogger("dispatcher")

mq_server_ip = 'localhost'
queue_warn_list = 'system.autowarnner.warnlist'
queue_patrol_restart = 'system.autowarnner.patrol.restart'
queue_patrol_checkalive = 'system.autowarnner.patrol.checkalive'

patten_patrol_highcpu = r'【A1-018】该进程\(PatrolAgent\)cpu使用率达到 \(.+%\)'
patten_patrol_highmem = r'【A1-019】该进程\(PatrolAgent\)占用内存达到 \(.+%\)'

def callback(ch, method, properties, body):
    msg  = eval(body)
    print(" [x] Received %s" % msg )
    warn_content = msg['warn_content']
    ip_address = msg['ip']
    warn_id = msg['warn_id']
    warn_no = msg['warn_no']
    print ("  [-] Warn Content: %s" % warn_content)
    

    time.sleep(body.count(b'.'))
    print(" [x] Done")
    ch.basic_ack(delivery_tag = method.delivery_tag)

if __name__ == '__main__':
    # do something
    print(' [*] Waiting for messages. To exit press CTRL+C')
    connection = pika.BlockingConnection(pika.ConnectionParameters(mq_server_ip))
    channel = connection.channel()
    channel.queue_declare(queue=queue_warn_list)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(callback, queue=queue_warn_list)
    channel.start_consuming()
