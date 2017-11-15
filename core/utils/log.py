"""
Logging class that incorporates making file and console logs.
The actions taken can be altered for different message types and level ranges.
"""

from io import open
from builtins import range
from .py3 import textstring

from datetime import datetime
from . import dictionary, funcargparse
from . import files as file_utils
import os.path
import sys
import re

_depends_local=[".dictionary"]


level_classes={"misc":0, "note":10, "warning":20, "error":30, "failure":40}
_max_level=50
def normalize_level(level):
    if level in level_classes:
        return (level_classes[level],level)
    level=int(level)
    if level<0:
        return (0,"misc")
    if level<10:
        return (level,"misc")
    if level<20:
        return (level,"note")
    elif level<30:
        return (level,"warning")
    elif level<40:
        return (level,"error")
    elif level<50:
        return (level,"failure")
    else:
        return (_max_level-1,"failure")


kind_classes=["progress", "debug", "unexpected", "info", "exectime"]



class ILogAction(object):
    def report(self, message="", origin=None, kind=None, level="note", display=None, continued=False):
        raise NotImplementedError("ILogAction.report")
    
class LogAction_None(ILogAction):
    def report(self, message="", origin=None, kind=None, level="note", display=None, continued=False):
        pass
    
    
    
class IMessageLogAction(ILogAction):
    def __init__(self, display=("lko",""), min_display=("","")):
        ILogAction.__init__(self)
        self.display=display
        self.min_display=min_display
        self.continuing=False
        self.time_width=30
        self.level_width=8
        self.kind_width=10
        self.origin_width=0
        self.horizontal_width=self.time_width+self.level_width+self.kind_width+self.origin_width+20
        self.format_alias={}
    
    def format_time(self, time=None):
        time=time or datetime.today()
        return time.strftime("[%Y/%m/%d %H:%M:%S.%f]").ljust(self.time_width)    
    def format_level(self, level):
        lev_class=normalize_level(level)
        return "{0}({1:02d})".format(lev_class[1].upper(),lev_class[0]).ljust(self.level_width+4)
    def format_kind(self, kind):
        return ("["+kind.lower()+"]").ljust(self.kind_width)
    def format_origin(self, origin):
        return ("@"+origin).rjust(self.origin_width+1)
    
    def special_format(self, message):
        message=self.format_alias.get(message,message)
        parts=[p.strip() for p in message.split("|")]
        result=""
        for p in parts:
            if p.startswith("lineskip"):
                lstr=p[8:].strip()
                l=int(lstr) if lstr else 1
                result=result+"\n"*l
            if p.startswith("horizontal"):
                lstr=p[10:].strip()
                l=int(lstr) if lstr else self.horizontal_width
                result=result+"="*l
        return result
            
        
    def format_message(self, message="", origin=None, kind=None, level="note", display=None):
        if message.startswith("%%"):
            return self.special_format(message[2:])
        if display is None:
            display=self.display
        display=display[self.continuing] if isinstance(display,tuple) else display
        display=display+self.min_display[self.continuing]
        txt=""
        if "t" in display:
            txt=self.format_time()
        if "l" in display:
            l=self.format_level(level)
            txt=txt+l
        if kind and "k" in display:
            k=self.format_kind(kind)
            txt=txt+k if txt else k
        if origin and "o" in display:
            o=self.format_origin(origin)
            txt=txt+"  "+o if txt else o
        return txt+":  "+message if txt else message
    
    def report_text(self, txt):
        raise NotImplementedError("MessageLogAction.report_text")
    def report(self, message="", origin=None, kind=None, level="note", display=None, continued=False):
        if continued:
            self.report_text(self.format_message(message,origin,kind,level,display))
            self.continuing=True
        else:
            self.report_text(self.format_message(message,origin,kind,level,display)+"\n")
            self.continuing=False
    
    
class LogAction_Console(IMessageLogAction):
    def __init__(self):
        IMessageLogAction.__init__(self)
        self.horizontal_width=79
        self.format_alias={"linebreak":"lineskip", "parbreak":"lineskip 2", "pagebreak":"lineskip 4"}
    def report_text(self, txt):
        sys.stdout.write(txt)
        sys.stdout.flush()
        
        
