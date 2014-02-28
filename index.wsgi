# -*- coding:utf-8 -*- 
from bottle import Bottle, run
from sae import create_wsgi_app
from sae.mail import send_mail
import json
import pprint
import traceback
import xiami


app = Bottle()


@app.route('/')
def hello():
    return "Hello, world! - Bottle"


@app.route('/xiami_checkin_xxx', method='GET')
def xiami_checkin():
    try:
        results = xiami.work()
        send_mail("your_mail@xxx.com",
                  results.get("title", "SAE"),
                  pprint.pformat(results.get("content", "{}")),
                  ("smtp.sina.com", 25, "your_mail@xxx.com", "your_mail_password", False))
        page = results
    except Exception, err:
        page = traceback.format_exc()
    return page


@app.route('/mail_test_xxx', method='GET')
def mail_test():
    send_mail("your_mail@xxx.com",
              "Hello from SAE",
              "Test SAE mail",
              ("smtp.sina.com", 25, "your_mail@xxx.com", "your_mail_password", False))
    return "done"


application = create_wsgi_app(app)
