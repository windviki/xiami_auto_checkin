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
#import urllib
#import urllib2
from datetime import *
#import cookielib
import requests
from bs4 import BeautifulSoup

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

    def __init__(self, start_time, end_time):
        _start = start_time.split(':')
        _end = end_time.split(':')
        _current = datetime.now()
        self.start_time = _current.replace(hour=int(_start[0]), minute=int(_start[1]))
        self.end_time = _current.replace(hour=int(_end[0]), minute=int(_end[1]))
        self.span = self.end_time - self.start_time

    def get(self):
        _current = datetime.now()
        _minutes = random.randint(1, get_total_seconds(self.span) / 60)
        _delta = timedelta(minutes=_minutes)
        if _current < self.start_time:
            return self.start_time + _delta
        elif _current > self.end_time:
            return _current.replace(minute=_current.minute + 1)
        else:
            _minutes = random.randint(1, get_total_seconds(self.end_time - _current) / 60 + 1)
            _delta = timedelta(minutes=_minutes)
            return _current + _delta


class ConfigHandler:
    """
    Configuration Handler
    """

    def __init__(self, config_path):
        self.config_section = "xiami"
        self.config_file = config_path
        self.config = ConfigParser.ConfigParser()
        self.config.read(self.config_file)
        if not self.config.has_section(self.config_section):
            self.config.add_section(self.config_section)
        self.username = []
        self.password = []
        if self.config.has_option(self.config_section, "username"):
            self.username = [x.strip() for x in self.config.get(self.config_section, "username").split(',') if
                             len(x) and not x.isspace()]
        if self.config.has_option(self.config_section, "password"):
            self.password = [x.strip() for x in self.config.get(self.config_section, "password").split(',') if
                             len(x) and not x.isspace()]
        self.pairs = zip(self.username, self.password)
        self.start_time = ""
        self.end_time = ""
        if self.config.has_option(self.config_section, "timerange"):
            _start_end = self.config.get(self.config_section, "timerange").split('-')
            self.start_time = _start_end[0]
            self.end_time = _start_end[1]

    def __getitem__(self, key):
        return self.config.get(self.config_section, key)

    def __setitem__(self, key, value):
        if type(value) == types.UnicodeType:
            value = value.encode("utf-8")
        self.config.set(self.config_section, key, value)

    def __delitem__(self, key):
        if self.config.has_option(self.config_section, key):
            self.config.remove_option(self.config_section, key)

    def save(self):
        self.config.write(open(self.config_file, "w+"))


