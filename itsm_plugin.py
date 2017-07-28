# -*- coding: utf-8 -*-
import requests
import time,datetime
import json
import pika
import threading
from time import sleep
import traceback
import logging,logging.config

login_url = 'http://10.98.81.13/itsm/j_spring_security_check'
username = '03661'
passwd = 'pass4ever'

# mq info
mq_server_ip = 'localhost'
queue_patrol_restart = 'system.autowarnner.patrol.restart'
queue_patrol_checkalive = 'system.autowarnner.patrol.checkalive'
queue_warn_list = 'system.autowarnner.warnlist'

warn_url_prfix = 'http://10.98.81.13/itsm/itsmWarningInfoAction!pageSearch.action?_timestamp='
warn_detail_url = 'http://10.98.81.13/itsm/itsmWarningInfoAction!view.action'

#logger
logging.config.fileConfig("logging.conf")
logger = logging.getLogger("ITSMScanner")

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
detaildata = {
    'id': ""
}
sendData = {
    "ip": "",
    "warn_no": "",
    "warn_id" : "",
    "warn_topic": "",
    "warn_content": ""
}

class ITSMScanner(threading.Thread):
    """docstring for ."""
    current_warn_id = 0
    session = None
    connection = None

    def __init__(self):
        super(ITSMScanner,self).__init__()

    def __del__(self):
        logger.debug("destruct scanner...")
        # need to destruct connection & session?

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
        channel.queue_declare(queue=queue_warn_list)

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
                    # Get target ip address
                    detaildata['id'] = warn['id']
                    detail = self.session.post(warn_detail_url, data=detaildata)
                    target_ip_address = detail.json()['data']['oppositeNo'].split('/')[1]
                    logger.info( "\t ip_address = %s " %(target_ip_address ))

                    # put data into message queue
                    sendData['warn_id'] = warn['id']
                    sendData['warn_no'] = warn['warNo']
                    sendData['ip'] = target_ip_address
                    sendData['warn_topic'] = warn['warTopic']
                    sendData['warn_content'] = warn['warContent']
                    msg_body = json.dumps(sendData)
                    channel.basic_publish(exchange='', routing_key=queue_warn_list, body=msg_body)

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
        self.session = Get_session(login_url, username, passwd)
        if not self.session:
            logger.error("Get session Failed")
            return
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(mq_server_ip))

        logger.info("Scanner thread (%s) is running... " %(self.getName()))
        #for i in range(3):
        while True:
            self.get_warn_tickets(-1, '')
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

"""
1. get latest warning message and put them into message queue
2. close itsm warn message
"""
if __name__ == '__main__':
    scanner = ITSMScanner()
    scanner.setDaemon(True)
    scanner.start()
    logger.info("##### scanner end. #####")
    try:
        while scanner.isAlive():
            sleep(60)
            pass
    except KeyboardInterrupt:
        scanner.cleanup_session()
        logger.debug("stopped by keyboard")

    logger.info("##### scanner end. #####")
