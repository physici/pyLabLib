"""
Mixing class for converting object into dict structure.
If attribute of an object is also serializable, it's going to be added to the top level of the dict.
Avoid recursive attributes (x.a=y, y.b=x), since they will lead to error while trying to load an object.
Avoid recursive containers (x[0]=y, y[0]=x), since they will lead to infinite loop while serializing.
Choice of the attributes to serialize is the same for all objects of the same class
"""

from future.utils import viewitems, viewvalues
from .py3 import textstring

import inspect
from . import string

class Serializable(object):
    _classes={}
    @staticmethod
    def _find_class(name, case_sensitive=True):
        """
        Find class name in the list of registered classes (can be case insensitive).
        Raise error if class isn't found.
        """
        try:
            _,cls=string.find_dict_string(name,Serializable._classes,case_sensitive=case_sensitive)
            return cls
        except KeyError:
            raise KeyError("can't find serializable class: {0}".format(name))
    @classmethod
    def _register_class(cls, name=None, attributes=None):
        """
        To be called after class definition to initialize necessary state. 
        """
        if name is None:
            name=cls.__name__
        cls._class_name=name
        cls._objects_count=0
        Serializable._classes[name]=cls
        if attributes is None:
            attributes={}
        attributes.setdefault("init","auto")
        if attributes["init"]=="auto": # derive from __init__ function
            attributes["init"]=inspect.getargspec(cls.__init__).args[1:] # first argument is self, last argument is name
            if len(attributes["init"])>0 and attributes["init"][-1]=="name": # last argument is name
                attributes["init"]=attributes["init"][:-1]
        attributes.setdefault("attr",[])
        cls._serializable_attributes=attributes
    @classmethod
    def _find_attribute_name(cls, name, case_sensitive=True):
        """
        Find attribute name in the attribute list (can be case insensitive) and return exact name and type (init or attr).
        Raise error if attribute isn't found.
        """
        for attr_type in ["init","attr"]:
            try:
                name=string.find_list_string(name,cls._serializable_attributes[attr_type],case_sensitive=case_sensitive)[1]
                return name,attr_type
            except KeyError:
                pass
        raise KeyError("can't find attribute {0} for class {1}".format(name,cls._class_name)) 
    @classmethod
    def _new_object_name(cls):
        """
        Generate new unique object name using counter.
        """
        name="{0}_{1}".format(cls._class_name,cls._objects_count)
        cls._objects_count=cls._objects_count+1
        return name
    
    def __init__(self, name=None):
        object.__init__(self)
        if not hasattr(self,"_object_name"):
            if name is None:
                name=self.__class__._new_object_name()
            self._object_name=name
    
    def _get_init_parameter(self, name):
        """
        Can be overloaded if init parameter isn't stored plainly in the object.
        If parameter doesn't need to be saved, raise AttirbuteError.
        """
        return getattr(self,name)
    def _get_attr_parameter(self, name):
        """
        Can be overloaded if attr parameter isn't stored plainly in the object.
        If parameter doesn't need to be saved, raise AttirbuteError.
        """
        return getattr(self,name)
    def _set_attr_parameter(self, name, value):
        """
        Can be overloaded if attr parameter setting isn't just assigning value.
        """
        setattr(self,name,value)
    
    def _serialize(self, full_dict):
        """
        Add the object into dictionary and return corresponding dict key (its name).
        """
        name=self._object_name
        if name in full_dict:
            return name #already serialized (or at least started)
        obj_dict=full_dict[name]={"__type__":self.__class__._class_name}
        for attr_name in self._serializable_attributes["init"]:
            try:
                attr=self._get_init_parameter(attr_name)
                obj_dict[attr_name]=_serialize(attr,full_dict)
            except AttributeError:
                pass
        for attr_name in self._serializable_attributes["attr"]:
            try:
                attr=self._get_attr_parameter(attr_name)
                obj_dict[attr_name]=_serialize(attr,full_dict)
            except AttributeError:
                pass
        return name
    @staticmethod
    def _deserialize(name, full_dict, loaded, case_sensitive=True):
        """
        Initiate and add object to the loaded from the description saved in full_dict.
        Just do initiation; assign additional attributes later if needed.
        If deserialization is case insensitive, exact name is the object key in the full_dict.
        """
        if name in loaded["#incomplete"]:
            raise ValueError("initialization loops for object {0}".format(name))
        try:
            name,obj_dict=string.find_dict_string(name,full_dict,case_sensitive=case_sensitive)
        except KeyError:
            raise KeyError("object isn't present in the dictionary: {0}".format(name))
        if name in loaded:
            return loaded[name] # already loaded
        cls=Serializable._find_class(obj_dict["__type__"],case_sensitive=case_sensitive)
        loaded["#incomplete"].append(name)
        init_dict={}
        for attr_name in obj_dict:
            if not string.string_equal(attr_name,"__type__",case_sensitive=case_sensitive):
                exact_name,attr_type=cls._find_attribute_name(attr_name,case_sensitive=case_sensitive)
                if attr_type=="init":
                    attr_val=_deserialize(obj_dict[attr_name],full_dict,loaded,case_sensitive=case_sensitive)
                    init_dict[exact_name]=attr_val
        loaded["#incomplete"].remove(name)
        obj=cls(**init_dict)
        obj._object_name=name
        loaded[name]=obj
        return obj
    def _set_additional_attributes(self, full_dict, loaded, case_sensitive=True):
        """
        Set additional attributes to the object after it has been loaded.
        """
        name=self._object_name
        if not name in full_dict:
            return
        obj_dict=full_dict[name]
        for attr_name in obj_dict:
            if not string.string_equal(attr_name,"__type__",case_sensitive=case_sensitive):
                exact_name,attr_type=self._find_attribute_name(attr_name,case_sensitive=case_sensitive)
                if attr_type=="attr":
                    attr_val=_deserialize(obj_dict[attr_name],full_dict,loaded)
                    self._set_attr_parameter(exact_name,attr_val)
    def _string_repr(self, attr_repr="repr"):
        params=[]
        if attr_repr=="repr":
            attr_repr=repr
        else:
            attr_repr=str
        for attr_name in self._serializable_attributes["init"]:
            try:
                attr=self._get_init_parameter(attr_name)
                params.append("{0}: {1}".format(attr_name,attr_repr(attr)))
            except AttributeError:
                pass
        for attr_name in self._serializable_attributes["attr"]:
            try:
                attr=self._get_init_parameter(attr_name)
                params.append("{0}: {1}".format(attr_name,attr_repr(attr)))
            except AttributeError:
                pass
        params=", ".join(params)
        return "("+params+")"


