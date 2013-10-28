#!/usr/bin/python
# encoding:utf-8
# +-----------------------------------------------------------------------------
# | Forked from huxuan
# | E-mail: i(at)huxuan.org
# +-----------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
# Name:        xiami_auto_checkin.py
# Purpose:
# Author:      windviki@gmail.com
# Created:     May 17, 2012
#-------------------------------------------------------------------------------

import re
import os
import sys
import urllib
import urllib2
from datetime import *
import cookielib

import types
import ConfigParser
import logging
import logging.handlers
import random
import time as Time

import traceback

def initlogger():
    """
    Initialize logger
    """
    # Formatter
    logformatter = logging.Formatter('[%(asctime)s] [%(name)-12s] [%(filename)s(%(lineno)d)] %(message)s')
    
    # Filter
    xiamifilter = logging.Filter('xiami')
    
    # Rotating file logger
    rotatingfilehandler = logging.handlers.RotatingFileHandler("xiami.log", "a", 5 * 1024 * 1024, 3)
    rotatingfilehandler.setLevel(logging.DEBUG)
    rotatingfilehandler.setFormatter(logformatter)
    rotatingfilehandler.addFilter(xiamifilter)
    
    # Console logger
    consolehandler = logging.StreamHandler()
    consolehandler.setLevel(logging.DEBUG)
    consolehandler.setFormatter(logformatter)
    consolehandler.addFilter(xiamifilter)
    
    logging.getLogger('').addHandler(rotatingfilehandler)
    logging.getLogger('').addHandler(consolehandler)
    
    logging.getLogger('').setLevel(logging.DEBUG)
    
def get_total_seconds(td):
    # datetime.total_seconds has been introduced in Python 2.7, therefore it can't be used here (Python 2.6)
    return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 1e6) / 1e6

class RandomTimeGenerator:
    """
    RandomTimeGenerator
    """
    def __init__(self, startime, endtime):
        _start = startime.split(':')
        _end = endtime.split(':')
        _current = datetime.now()
        self.starttime = _current.replace(hour=int(_start[0]), minute=int(_start[1]))
        self.endtime = _current.replace(hour=int(_end[0]), minute=int(_end[1]))
        self.span = self.endtime - self.starttime
        
    def get(self):
        _current = datetime.now()
        _minutes = random.randint(1, get_total_seconds(self.span) / 60)
        _delta = timedelta(minutes=_minutes)
        if _current < self.starttime:
            return self.starttime + _delta
        elif _current > self.endtime:
            return _current.replace(minute=_current.minute + 1)
        else:
            _minutes = random.randint(1, get_total_seconds(self.endtime - _current) / 60 + 1)
            _delta = timedelta(minutes=_minutes)
            return _current + _delta
    
    
class ConfigHandler:
    """
    Configuration Handler
    """
    def __init__(self, configpath):
        self.configsection = "xiami"
        self.configfile = configpath
        self.config = ConfigParser.ConfigParser()
        self.config.read(self.configfile)
        if not self.config.has_section(self.configsection):
            self.config.add_section(self.configsection)
        self.username = []
        self.password = []
        if self.config.has_option(self.configsection, "username"):
            self.username = [x.strip() for x in self.config.get(self.configsection, "username").split(',') if len(x) and not x.isspace()]
        if self.config.has_option(self.configsection, "password"):
            self.password = [x.strip() for x in self.config.get(self.configsection, "password").split(',') if len(x) and not x.isspace()]
        self.pairs = zip(self.username, self.password)
        self.startime = ""
        self.endtime = ""
        if self.config.has_option(self.configsection, "timerange"):
            _startend = self.config.get(self.configsection, "timerange").split('-')
            self.startime = _startend[0]
            self.endtime = _startend[1]
        
    def __getitem__(self, key):
        return self.config.get(self.configsection, key)
    
    def __setitem__(self, key, value):
        if type(value) == types.UnicodeType:
            value = value.encode("utf-8")
        self.config.set(self.configsection, key, value)
        
    def __delitem__(self, key):
        if self.config.has_option(self.configsection, key):
            self.config.remove_option(self.configsection, key)
        
    def save(self):
        self.config.write(open(self.configfile, "w+"))


