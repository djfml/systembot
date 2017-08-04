# -*- coding: utf-8 -*-
import requests
import time,datetime
import json
import pika
import threading
from time import sleep
import traceback
import logging,logging.config

itsm_ip = '10.98.81.13'
username = '03661'
passwd = 'pass4ever'

# mq info
mq_server_ip = 'localhost'
mq_exchange_name = 'systembot'
mq_routing_key = 'warn_ticket'
mq_routing_key_commit = "commit"

queue_warn_list = 'system.autowarnner.warnlist'
queue_patrol_restart = 'system.autowarnner.patrol.restart'
queue_patrol_checkalive = 'system.autowarnner.patrol.checkalive'
queue_commit = 'system.autowarnner.commit'

login_url = 'http://' + itsm_ip + '/itsm/j_spring_security_check'
warn_url_prfix = 'http://' + itsm_ip + '/itsm/itsmWarningInfoAction!pageSearch.action?_timestamp='
warn_detail_url = 'http://' + itsm_ip + '/itsm/itsmWarningInfoAction!view.action'
warn_addlog_url = 'http://'+ itsm_ip + '/itsm/itsmWarningInfoAction!addUserLog.action'
warn_accept_url = 'http://'+ itsm_ip + '/itsm/itsmWarningInfoAction!accept.action'
warn_close_url = 'http://'+ itsm_ip + '/itsm/itsmWarningInfoAction!close.action'

#logger
logging.config.fileConfig("logging.conf")
logger = logging.getLogger("scanner")

session = None
authentication = pika.PlainCredentials('sysbot', 'sysbot')
connection = pika.BlockingConnection(pika.ConnectionParameters(host=mq_server_ip, port=5672, credentials=authentication))

# json data
postdata = {
    'start' : "0",
    'end'   : "20",
    'warTopic' : '', # Topic search key word
    'createDateBegin': "",
    'createDateOver': "",
    'queryWarOrigin': "40,160", # Warn srouce - sysm, nbu
    'queryWarStatus': "" # Warn status - unhandled (10)
}
acceptdata = {
    'id': "",
    'warNo': ""
}
closedata = {
    'id': "",
    'ids': "",
    'closeCode': "30",
    'userLog': "计划内告警，重启Patrol Agent"
}
sendData = {
    "ip": "",
    "warn_no": "",
    "warn_id" : "",
    "warn_topic": "",
    "warn_content": ""
}
addlogData = {
    "id": "",
    "userLog": "XXX"
}

