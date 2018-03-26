class LimitError(ArithmeticError):
    def __init__(self, value, lower_limit=None, upper_limit=None):
        self.value=value
        self.lower_limit=lower_limit
        self.upper_limit=upper_limit
    def __str__(self):
        lb=self.lower_limit
        if lb==None:
            lb="-Inf"
        hb=self.upper_limit
        if hb==None:
            hb="+Inf"
        return "value {0} is out of limits ({1}, {2})".format(self.value, lb,hb)
class NumberLimit(object):
    """
    Class that given a number casts it to appropriate datatype and checks if it's inside given limits.
    If lower_limit or upper_limit are None, they are assumed to be infinite.
    The number is truncated to an appropriate bound if action=='truncate' or raises LimitError if action=='ignore'.
    """
    def __init__(self, lower_limit=None, upper_limit=None, action="ignore", value_type=None):
        object.__init__(self)
        if not value_type in [None,"float","int"]:
            raise ValueError("unrecognized value type: {0}".format(value_type))
        self.value_type=value_type
        lower_limit,upper_limit=self.cast(lower_limit), self.cast(upper_limit)
        if lower_limit!=None and upper_limit!=None and lower_limit>upper_limit:
            raise ValueError("impossible value range: ({0}, {1})".format(lower_limit,upper_limit))
        self.range=(lower_limit,upper_limit)
        if not action in ["coerce", "ignore"]:
            raise ValueError("unrecognized action: {0}".format(action))
        self.action=action
    def __call__(self, value):
        """
        Restrict value to the preset limit and type.
        Raise LimitError if value is outside bounds and action=='ignore'.
        """
        value=self.cast(value)
        if self.range[0]!=None and value<self.range[0]:
            if self.action=="coerce":
                return self.range[0]
            elif self.action=="ignore":
                raise LimitError(value,*self.range)
        elif self.range[1]!=None and value>self.range[1]:
            if self.action=="coerce":
                return self.range[1]
            elif self.action=="ignore":
                raise LimitError(value,*self.range)
        else:
            return value
    def cast(self, value):
        if value==None:
            return None
        if self.value_type=="float":
            return float(value)
        elif self.value_type=="int":
            return int(value)
        else:
            return value

def filter_limiter(pred):
    def wrapped(v):
        if not pred(v):
            raise LimitError(v)
        return v
    return wrapped

def as_limiter(limiter):
    if hasattr(limiter,"__call__"):
        return limiter
    if isinstance(limiter,tuple):
        return NumberLimit(*limiter)
    raise ValueError("unknown limiter: {}".format(limiter))