class XiamiHandler:
    """
    Xiami web request/response Handler
    """
    def __init__(self, username, password):
        self.logger = logging.getLogger('xiami.XiamiHandler')
        self.username = username
        self.password = password
        self.loginresponse = ''
        self.checkinresponse = ''
        self.logoutresponse = ''
        self.cookie = ''
        self.useragent = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.94 Safari/537.36'
        self.login_url = 'http://www.xiami.com/member/login'
        self.login_data = urllib.urlencode({
                                       'done':"%2F",
                                       'type':'',
                                       'email':self.username,
                                       'password':self.password,
                                       'autologin':0,
                                       'submit':'登 录', })
        self.login_headers = {'Referer':'http://www.xiami.com/home',
                              'User-Agent': self.useragent, }
        self.checkin_url = "http://www.xiami.com/task/signin"
        self.checkin_headers = {'Referer':'http://www.xiami.com/home',
                                'User-Agent': self.useragent, }
        self.logout_url = 'http://www.xiami.com/member/logout'
        self.logout_headers = {'Referer':'http://www.xiami.com/member/mypm-notice',
                                'User-Agent': self.useragent, }
        
    def process(self, debug=False):
        login_result = self._login()
        if not login_result:
            self.logger.error('[Error] Login Failed! user = %s', self.username)
            return False
        checkin_pattern = re.compile(r'<b class="icon tosign done">')
        checkin_result = checkin_pattern.search(self.loginresponse)
        bresult = False
        if checkin_result:
            # Checkin Already
            self.logger.info('[Succeed] Checkin Already! user = %s, result = %s days', self.username, result)
            bresult = True
        else:
            #self.checkin_url = 'http://www.xiami.com' + checkin_result.group(1)
            #self.logger.debug('checkin url = %s', self.checkin_url)
            bresult = self._checkin()
            self.logger.info('[Succeed] Checked in! user = %s, result = %s days', self.username, self.checkinresponse)
        if bresult:
            self._logout()
            self.logger.info('Logout, user = %s', self.username)
        if debug:
            self._dump()
        return bresult

    def _login(self):
        # Post login info
        login_request = urllib2.Request(self.login_url, self.login_data, self.login_headers)
        try:
            _loginresponse = urllib2.urlopen(login_request).read()
            # Get main page
            main_page_request = urllib2.Request("http://www.xiami.com/home", None, self.login_headers)
            self.loginresponse = urllib2.urlopen(main_page_request).read()
            return True
        except urllib2.HTTPError, he:
            self.logger.error('[Error] _login Failed! error = %s', he)
            self.loginresponse = ""
            return False
        except urllib2.URLError, ue:
            self.logger.error('[Error] _login Failed! error = %s', ue)
            self.loginresponse = ""
            return False
        except Exception, ce:
            self.logger.error('[Error] _login Failed! error = %s', ce)
            self.loginresponse = ""
            return False
    
    def _logout(self):
        # Logout
        logout_request = urllib2.Request(self.logout_url, None, self.logout_headers)
        try:
            self.logoutresponse = urllib2.urlopen(logout_request).read()
        except urllib2.HTTPError, he:
            self.logger.error('[Error] _logout Failed! error = %s', he)
            self.logoutresponse = ""
        except Exception, ce:
            self.logger.error('[Error] _logout Failed! error = %s', ce)
            self.logoutresponse = ""
        
    def _checkin(self):
        checkin_request = urllib2.Request(self.checkin_url, None, self.checkin_headers)
        try:
            self.checkinresponse = urllib2.urlopen(checkin_request).read()
            # Get main page
            #main_page_request = urllib2.Request("http://www.xiami.com", None, self.login_headers)
            #self.checkinresponse = urllib2.urlopen(main_page_request).read()
            return True
        except urllib2.HTTPError, he:
            self.logger.error('[Error] _checkin Failed! error = %s', he)
            self.checkinresponse = ""
            return False
        except urllib2.URLError, ue:
            self.logger.error('[Error] _checkin Failed! error = %s', ue)
            self.checkinresponse = ""
            return False
        except Exception, ce:
            self.logger.error('[Error] _checkin Failed! error = %s', ce)
            self.checkinresponse = ""
            return False
        
    def _dump(self):
        datas = {'login':self.loginresponse,
                 'checkin':self.checkinresponse,
                 'logout':self.logoutresponse}
        logdir = os.path.join(os.getcwd(), "logs")
        if not os.path.exists(logdir):
            os.mkdir(logdir)
        for k, v in datas.items():
            outputfname = os.path.join(logdir, "%s-%s.html" % (k, self.username))
            outputfile = file(outputfname, "wb")  
            outputfile.write(v)
            outputfile.close()