class LogAction_File(IMessageLogAction):
    def __init__(self, path=None, display=("tlko",""), min_display=("tlko","")):
        IMessageLogAction.__init__(self,display=display,min_display=min_display)
        self.origin_width=20
        self.path=path
        self.horizontal_width=self.time_width+self.level_width+self.kind_width+self.origin_width+50
        self.format_alias={"linebreak":"", "parbreak":"lineskip", "pagebreak":"lineskip|horizontal|lineskip"}
    def report_text(self, txt):
        if self.path:
            try:
                with open(self.path,"a") as f:
                    f.write(txt)
            except IOError:
                folder=os.path.split(self.path)[0]
                file_utils.retry_ensure_dir(folder)
            
        
class LogError(Exception):
    def __init__(self, message):
        Exception.__init__(self)
        self.message=message
    def __str__(self):
        return self.message
class LogAction_Exception(IMessageLogAction):
    def __init__(self, display="tlko"):
        IMessageLogAction.__init__(self,display=display)
    def report_text(self, txt):
        raise LogError(txt)
    
    
class Log(object):
    def __init__(self, enabled=True):
        object.__init__(self)
        self.enabled=enabled
        self._actions_dict={"none":LogAction_None(), "console":LogAction_Console(), "exception":LogAction_Exception(), "file":LogAction_File()}
        self.add_named_action("file.error",LogAction_File())
        self._rules=dictionary.PrefixTree() # PrefixTree[dict[list[dict]]] PrefixTree -> origin, dict -> kind, list -> level, dict-> action:kwargs
        self._hash={}
        
    def enable(self, enabled=True):
        self.enabled=enabled
        
    def add_named_action(self, name, action):
        self._actions_dict[name]=action
    def get_named_action(self, name):
        return self._actions_dict[name]
    def set_logfile(self, path, name="file"):
        self._actions_dict.setdefault(name,LogAction_File()).path=path
    
    def _normalize_level_range(self, level_range):
        if level_range is None:
            level_range=(0,_max_level)
        elif not funcargparse.is_sequence(level_range):
            level_range=(level_range,_max_level)
        return [normalize_level(l)[0] for l in level_range]
    def add_rule(self, action, origin="", kind="*", level_range=None, **kwargs):
        action=self._actions_dict.get(action,action)
        kind_table=self._rules.setdefault((origin,"*"),({},))[0]
        level_table=kind_table.setdefault(kind,[ {} for _ in range(_max_level)])
        level_range=self._normalize_level_range(level_range)
        for l in range(*level_range):
            level_table[l][action]=kwargs
        self._hash.clear()
    def remove_rule(self, action=None, origin="", kind="*", level_range=None):
        action=self._actions_dict.get(action,action)
        if (origin,"*") not in self._rules:
            return
        kind_table=self._rules[origin,"*"][0]
        if kind not in kind_table:
            return
        level_table=kind_table[kind]
        level_range=self._normalize_level_range(level_range)
        for l in range(*level_range):
            if action is None:
                level_table[l].clear()
            elif action in level_table[l]: 
                del level_table[l][action]
        self._hash.clear()
    def _find_actions(self, origin, kind, level):
        pfx=self._rules.find_all_prefixes(origin,return_path=False)
        ks=[kind,"*"]
        actions=[]
        for kt, in pfx[::-1]:
            for k in ks:
                if k in kt:
                    acts=kt[k][level]
                    if "suppress" in acts:
                        return actions
                    actions+=list(acts.items())
        return actions
    def _find_actions_hashed(self, origin, kind, level):
        acts=self._hash.get((origin,kind,level),None)
        if acts is None:
            acts=self._find_actions(origin,kind,level)
            self._hash[origin,kind,level]=acts
        return acts
        
        
        
    def report(self, message="", origin=None, kind=None, level="note", display=None, continued=False, action=None):
        if not self.enabled:
            return
        if not isinstance(message,textstring):
            message=str(message)
        level=normalize_level(level)[0]
        if action is None:
            actions=self._find_actions_hashed(origin,kind,level)
        else:
            actions=[(self._actions_dict.get(action,action),{})]
        for a,kwargs in actions:
            if a!="suppress":
                if display is not None:
                    kwargs["display"]=display
                exc=None
                try:
                    a.report(message,origin or "",kind or "",level,continued=continued,**kwargs)
                except LogError as e:
                    exc=exc or e
                if exc is not None:
                    raise exc
        return len(actions)>0
            
    def error(self, message="", origin=None, kind="unexpected", level="error", display=None, continued=False, action=None):
        return self.report(message,origin,kind,level,display,continued,action)
    def prog(self, message="", origin=None, kind="progress", level="note", display=("o",""), continued=False, action=None):
        return self.report(message,origin,kind,level,display,continued,action)
    def progc(self, message="", origin=None, kind="progress", level="note", display=("o",""), continued=True, action=None):
        return self.report(message,origin,kind,level,display,continued,action)
    def info(self, message="", origin=None, kind="info", level="note", display=("o",""), continued=False, action=None):
        return self.report(message,origin,kind,level,display,continued,action)
    def infoc(self, message="", origin=None, kind="info", level="note", display=("o",""), continued=True, action=None):
        return self.report(message,origin,kind,level,display,continued,action)
    def debug(self, message="", origin=None, kind="debug", level="note", display=("o",""), continued=False, action=None):
        return self.report(message,origin,kind,level,display,continued,action)
    def debugc(self, message="", origin=None, kind="debug", level="note", display=("o",""), continued=True, action=None):
        return self.report(message,origin,kind,level,display,continued,action)
    def etime(self, message="", origin=None, kind="exectime", level="note", display=("to",""), continued=False, action=None):
        return self.report(message,origin,kind,level,display,continued,action)
    def etimec(self, message="", origin=None, kind="exectime", level="note", display=("to",""), continued=True, action=None):
        return self.report(message,origin,kind,level,display,continued,action)
    
    def enable_kind(self, kind, enable=True, level=0, action="console", **kwargs):
        actions=funcargparse.as_sequence(action)
        if enable:
            self.enable()
            for a in actions:
                self.add_rule(a,kind=kind,level_range=level,**kwargs)
        else:
            for a in actions:
                self.remove_rule(a,kind=kind)
                