class ITSMScanner(threading.Thread):
    """docstring for ."""
    current_warn_id = 0
    session = None
    connection = None

    def __init__(self, session, connection):
        super(ITSMScanner,self).__init__()
        self.session = session
        self.connection = connection

    def __del__(self):
        logger.debug("destruct scanner...")
        # need to destruct connection & session?

    def getConnection(self):
        return self.connection

    def get_warn_tickets(self, NumOfDays=-1, title="Patrol"):
        logger.debug("get_warn_tickets")

        time_now = datetime.datetime.now()
        time_yesterday = time_now + datetime.timedelta(days=NumOfDays)
        createDateOver = time_now.strftime("%Y-%m-%d %H:%M:%S")
        createDateBegin = time_yesterday.strftime("%Y-%m-%d %H:%M:%S")

        postdata['createDateOver'] = createDateOver
        postdata['createDateBegin'] = createDateBegin
        postdata['warTopic'] = title

        ts = int(time.time()*1000)
        warn_url = warn_url_prfix  + str(ts)
        logger.debug(warn_url)

        channel = self.connection.channel()
        channel.exchange_declare(exchange=mq_exchange_name, type='direct')
        channel.queue_declare(queue=queue_warn_list)
        channel.queue_bind(exchange=mq_exchange_name, queue=queue_warn_list, routing_key=mq_routing_key)

        try:
            res = self.session.post(warn_url, data=postdata)
            logger.info (res.status_code)
            warn_list = res.json()['root']
            warn_list = sorted(warn_list, key=lambda k: k['id'])
            for warn in warn_list:
                try:
                    if  self.current_warn_id >= int( warn['id'] ) :
                        continue
                    else:
                        self.current_warn_id = int( warn['id'])
                        logger.info( ">>>> current_warn_id is updated to %d " %( int(warn['id']) ) )

                    logger.info ( "| %s | %d | %s |" %(warn['warNo'] ,(warn['id']), warn['warContent']))

                    # Accept warn ticket
                    acceptdata['id'] = warn['id']
                    acceptdata['warNo'] = warn['warNo']
                    self.session.post(warn_accept_url, data=acceptdata)

                    # Get target ip address
                    target_ip_address = warn['warContent'].split(',')[2]
                    logger.info( "\t ip_address = %s " %(target_ip_address ))

                    # put data into message queue
                    sendData['warn_id'] = warn['id']
                    sendData['warn_no'] = warn['warNo']
                    sendData['ip'] = target_ip_address
                    sendData['warn_topic'] = warn['warTopic']
                    sendData['warn_content'] = warn['warContent']
                    msg_body = json.dumps(sendData)
                    channel.basic_publish(exchange=mq_exchange_name, routing_key=mq_routing_key, body=msg_body)

                except Exception as e:
                    logger.error(traceback.print_exc())
                    continue
        except Exception as e:
            logger.error("[ERROR], please check exception")
            logger.error(e)

    def cleanup_session(self):
        try:
            if self.connection:
                self.connection.close()
            if self.session:
                self.session.close()
        except Exception as e:
            logger.error(e)
        logger.debug("clean up scanner's sessions...")

    def run(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(mq_server_ip))

        logger.info("Scanner thread (%s) is running... " %(self.getName()))
        #for i in range(3):
        while True:
            self.get_warn_tickets(-3, 'Patrol')
            logger.info (" ...<<<<<<<...")
            sleep(30)

        cleanup_session()
        logger.info("Scanner thread (%s) finished..." %(self.getName()))

def Get_session(url, username, passwd):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2490.86 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    }

    session = requests.Session()
    session.headers = headers

    postdata = {
        'j_username' : username,
        'j_password' : passwd
    }

    res = session.post(url, data=postdata)
    # print (res.text.encode('utf-8') )
    if res.text.find('j_spring_security_logout') > -1:
        return session
    else:
        return

def callback(ch, method, properties, body):
    msg  = eval(body)
    print(" [x] Received %s" % msg )
    warn_id = msg['warn_id']
    warn_no = msg['warn_no']

    try:
        addlogData['id'] = warn_id
        addlogData['userLog'] = '[sysbot] [A] finish restart @' + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        #closedata['id'] = warn_id
        #closedata['ids'] = warn_id
        session.post(warn_addlog_url, addlogData)

        # TODO need check whether the target recovers
        # TODO PUT THIS SCRIPT ON PATROL CENTER
        #for x in xrange(3):
        #    sleep(120)
        #session.post(warn_close_url, closedata)

        print ("    ####--- Warn: %s committed... " % warn_no )
        time.sleep(body.count(b'.'))
        print(" [x] Done")
    except Exception as e:
        print(traceback.print_exc())

    ch.basic_ack(delivery_tag = method.delivery_tag)

"""
1. get latest warning message and put them into message queue
2. close itsm warn message
"""
if __name__ == '__main__':

    session = Get_session(login_url, username, passwd)
    if not session:
        logger.error("Get session Failed")
        exit

    # constuct scanner
    scanner = ITSMScanner(session, connection)
    scanner.setDaemon(True)
    scanner.start()
    logger.info("##### scanner end. #####")

    # declare queue for commit handling
    commit_channel = connection.channel()
    commit_channel.exchange_declare(exchange=mq_exchange_name, type='direct')
    commit_channel.queue_declare(queue=queue_commit)
    commit_channel.queue_bind(exchange=mq_exchange_name, queue=queue_commit, routing_key=mq_routing_key_commit)

    #channel.queue_declare(queue=queue_warn_list)
    commit_channel.basic_qos(prefetch_count=1)
    commit_channel.basic_consume(callback, queue=queue_commit)
    commit_channel.start_consuming()

    try:
        while scanner.isAlive():
            sleep(60)
            pass
    except KeyboardInterrupt:
        scanner.cleanup_session()
        logger.debug("stopped by keyboard")

    logger.info("##### scanner end. #####")
