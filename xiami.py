# encoding:utf-8
#-------------------------------------------------------------------------------
# Name:        xiami.py
# Purpose:
# Author:      windviki@gmail.com
# Created:     May 17, 2012
#-------------------------------------------------------------------------------

import re
import os
import urllib
import urllib2
import cookielib
import pprint

import logging
import logging.handlers
import random
import datetime
import time as Time

import traceback
from StringIO import StringIO
import gzip
import time

# Init urllib2
global_cookie_jar = cookielib.CookieJar()
global_cookie_processor = urllib2.HTTPCookieProcessor(global_cookie_jar)
global_opener = urllib2.build_opener(global_cookie_processor)
urllib2.install_opener(global_opener)


def initlogger():
    """
    Initialize logger
    """
    # Formatter
    logformatter = logging.Formatter('[%(asctime)s] [%(name)-12s] [%(filename)s(%(lineno)d)] %(message)s')

    # Filter
    xiamifilter = logging.Filter('xiami')

    # Rotating file logger
    #rotatingfilehandler = logging.handlers.RotatingFileHandler("xiami.log", "a", 5 * 1024 * 1024, 3)
    #rotatingfilehandler.setLevel(logging.DEBUG)
    #rotatingfilehandler.setFormatter(logformatter)
    #rotatingfilehandler.addFilter(xiamifilter)

    # Console logger
    consolehandler = logging.StreamHandler()
    consolehandler.setLevel(logging.DEBUG)
    consolehandler.setFormatter(logformatter)
    consolehandler.addFilter(xiamifilter)

    #logging.getLogger('').addHandler(rotatingfilehandler)
    logging.getLogger('').addHandler(consolehandler)

    logging.getLogger('').setLevel(logging.DEBUG)


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
        self.user_id = -1
        self.mail_content = {}

    def process(self, debug=False):
        self.mail_content = {}
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
        try:
            if isinstance(content, str):
                content = content.decode("utf-8")
                #pass
            if isinstance(content, unicode):
                pass
                #content = content.encode("utf-8")
        except UnicodeEncodeError:
            pass
        except UnicodeDecodeError:
            pass
        #签到%d天
        number = re.search(ur"\u7b7e\u5230(\d+)\u5929", content)
        if number:
            return number.group(1)
        return None

    def _login(self):
        try:
            xiami_token = ""
            # Main page
            main_page_request = urllib2.Request(self.main_page_url, None, self.common_headers)
            main_page_response = urllib2.urlopen(main_page_request)
            self.logger.info('_login requested main page ...')
            cookies = global_cookie_jar.make_cookies(main_page_response, main_page_request)
            if cookies:
                xiami_cookie = cookies[0]  # _xiamitoken
                #unsign_cookie = cookies[1]  # _unsign_token
                xiami_token = xiami_cookie.value
                #unsign_token = xiami_cookie.unsign_cookie
                self.logger.info('_xiamitoken = %s', pprint.pformat(cookies))
            else:
                self.logger.info('no cookies ...')

            # home
            time_value = int(time.time()*1000)
            main_page_home_request = urllib2.Request(
                "%s/index/home?_=%s" % (self.main_page_url, str(time_value)),
                None, self.home_headers)
            main_page_home_response = urllib2.urlopen(main_page_home_request)
            self.logger.info('_login requested index/home, time_value = %s', time_value)

            cookies = global_cookie_jar.make_cookies(main_page_home_response, main_page_home_request)
            if cookies:
                xiami_cookie = cookies[0]  # _xiamitoken
                #unsign_cookie = cookies[1]  # _unsign_token
                xiami_token = xiami_cookie.value
                #unsign_token = xiami_cookie.unsign_cookie
                #self.logger.info('_xiamitoken = %s', pprint.pformat(cookies))
            else:
                #self.logger.info('no cookies ...')
                pass

            self.login_data.update({"_xiamitoken": xiami_token})
            self.logger.info('token = %s', xiami_token)

            # Post login info
            login_request = urllib2.Request(self.login_url, urllib.urlencode(self.login_data), self.common_headers)
            login_response = urllib2.urlopen(login_request)
            self.user_id = global_cookie_jar._cookies[".xiami.com"]["/"]["user"].value.split('%22')[0]
            self.logger.info('user_id = %s', self.user_id)

            # Switch to mobile web page
            mobile_request = urllib2.Request(self.mobile_url, None, self.common_headers)
            mobile_response = urllib2.urlopen(mobile_request)
            #self.login_response = urllib2.urlopen(mobile_request).read()
            if mobile_response.info().get('Content-Encoding') == 'gzip':
                temp_buffer = StringIO(mobile_response.read())
                gf = gzip.GzipFile(fileobj=temp_buffer)
                self.login_response = gf.read()

            self.mail_content.update({"_login": "OK"})

            return True
        except urllib2.HTTPError, he:
            self.mail_content.update({"_login": he})
            self.logger.error('[Error] _login Failed! error = %s', he)
            self.login_response = ""
            return False
        except urllib2.URLError, ue:
            self.mail_content.update({"_login": ue})
            self.logger.error('[Error] _login Failed! error = %s', ue)
            self.login_response = ""
            return False
        except Exception, ce:
            self.mail_content.update({"_login": ce})
            self.logger.error('[Error] _login Failed! error = %s', ce)
            self.login_response = ""
            return False

    def _logout(self):
        # Logout
        try:
            logout_request = urllib2.Request(self.logout_url, None, self.logout_headers)
            self.logout_response = urllib2.urlopen(logout_request).read()
        except urllib2.HTTPError, he:
            self.logger.error('[Error] _logout Failed! error = %s', he)
            self.logout_response = ""
        except urllib2.URLError, ue:
            self.logger.error('[Error] _logout Failed! error = %s', ue)
            self.login_response = ""
            return False
        except Exception, ce:
            self.logger.error('[Error] _logout Failed! error = %s', ce)
            self.logout_response = ""

    def _checkin(self):
        try:
            mobile_sign_in_url = '%s/checkin/id/%s' % (self.mobile_url, self.user_id)
            sign_in_request = urllib2.Request(mobile_sign_in_url, None, self.common_headers)
            sign_in_response = urllib2.urlopen(sign_in_request)

            #self.check_in_response = urllib2.urlopen(sign_in_request).read()
            if sign_in_response.info().get('Content-Encoding') == 'gzip':
                temp_buffer = StringIO(sign_in_response.read())
                gf = gzip.GzipFile(fileobj=temp_buffer)
                self.check_in_response = gf.read()

            checked_days = self._get_day(self.check_in_response)
            self.logger.info('[Succeed] Checked in! user = %s, result = %s days',
                             self.username, checked_days)
            self.mail_content.update({"_checkin": "OK, %s days" % checked_days})

            return True
        except urllib2.HTTPError, he:
            self.mail_content.update({"_checkin": he})
            self.logger.error('[Error] _checkin Failed! error = %s', he)
            self.check_in_response = ""
            return False
        except urllib2.URLError, ue:
            self.mail_content.update({"_checkin": ue})
            self.logger.error('[Error] _checkin Failed! error = %s', ue)
            self.check_in_response = ""
            return False
        except Exception, ce:
            self.mail_content.update({"_checkin": ce})
            self.logger.error('[Error] _checkin Failed! error = %s', ce)
            self.check_in_response = ""
            return False

    def _dump(self):
        datas = {
            'login': self.login_response,
            #'checkin': self.check_in_response,
            #'logout': self.logout_response
        }
        logdir = os.path.join(os.getcwd(), "logs")
        if not os.path.exists(logdir):
            os.mkdir(logdir)
        for k, v in datas.items():
            output_file_name = os.path.join(logdir, "%s-%s.html" % (k, self.username))
            output_file = file(output_file_name, "wb")
            output_file.write(v)
            output_file.close()


