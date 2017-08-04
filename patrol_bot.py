# -*- coding: utf-8 -*-

import json
import pika
import threading
import time
import traceback
import logging,logging.config
import subprocess

logging.config.fileConfig("logging.conf")
logger = logging.getLogger("root")

mq_server_ip = 'localhost'
mq_exchange_name = 'systembot'
mq_routing_key = 'warn_ticket'
mq_routing_key_patrol_restart = "restart_patrol"
mq_routing_key_commit = "commit"

queue_warn_list = 'system.autowarnner.warnlist'
queue_patrol_restart = 'system.autowarnner.patrol.restart'
queue_patrol_checkalive = 'system.autowarnner.patrol.checkalive'
queue_commit = 'system.autowarnner.commit'

connection = None
handler_channel = None
commit_channel = None

def callback(ch, method, properties, body):
    msg  = eval(body)
    logger.info(" [x] Received %s" % msg )
    ip_address = msg['ip_address']
    warn_id = msg['warn_id']
    warn_no = msg['warn_no']
    logger.info ("    >>>--- Restart Target: %s" % ip_address )

    # do the real restart, only on linux
    cmdstr = '/bin/nsh RestartPatrolAgent.nsh ' + ip_address
    suc = 1
    try:
        out_bytes = subprocess.check_output(cmdstr, shell=True, timeout=60)
        logger.info("   [-] command exec Successful, output is: %s" % out_bytes.decode('gb18030') )
    except subprocess.CalledProcessError as e:
        suc = 0
        out_bytes = e.output
        code = e.returncode
        logger.error(traceback.print_exc())
    except subprocess.TimeoutExpired as e:
        suc = 0
        logger.info("   [-] command exec timeout (over 60 sec) "  )

    time.sleep(body.count(b'.'))
    logger.info(" [x] Restart Done")
    ch.basic_ack(delivery_tag = method.delivery_tag)

    if suc :
        # put commit msg in commit channel
        logger.info(" [*] Restart Successful, put commit message back. ")
        commit_channel.basic_publish(exchange=mq_exchange_name, routing_key=mq_routing_key_commit, body=body)
    else:
        logger.error(" [*] Restart Failure... ")


if __name__ == '__main__':
    # do something
    logger.info(' [*] Waiting for (patrol) messages. To exit press CTRL+C')

    authentication = pika.PlainCredentials('sysbot', 'sysbot')
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=mq_server_ip,port=5672,credentials=authentication))

    # declare queue for restart patrol
    restart_channel = connection.channel()
    restart_channel.exchange_declare(exchange=mq_exchange_name, type='direct')
    restart_channel.queue_declare(queue=queue_patrol_restart)
    restart_channel.queue_bind(exchange=mq_exchange_name, queue=queue_patrol_restart, routing_key=mq_routing_key_patrol_restart)

    # declare queue for commit handling
    commit_channel = connection.channel()
    commit_channel.exchange_declare(exchange=mq_exchange_name, type='direct')
    commit_channel.queue_declare(queue=queue_commit)
    commit_channel.queue_bind(exchange=mq_exchange_name, queue=queue_commit, routing_key=mq_routing_key_commit)

    restart_channel.basic_qos(prefetch_count=1)
    restart_channel.basic_consume(callback, queue=queue_patrol_restart)
    restart_channel.start_consuming()
