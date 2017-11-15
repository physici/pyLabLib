textstring=(basestring,) if (str is bytes) else (str,)
anystring=(str, unicode) if (str is bytes) else (str,bytes)