class XiamiHandler:
    """
    Xiami web request/response Handler
    """

    def __init__(self, username, password):
        self.logger = logging.getLogger('xiami.XiamiHandler')
        self.username = username
        self.password = password
        self.login_response = ''
        self.check_in_response = ''
        self.logout_response = ''
        self.cookie = ''
        self.user_agent = "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                          "Chrome/27.0.1453.94 Safari/537.36"
        self.main_page_url = 'http://www.xiami.com'
        self.mobile_url = 'http://www.xiami.com/web'
        self.login_url = 'https://login.xiami.com/member/login'
        self.login_data = {
            '_xiamitoken': '',
            'done': "/",
            'type': '',
            'email': self.username,
            'password': self.password,
            'autologin': 0,
            'submit': '登 录',
        }
        self.common_headers = {
            'Referer': 'http://www.xiami.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip,deflate,sdch',
            'Accept-Language': 'zh-CN,en-US;q=0.8,en;q=0.6',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            #'Host': 'http://www.xiami.com',
            'Origin': 'http://www.xiami.com',
            'Pragma': 'no-cache',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': self.user_agent,
            'X-Requested-With': 'XMLHttpRequest',
        }
        self.home_headers = {
            'Referer': 'http://www.xiami.com/',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Encoding': 'gzip,deflate,sdch',
            'Accept-Language': 'zh-CN,en-US;q=0.8,en;q=0.6',
            'Cache-Control': 'must-revalidate',
            'Connection': 'keep-alive',
            #'Host': 'www.xiami.com',
            #'Origin': 'http://www.xiami.com',
            #'Pragma': 'no-cache',
            #'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': self.user_agent,
        }
        self.checkin_url = "http://www.xiami.com/task/signin"
        self.checkin_headers = {
            'Referer': 'http://www.xiami.com/home',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip,deflate,sdch',
            'Accept-Language': 'zh-CN,en-US;q=0.8,en;q=0.6',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Host': 'www.xiami.com',
            'Origin': 'http://www.xiami.com',
            'Pragma': 'no-cache',
            'Content-Length': '0',
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': self.user_agent,
        }
        self.logout_url = 'http://www.xiami.com/member/logout'
        self.logout_headers = {
            'Referer': 'http://www.xiami.com/member/mypm-notice',
            'User-Agent': self.user_agent,
        }
        self.session = requests.Session()
        self.user_id = -1

    def process(self, debug=False):
        login_result = self._login()
        if not login_result:
            self.logger.error('[Error] Login Failed! user = %s', self.username)
            return False
        result = False
        day = self._get_day(self.login_response)
        if day:
            # Checkin Already
            self.logger.info('[Succeed] Checkin Already! user = %s, result = %s days',
                             self.username, day)
            result = True
        else:
            result = self._checkin()
        if result:
            self._logout()
            self.logger.info('Logout, user = %s', self.username)
        if debug:
            self._dump()
        return result

    @staticmethod
    def _get_day(content):
        soup = BeautifulSoup(content)
        div = soup.find_all('div', {"class": "idh"})
        if div and len(div) > 1:
            number = re.search(r"\d+", div[1].text)
            if number:
                return number.group()
        return None

    def _login(self):
        try:
            xiami_token = self.session.get(self.main_page_url, headers=self.common_headers).cookies['_xiamitoken']
            self.login_data.update({"_xiamitoken": xiami_token})
            # Post login info
            login_post = self.session.post(self.login_url, headers=self.common_headers, data=self.login_data)
            self.user_id = self.session.cookies['user'].split('%22')[0]

            # Switch to mobile web page
            mobile_get = self.session.get(self.mobile_url, headers=self.common_headers)
            self.login_response = mobile_get.content
            return True
        except requests.HTTPError, he:
            self.logger.error('[Error] _login Failed! error = %s', he)
            self.login_response = ""
            return False
        except requests.RequestException, ue:
            self.logger.error('[Error] _login Failed! error = %s', ue)
            self.login_response = ""
            return False
        except Exception, ce:
            self.logger.error('[Error] _login Failed! error = %s', ce)
            self.login_response = ""
            return False

    def _logout(self):
        # Logout
        try:
            self.logout_response = self.session.get(self.logout_url, headers=self.logout_headers).content
        except requests.HTTPError, he:
            self.logger.error('[Error] _logout Failed! error = %s', he)
            self.logout_response = ""
        except Exception, ce:
            self.logger.error('[Error] _logout Failed! error = %s', ce)
            self.logout_response = ""

    def _checkin(self):
        try:
            mobile_sign_in_url = '%s/checkin/id/%s' % (self.mobile_url, self.user_id)
            self.session.post(mobile_sign_in_url, headers=self.common_headers)

            self.check_in_response = self.session.get(self.mobile_url, headers=self.common_headers).content
            self.logger.info('[Succeed] Checked in! user = %s, result = %s days',
                             self.username, self._get_day(self.check_in_response))
            return True
        except requests.HTTPError, he:
            self.logger.error('[Error] _checkin Failed! error = %s', he)
            self.check_in_response = ""
            return False
        except requests.RequestException, ue:
            self.logger.error('[Error] _checkin Failed! error = %s', ue)
            self.check_in_response = ""
            return False
        except Exception, ce:
            self.logger.error('[Error] _checkin Failed! error = %s', ce)
            self.check_in_response = ""
            return False

    def _dump(self):
        datas = {'login': self.login_response,
                 'checkin': self.check_in_response,
                 'logout': self.logout_response}
        logdir = os.path.join(os.getcwd(), "logs")
        if not os.path.exists(logdir):
            os.mkdir(logdir)
        for k, v in datas.items():
            output_file_name = os.path.join(logdir, "%s-%s.html" % (k, self.username))
            output_file = file(output_file_name, "wb")
            output_file.write(v)
            output_file.close()


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
    xiami_logger = logging.getLogger('xiami')
    xiami_logger.info('')
    xiami_logger.info('-' * 30)

    # Configuration
    config_filepath = os.path.join(os.getcwd(), 'config.txt')
    if not os.path.exists(config_filepath):
        xiami_logger.error('%s does not exist!', config_filepath)
        return

    configuration = ConfigHandler(config_filepath)
    if len(configuration.username) == 0 or len(configuration.password) == 0:
        xiami_logger.error('Not find username or password in configuration file!')
        return

    #import pprint
    #pprint.pprint(configuration.username)
    #pprint.pprint(configuration.password)
    #pprint.pprint(configuration.pairs)

    try:
        # Init urllib2
        #opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
        #urllib2.install_opener(opener)

        if bRunOnce:
            xiami_logger.info('Start single-pass task...')
            for i, p in enumerate(configuration.pairs):
                xiami = XiamiHandler(p[0], p[1])
                while not xiami.process(debug=False):
                    xiami_logger.error('Process failed! try it again 15 seconds later...')
                    Time.sleep(15)
                if i != len(configuration.pairs) - 1:
                    Time.sleep(random.randint(30, 40))
            xiami_logger.info('Single-pass task was completed successfully. Quit.')
        else:
            # Loop
            current_day = datetime.now().day - 1
            while True:
                dt_current = datetime.now()
                if dt_current.day != current_day:  # new day comes
                    current_day = dt_current.day
                    random_time = RandomTimeGenerator(configuration.start_time, configuration.end_time).get()
                    xiami_logger.info('Scheduled at: %s', random_time)
                    Time.sleep(5)
                    while True:
                        dt_current = datetime.now()
                        if dt_current.hour == random_time.hour and dt_current.minute == random_time.minute:
                            xiami_logger.info('Start scheduled task...')
                            # XiamiHandler
                            for i, p in enumerate(configuration.pairs):
                                xiami = XiamiHandler(p[0], p[1])
                                retry_times = 10
                                while not xiami.process(debug=False) and retry_times:
                                    xiami_logger.error('Process failed! try it again 15 seconds later...')
                                    Time.sleep(15)
                                    retry_times -= 1
                                if i != len(configuration.pairs) - 1:
                                    Time.sleep(random.randint(30, 40))
                            xiami_logger.info('Scheduled task was completed!')
                            break
                        Time.sleep(5)  # check scheduled minute every 5 seconds
                Time.sleep(59)  # check new days every 59 seconds

    except Exception, e:
        xiami_logger.error('fatal error, error = %s, traceback = %s', e, traceback.format_exc())


if __name__ == '__main__':
    main()