def _serialize(obj, full_dict, deep_copy=True):
    """
    Return value corresponding to a given object to be put as value in the dictionary (adds it to the full_dict if it's Serializable)
    All Serializable children are added by reference, all standard containers are added by value.
    """
    if isinstance(obj, Serializable):
        return obj._serialize(full_dict)
    if isinstance(obj, list):
        return [_serialize(elt,full_dict) for elt in obj]
    if isinstance(obj, tuple):
        return tuple([_serialize(elt,full_dict) for elt in obj])
    if isinstance(obj, dict):
        ser_dict={}
        for k,v in viewitems(obj):
            ser_dict[k]=_serialize(v,full_dict) # assume that k doesn't contain any serializable objects
        return ser_dict
    if deep_copy:
        try:
            return obj.copy()
        except AttributeError:
            pass
    return obj
    
def _deserialize(obj, full_dict, loaded, case_sensitive, deep_copy=True):
    """
    Construct value from the obj. If obj is a string, assume that it's a serializable object first; otherwise treat it as a string
    If value is Serializeble, add it into loaded 
    """
    if isinstance(obj,textstring):
        if obj in full_dict:
            return Serializable._deserialize(obj,full_dict,loaded,case_sensitive=case_sensitive)
        else: # assume that value is string itself
            return obj
    if isinstance(obj,list):
        return [_deserialize(elt,full_dict,loaded,case_sensitive=case_sensitive) for elt in obj]
    if isinstance(obj,tuple):
        return tuple([_deserialize(elt,full_dict,loaded,case_sensitive=case_sensitive) for elt in obj])
    if isinstance(obj,dict):
        deser_dict={}
        for k,v in viewitems(obj):
            deser_dict[k]=_deserialize(v,full_dict,loaded,case_sensitive=case_sensitive)
        return deser_dict
    if deep_copy:
        try:
            return obj.copy()
        except AttributeError:
            pass
    return obj


def init_name(object_name_arg="name"):
    """
    __init__ function decorator for convenience 
    """
    if object_name_arg is None:
        def decorator(init_func):
            def wrapped(self, *args, **vargs):
                Serializable.__init__(self)
                init_func(self,*args,**vargs)
            return wrapped
    else:
        def decorator(init_func):
            def wrapped(self, *args, **vargs):
                Serializable.__init__(self,vargs.get(object_name_arg,None))
                if object_name_arg in vargs:
                    del vargs[object_name_arg]
                init_func(self,*args,**vargs)
            return wrapped
    return decorator
init=init_name()


def to_dict(objects, full_dict=None, deep_copy=True):
    """
    Serialize list of objects into a dictionary.
    Only Serializable objects get added.
    """
    if full_dict is None:
        full_dict={}
    if isinstance(objects,Serializable):
        objects=[objects]
    for obj in objects:
        _serialize(obj,full_dict,deep_copy=deep_copy)
    return full_dict
def from_dict(full_dict, case_sensitive=True, deep_copy=True):
    """
    Deserialize objects from full_dict and return their dictionary.
    Only Serializable objects get returned.
    """
    loaded={"#incomplete":[]} #contains list of object currently being created, to escape recursive loops
    for name in full_dict:
        _deserialize(name,full_dict,loaded,case_sensitive=case_sensitive)
    del loaded["#incomplete"]
    for obj in viewvalues(loaded):
        obj._set_additional_attributes(full_dict,loaded,case_sensitive=case_sensitive)
    return loaded