users_info = [
    ("xxx@gmail.com", "xxx"),
    ("xxx@163.com", "xxx"),
]


def work():
    """
    Main process of auto checkin
    """
    # Logger
    initlogger()
    xiami_logger = logging.getLogger('xiami')
    xiami_logger.info('')
    xiami_logger.info('-' * 30)

    try:
        xiami_logger.info('Start single-pass task...')
        all_done = True
        results = {
            "title": "",
            "content": [],
        }
        for i, p in enumerate(users_info):
            xiami_handler = XiamiHandler(p[0], p[1])
            xiami_logger.info('Process %s...', p[0])
            retry = 5
            while not xiami_handler.process(debug=False):
                retry -= 1
                if retry < 0:
                    xiami_logger.error('Process %s failed! abort...', p[0])
                    break
                xiami_logger.error('Process %s failed! try it again 15 seconds later...', p[0])
                Time.sleep(15)
            if retry < 0:
                all_done = False
            results["content"].append({
                "user": p[0],
                "result": xiami_handler.mail_content,
            })
            if i != len(users_info) - 1:
                Time.sleep(random.randint(5, 10))
        xiami_logger.info('Single-pass task was completed successfully. Quit.')
        results["title"] = "XIAMI check-in %s %s" % (datetime.datetime.now().strftime("%Y%m%d"),
                                                     "OK" if all_done else "FAILED")
        return results

    except Exception, e:
        xiami_logger.error('fatal error, error = %s, traceback = %s', e, traceback.format_exc())
        return {}


if __name__ == '__main__':
    pprint.pprint(work())
