# -*- coding: utf-8 -*-

import json
import pika
import threading
import time
from time import sleep
import traceback
import logging,logging.config
import re

logging.config.fileConfig("logging.conf")
logger = logging.getLogger("dispatcher")

mq_server_ip = 'localhost'
mq_exchange_name = 'systembot'
mq_routing_key = 'warn_ticket'
mq_routing_key_patrol_restart = "restart_patrol"
mq_routing_key_commit = "commit"

queue_warn_list = 'system.autowarnner.warnlist'
queue_patrol_restart = 'system.autowarnner.patrol.restart'
queue_patrol_checkalive = 'system.autowarnner.patrol.checkalive'
queue_commit = 'system.autowarnner.commit'

patten_patrol_highcpu = re.compile(r'【A1-018】该进程\(PatrolAgent\)cpu使用率达到 \(.+%\)')
patten_patrol_highmem = re.compile(r'【A1-019】该进程\(PatrolAgent\)占用内存达到 \(.+KB\)')

connection = None
channel = None
handler_channel = None

sendData = {
    "warn_no": "",
    "warn_id": "",
    "ip_address": ""
}

def callback(ch, method, properties, body):
    msg  = eval(body)
    print(" [x] Received %s" % msg )
    warn_content = msg['warn_content']
    ip_address = msg['ip']
    warn_id = msg['warn_id']
    warn_no = msg['warn_no']
    print ("    >>>--- Warn Content: %s" % warn_content )

    r1 = patten_patrol_highcpu.findall(warn_content)
    r2 = patten_patrol_highmem.findall(warn_content)
    if r1 or r2:
        restart_patrol(warn_id, warn_no, ip_address)

    time.sleep(body.count(b'.'))
    print(" [x] Done")
    ch.basic_ack(delivery_tag = method.delivery_tag)

def restart_patrol(warn_id, warn_no, ip_address):
    print(" [P] begin restart ")
    sendData['ip_address'] = ip_address
    sendData['warn_id'] = warn_id
    sendData['warn_no'] = warn_no
    msg_body = json.dumps(sendData)
    handler_channel.basic_publish(exchange=mq_exchange_name, routing_key=mq_routing_key_patrol_restart, body=msg_body)

    #simulate commit action, which should be taken on the target machine
    commit_channel.basic_publish(exchange=mq_exchange_name, routing_key=mq_routing_key_commit, body=msg_body)


if __name__ == '__main__':
    # do something
    print(' [*] Waiting for messages. To exit press CTRL+C')
    connection = pika.BlockingConnection(pika.ConnectionParameters(mq_server_ip))

    # declare queue for warn ticket list
    channel = connection.channel()
    channel.exchange_declare(exchange=mq_exchange_name, type='direct')
    channel.queue_declare(queue=queue_warn_list)

    # declare queue for restart patrol
    handler_channel = connection.channel()
    handler_channel.exchange_declare(exchange=mq_exchange_name, type='direct')
    handler_channel.queue_declare(queue=queue_patrol_restart)
    handler_channel.queue_bind(exchange=mq_exchange_name, queue=queue_patrol_restart, routing_key=mq_routing_key_patrol_restart)

    # declare queue for commit handling
    commit_channel = connection.channel()
    commit_channel.exchange_declare(exchange=mq_exchange_name, type='direct')
    commit_channel.queue_declare(queue=queue_commit)
    commit_channel.queue_bind(exchange=mq_exchange_name, queue=queue_commit, routing_key=mq_routing_key_commit)

    #channel.queue_declare(queue=queue_warn_list)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(callback, queue=queue_warn_list)
    channel.start_consuming()