#_default_log_line_re_date=r"\[([\d\s/:.]+)\]"
_default_log_line_re_time=r"\[(.+?)\]"
_default_log_line_time_fmt="%Y/%m/%d %H:%M:%S.%f"
_default_log_line_re_level=r"[\w\d]*?\((\d+)\)"
_default_log_line_re_kind=r"\[(.*?)\]"
_default_log_line_re_origin=r"@\s*(.*?)"
_default_log_line_re_description=r":\s*(.*)"
_default_log_line_re_parts=[_default_log_line_re_time,_default_log_line_re_level,
                            _default_log_line_re_kind,_default_log_line_re_origin,
                            _default_log_line_re_description]
_default_log_line_re="^"+r"\s*".join(["(?:"+p+")?" for p in _default_log_line_re_parts])+"$"
_default_log_line_rec=re.compile(_default_log_line_re)
_default_log_skip_re=r"^\s*[-=#]*\s*$"
_default_log_skip_rec=re.compile(_default_log_skip_re)
def _parse_log_line(line, strict=True, regex=None):
    regex=regex or _default_log_line_rec
    m=re.match(regex,line)
    if m is None:
        return None
    g=dict(zip(["time","level","kind","origin","message"],m.groups()))
    g["full"]=line
    if g["time"] is not None:
        try:
            g["time"]=datetime.strptime(g["time"],_default_log_line_time_fmt)
        except ValueError:
            if strict:
                return None
    if g["level"] is not None:
        try:
            g["level"]=int(g["level"])
        except ValueError:
            if strict:
                return None
    return g
    
    
def read_log(path, strict=True, required=None, bad_line_action="append"):
    required=required or {"message","time"}
    funcargparse.check_parameter_range(bad_line_action,"bad_line_action",{"append","ignore"})
    regex=_default_log_line_rec
    log_lines=[]
    with open(path,"r") as f:
        for line in f:
            line=line.strip()
            if re.match(_default_log_skip_rec,line):
                continue
            parsed=_parse_log_line(line,strict=strict,regex=regex)
            if parsed is None:
                bad_line=True
            else:
                bad_line=False
                for r in required:
                    if parsed.get(r) is None:
                        bad_line=True
                        break
            if bad_line:
                if bad_line_action=="append" and log_lines:
                    log_lines[-1]["message"]=(log_lines[-1]["message"] or "")+line
            else:
                log_lines.append(parsed)
    return log_lines
        
default_log=Log(enabled=False)
default_log.add_rule("exception",level_range="error")
default_log.add_rule("console",kind="unexpected")