def main():
    """
    Main process of auto checkin
    """
    # Run Once
    bRunOnce = False
    if len(sys.argv) > 1:
        if sys.argv[1] == "-q":
            bRunOnce = True
            
    # Logger
    initlogger()
    xiamilogger = logging.getLogger('xiami')
    xiamilogger.info('')
    xiamilogger.info('-' * 30)
    
    # Configuration
    configfilepath = os.path.join(os.getcwd(), 'config.txt')
    if not os.path.exists(configfilepath):
        xiamilogger.error('%s does not exist!', configfilepath)
        return

    configuration = ConfigHandler(configfilepath)
    if len(configuration.username) == 0 or len(configuration.password) == 0:
        xiamilogger.error('Not find username or password in configuration file!')
        return

    #import pprint
    #pprint.pprint(configuration.username)
    #pprint.pprint(configuration.password)
    #pprint.pprint(configuration.pairs)
    
    try:
        # Init urllib2
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
        urllib2.install_opener(opener)

        if bRunOnce:
            xiamilogger.info('Start single-pass task...')
            for i, p in enumerate(configuration.pairs):
                xiami = XiamiHandler(p[0], p[1])
                while not xiami.process(debug=False):
                    xiamilogger.error('Process failed! try it again 15 seconds later...')
                    Time.sleep(15)
                if i != len(configuration.pairs) - 1:
                    Time.sleep(random.randint(30, 40))
            xiamilogger.info('Single-pass task was completed successfully. Quit.')
        else:
            # Loop
            current_day = datetime.now().day - 1
            while True:
                dt_current = datetime.now()
                if dt_current.day <> current_day: # new day comes
                    current_day = dt_current.day
                    random_time = RandomTimeGenerator(configuration.startime, configuration.endtime).get()
                    xiamilogger.info('Scheduled at: %s', random_time)
                    Time.sleep(5)
                    while True:
                        dt_current = datetime.now()
                        if dt_current.hour == random_time.hour and dt_current.minute == random_time.minute:
                            xiamilogger.info('Start scheduled task...')
                            # XiamiHandler
                            for i, p in enumerate(configuration.pairs):
                                xiami = XiamiHandler(p[0], p[1])
                                retry_times = 10
                                while not xiami.process(debug=False) and retry_times:
                                    xiamilogger.error('Process failed! try it again 15 seconds later...')
                                    Time.sleep(15)
                                    retry_times -= 1
                                if i != len(configuration.pairs) - 1:
                                    Time.sleep(random.randint(30, 40))
                            xiamilogger.info('Scheduled task was completed!')
                            break
                        Time.sleep(5) # check scheduled minute every 5 seconds
                Time.sleep(59) # check new days every 59 seconds

    except Exception, e:
        xiamilogger.error('fatal error, error = %s, traceback = %s', e, traceback.format_exc())


if __name__ == '__main__':
    main()
