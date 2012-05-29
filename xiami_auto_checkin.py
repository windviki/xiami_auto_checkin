#!/usr/bin/python
# encoding:utf-8
# +-----------------------------------------------------------------------------
# | Fork from huxuan
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
        _minutes = random.randint(1, self.span.total_seconds() / 60)
        _delta = timedelta(minutes=_minutes)
        if _current < self.starttime:
            return self.starttime + _delta
        elif _current > self.endtime:
            return _current.replace(minute=_current.minute + 1)
        else:
            _minutes = random.randint(1, (self.endtime - _current).total_seconds() / 60 + 1)
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
            self.username = [x.strip() for x in self.config.get(self.configsection, "username").split(',')]
        if self.config.has_option(self.configsection, "password"):
            self.password = [x.strip() for x in self.config.get(self.configsection, "password").split(',')]
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
        self.login_url = 'http://www.xiami.com/web/login'
        self.login_data = urllib.urlencode({'email':self.username,
                                       'password':self.password,
                                       'LoginButton':'登陆', })
        self.login_headers = {'Referer':'http://www.xiami.com/web/login',
                              'User-Agent':'Mozilla/5.0 (Windows NT 6.1; rv:12.0) Gecko/20100101 Firefox/12.0', }
        self.checkin_url = ''
        self.checkin_headers = {'Referer':'http://www.xiami.com/web',
                                'User-Agent':'Mozilla/5.0 (Windows NT 6.1; rv:12.0) Gecko/20100101 Firefox/12.0', }
        self.logout_url = 'http://www.xiami.com/member/logout'
        self.logout_headers = {'Referer':'http://www.xiami.com/member/mypm-notice',
                                'User-Agent':'Mozilla/5.0 (Windows NT 6.1; rv:12.0) Gecko/20100101 Firefox/12.0', }
        
    def process(self, debug=False):
        checkin_result = self._login()
        bresult = False
        if not checkin_result:
            # Checkin Already | Login Failed
            result = self._check(self.loginresponse)
            if result:
                self.logger.info('[Succeed] Checkin Already! user = %s, result = %s', self.username, result)
                bresult = True
            else:
                self.logger.error('[Error] Login Failed! user = %s', self.username)
                bresult = False
        else:
            self.checkin_url = 'http://www.xiami.com' + checkin_result.group(1)
            self.logger.debug('checkin url = %s', self.checkin_url)
            bresult = self._checkin()
        if bresult:
            self._logout()
            self.logger.info('Logout, user = %s', self.username)
        if debug:
            self._dump()
        return bresult
            
    def _check(self, response):
        """
        Check whether checkin is successful
    
        Args:
            response: the urlopen result of checkin
    
        Returns:
            If succeed, return a string like '已经连续签到**天'
                ** is the amount of continous checkin days
            If not, return False
        """
        pattern = re.compile(r'<div class="idh">(已连续签到\d+天)</div>')
        result = pattern.search(response)
        if result: 
            return result.group(1)
        return False

    def _login(self):
        # Login
        login_request = urllib2.Request(self.login_url, self.login_data, self.login_headers)
        self.loginresponse = urllib2.urlopen(login_request).read()
        # Checkin
        checkin_pattern = re.compile(r'<a class="check_in" href="(.*?)">')
        checkin_result = checkin_pattern.search(self.loginresponse)
        return checkin_result
    
    def _logout(self):
        # Logout
        logout_request = urllib2.Request(self.logout_url, None, self.logout_headers)
        self.logoutresponse = urllib2.urlopen(logout_request).read()
        
    def _checkin(self):
        checkin_request = urllib2.Request(self.checkin_url, None, self.checkin_headers)
        self.checkinresponse = urllib2.urlopen(checkin_request).read()
    
        # Result
        result = self._check(self.checkinresponse)
        if result:
            self.logger.info('[Succeed] Checkin Succeed! user = %s, result = %s', self.username, result)
            return True
        else:
            self.logger.error('[Error] Checkin Failed!')
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
        xiamilogger.error('Not find username or password in configuration!')
        return
    
    # Init urllib2
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
    urllib2.install_opener(opener)

    if bRunOnce:
        xiamilogger.info('Start single-pass task...')
        for p in configuration.pairs:
            xiami = XiamiHandler(p[0], p[1])
            xiami.process()
            Time.sleep(random.randint(0, 10))
        xiamilogger.info('Single-pass task was completed. Quit.')
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
                        xiamilogger.info('Scheduled task was started!')
                        # XiamiHandler
                        for p in configuration.pairs:
                            xiami = XiamiHandler(p[0], p[1])
                            xiami.process()
                        xiamilogger.info('Scheduled task was completed!')
                        break
                    Time.sleep(5)
            Time.sleep(59)


if __name__ == '__main__':
    main()
