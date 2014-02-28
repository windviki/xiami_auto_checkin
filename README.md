# A Xiami auto-checkin script #

## Use it on SAE (xiami.py): ##

1. copy index.wsgi, config.yaml, xiami.py to your SAE SVN dir.

2. modify SAE name, email address and password in index.wsgi.

3. modify users_info in xiami.py (your xiami accout and password).

4. upload it to SAE. it will do checkin task everyday and send result to your mail.


## Use it as standalone tool (xiami.py): ##

1. modify users_info in xiami.py (your xiami accout and password).

2. python xiami.py to run it.

----------------------------------------------------------------------------

## Use as standalone script (xiami\_auto\_checkin.py): ##

**Deprecated. No update any more.**

1. rename config_template.txt to config.txt and set your username(email) and password.
As for multiple accouts, please split them with ','.
So that your password cannot contain a ',' :-(.

2. type command in shell or in cmd:
python xiami_auto_checkin.py
to run script in loop mode (e.g. use nohup to run it on a *nux server). It will login and check in everyday automatically.

3. type command in shell or in cmd:
python xiami_auto_checkin.py -q
to run script in single-pass mode. It will login and check in, then quit.

windviki(at)gmail.com


## windows上打包好的exe使用说明： ##

**Deprecated. No update any more.**

打包好的exe版本使用方法（win7，开机自启动，签到一次则退出）：

1. 解压到任意目录。

2. 拷贝dist目录下的config.txt到上层目录。即loop.bat和once.bat目录。

3. 在config.txt里面修改好自己的用户名密码。需要签到的只有一个账户，则可以只写一个。多个则用","隔开。

4. 右击once.bat，创建快捷方式。

5. 剪切该快捷方式到：
C:\Users\<你的windows用户名>\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup 
