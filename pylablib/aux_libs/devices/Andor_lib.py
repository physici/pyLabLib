from ...core.utils import functions
from .misc import default_lib_folder, load_lib

import ctypes
import collections
import os.path

import numpy as np



##### Constants #####

Andor_statuscodes = {
		20001: "DRV_ERROR_CODES",
		20002: "DRV_SUCCESS",
		20003: "DRV_VXDNOTINSTALLED",
		20004: "DRV_ERROR_SCAN",
		20005: "DRV_ERROR_CHECK_SUM",
		20006: "DRV_ERROR_FILELOAD",
		20007: "DRV_UNKNOWN_FUNCTION",
		20008: "DRV_ERROR_VXD_INIT",
		20009: "DRV_ERROR_ADDRESS",
		20010: "DRV_ERROR_PAGELOCK",
		20011: "DRV_ERROR_PAGEUNLOCK",
		20012: "DRV_ERROR_BOARDTEST",
		20013: "DRV_ERROR_ACK",
		20014: "DRV_ERROR_UP_FIFO",
		20015: "DRV_ERROR_PATTERN",
		20017: "DRV_ACQUISITION_ERRORS",
		20018: "DRV_ACQ_BUFFER",
		20019: "DRV_ACQ_DOWNFIFO_FULL",
		20020: "DRV_PROC_UNKONWN_INSTRUCTION",
		20021: "DRV_ILLEGAL_OP_CODE",
		20022: "DRV_KINETIC_TIME_NOT_MET",
		20023: "DRV_ACCUM_TIME_NOT_MET",
		20024: "DRV_NO_NEW_DATA",
		20025: "DRV_PCI_DMA_FAIL",
		20026: "DRV_SPOOLERROR",
		20027: "DRV_SPOOLSETUPERROR",
		20028: "DRV_FILESIZELIMITERROR",
		20029: "DRV_ERROR_FILESAVE",
		20033: "DRV_TEMPERATURE_CODES",
		20034: "DRV_TEMPERATURE_OFF",
		20035: "DRV_TEMPERATURE_NOT_STABILIZED",
		20036: "DRV_TEMPERATURE_STABILIZED",
		20037: "DRV_TEMPERATURE_NOT_REACHED",
		20038: "DRV_TEMPERATURE_OUT_RANGE",
		20039: "DRV_TEMPERATURE_NOT_SUPPORTED",
		20040: "DRV_TEMPERATURE_DRIFT",
		20049: "DRV_GENERAL_ERRORS",
		20050: "DRV_INVALID_AUX",
		20051: "DRV_COF_NOTLOADED",
		20052: "DRV_FPGAPROG",
		20053: "DRV_FLEXERROR",
		20054: "DRV_GPIBERROR",
		20055: "DRV_EEPROMVERSIONERROR",
		20064: "DRV_DATATYPE",
		20065: "DRV_DRIVER_ERRORS",
		20066: "DRV_P1INVALID",
		20067: "DRV_P2INVALID",
		20068: "DRV_P3INVALID",
		20069: "DRV_P4INVALID",
		20070: "DRV_INIERROR",
		20071: "DRV_COFERROR",
		20072: "DRV_ACQUIRING",
		20073: "DRV_IDLE",
		20074: "DRV_TEMPCYCLE",
		20075: "DRV_NOT_INITIALIZED",
		20076: "DRV_P5INVALID",
		20077: "DRV_P6INVALID",
		20078: "DRV_INVALID_MODE",
		20079: "DRV_INVALID_FILTER",
		20080: "DRV_I2CERRORS",
		20081: "DRV_I2CDEVNOTFOUND",
		20082: "DRV_I2CTIMEOUT",
		20083: "DRV_P7INVALID",
		20084: "DRV_P8INVALID",
		20085: "DRV_P9INVALID",
		20086: "DRV_P10INVALID",
		20087: "DRV_P11INVALID",
		20089: "DRV_USBERROR",
		20090: "DRV_IOCERROR",
		20091: "DRV_VRMVERSIONERROR",
		20092: "DRV_GATESTEPERROR",
		20093: "DRV_USB_INTERRUPT_ENDPOINT_ERROR",
		20094: "DRV_RANDOM_TRACK_ERROR",
		20095: "DRV_INVALID_TRIGGER_MODE",
		20096: "DRV_LOAD_FIRMWARE_ERROR",
		20097: "DRV_DIVIDE_BY_ZERO_ERROR",
		20098: "DRV_INVALID_RINGEXPOSURES",
		20099: "DRV_BINNING_ERROR",
		20100: "DRV_INVALID_AMPLIFIER",
		20101: "DRV_INVALID_COUNTCONVERT_MODE",
		20990: "DRV_ERROR_NOCAMERA",
		20991: "DRV_NOT_SUPPORTED",
		20992: "DRV_NOT_AVAILABLE",
		20115: "DRV_ERROR_MAP",
		20116: "DRV_ERROR_UNMAP",
		20117: "DRV_ERROR_MDL",
		20118: "DRV_ERROR_UNMDL",
		20119: "DRV_ERROR_BUFFSIZE",
		20121: "DRV_ERROR_NOHANDLE",
		20130: "DRV_GATING_NOT_AVAILABLE",
		20131: "DRV_FPGA_VOLTAGE_ERROR",
		20150: "DRV_OW_CMD_FAIL",
		20151: "DRV_OWMEMORY_BAD_ADDR",
		20152: "DRV_OWCMD_NOT_AVAILABLE",
		20153: "DRV_OW_NO_SLAVES",
		20154: "DRV_OW_NOT_INITIALIZED",
		20155: "DRV_OW_ERROR_SLAVE_NUM",
		20156: "DRV_MSTIMINGS_ERROR",
		20173: "DRV_OA_NULL_ERROR",
		20174: "DRV_OA_PARSE_DTD_ERROR",
		20175: "DRV_OA_DTD_VALIDATE_ERROR",
		20176: "DRV_OA_FILE_ACCESS_ERROR",
		20177: "DRV_OA_FILE_DOES_NOT_EXIST",
		20178: "DRV_OA_XML_INVALID_OR_NOT_FOUND_ERROR",
		20179: "DRV_OA_PRESET_FILE_NOT_LOADED",
		20180: "DRV_OA_USER_FILE_NOT_LOADED",
		20181: "DRV_OA_PRESET_AND_USER_FILE_NOT_LOADED",
		20182: "DRV_OA_INVALID_FILE",
		20183: "DRV_OA_FILE_HAS_BEEN_MODIFIED",
		20184: "DRV_OA_BUFFER_FULL",
		20185: "DRV_OA_INVALID_STRING_LENGTH",
		20186: "DRV_OA_INVALID_CHARS_IN_NAME",
		20187: "DRV_OA_INVALID_NAMING",
		20188: "DRV_OA_GET_CAMERA_ERROR",
		20189: "DRV_OA_MODE_ALREADY_EXISTS",
		20190: "DRV_OA_STRINGS_NOT_EQUAL",
		20191: "DRV_OA_NO_USER_DATA",
		20192: "DRV_OA_VALUE_NOT_SUPPORTED",
		20193: "DRV_OA_MODE_DOES_NOT_EXIST",
		20194: "DRV_OA_CAMERA_NOT_SUPPORTED",
		20195: "DRV_OA_FAILED_TO_GET_MODE",
		20211: "DRV_PROCESSING_FAILED",
}
def text_status(status):
    if status in Andor_statuscodes:
        return Andor_statuscodes[status]
    raise AndorLibError("unrecognized status code: {}".format(status))

Andor_AcqMode = {
        1: "AC_ACQMODE_SINGLE",
		2: "AC_ACQMODE_VIDEO",
		4: "AC_ACQMODE_ACCUMULATE",
		8: "AC_ACQMODE_KINETIC",
		16: "AC_ACQMODE_FRAMETRANSFER",
		32: "AC_ACQMODE_FASTKINETICS",
		64: "AC_ACQMODE_OVERLAP",
}

Andor_ReadMode = {
		1: "AC_READMODE_FULLIMAGE",
		2: "AC_READMODE_SUBIMAGE",
		4: "AC_READMODE_SINGLETRACK",
		8: "AC_READMODE_FVB",
		16: "AC_READMODE_MULTITRACK",
		32: "AC_READMODE_RANDOMTRACK",
		64: "AC_READMODE_MULTITRACKSCAN",
}

Andor_TriggerMode = {
		1: "AC_TRIGGERMODE_INTERNAL",
		2: "AC_TRIGGERMODE_EXTERNAL",
		4: "AC_TRIGGERMODE_EXTERNAL_FVB_EM",
		8: "AC_TRIGGERMODE_CONTINUOUS",
		16: "AC_TRIGGERMODE_EXTERNALSTART",
		32: "AC_TRIGGERMODE_EXTERNALEXPOSURE",
		0x40: "AC_TRIGGERMODE_INVERTED",
		0x80: "AC_TRIGGERMODE_EXTERNAL_CHARGESHIFTING",
}

Andor_CameraType = {
		0: "AC_CAMERATYPE_PDA",
		1: "AC_CAMERATYPE_IXON",
		2: "AC_CAMERATYPE_ICCD",
		3: "AC_CAMERATYPE_EMCCD",
		4: "AC_CAMERATYPE_CCD",
		5: "AC_CAMERATYPE_ISTAR",
		6: "AC_CAMERATYPE_VIDEO",
		7: "AC_CAMERATYPE_IDUS",
		8: "AC_CAMERATYPE_NEWTON",
		9: "AC_CAMERATYPE_SURCAM",
		10: "AC_CAMERATYPE_USBICCD",
		11: "AC_CAMERATYPE_LUCA",
		12: "AC_CAMERATYPE_RESERVED",
		13: "AC_CAMERATYPE_IKON",
		14: "AC_CAMERATYPE_INGAAS",
		15: "AC_CAMERATYPE_IVAC",
		16: "AC_CAMERATYPE_UNPROGRAMMED",
		17: "AC_CAMERATYPE_CLARA",
		18: "AC_CAMERATYPE_USBISTAR",
		19: "AC_CAMERATYPE_SIMCAM",
		20: "AC_CAMERATYPE_NEO",
		21: "AC_CAMERATYPE_IXONULTRA",
		22: "AC_CAMERATYPE_VOLMOS",
}

Andor_PixelMode = {
		1: "AC_PIXELMODE_8BIT",
		2: "AC_PIXELMODE_14BIT",
		4: "AC_PIXELMODE_16BIT",
		8: "AC_PIXELMODE_32BIT",
        
		0x000000: "AC_PIXELMODE_MONO",
		0x010000: "AC_PIXELMODE_RGB",
		0x020000: "AC_PIXELMODE_CMY",
}

Andor_SetFunction = {
		0x01: "AC_SETFUNCTION_VREADOUT",
		0x02: "AC_SETFUNCTION_HREADOUT",
		0x04: "AC_SETFUNCTION_TEMPERATURE",
		0x08: "AC_SETFUNCTION_MCPGAIN",
		0x10: "AC_SETFUNCTION_EMCCDGAIN",
		0x20: "AC_SETFUNCTION_BASELINECLAMP",
		0x40: "AC_SETFUNCTION_VSAMPLITUDE",
		0x80: "AC_SETFUNCTION_HIGHCAPACITY",
		0x0100: "AC_SETFUNCTION_BASELINEOFFSET",
		0x0200: "AC_SETFUNCTION_PREAMPGAIN",
		0x0400: "AC_SETFUNCTION_CROPMODE",
		0x0800: "AC_SETFUNCTION_DMAPARAMETERS",
		0x1000: "AC_SETFUNCTION_HORIZONTALBIN",
		0x2000: "AC_SETFUNCTION_MULTITRACKHRANGE",
		0x4000: "AC_SETFUNCTION_RANDOMTRACKNOGAPS",
		0x8000: "AC_SETFUNCTION_EMADVANCED",
		0x010000: "AC_SETFUNCTION_GATEMODE",
		0x020000: "AC_SETFUNCTION_DDGTIMES",
		0x040000: "AC_SETFUNCTION_IOC",
		0x080000: "AC_SETFUNCTION_INTELLIGATE",
		0x100000: "AC_SETFUNCTION_INSERTION_DELAY",
		0x200000: "AC_SETFUNCTION_GATESTEP",
		0x400000: "AC_SETFUNCTION_TRIGGERTERMINATION",
		0x800000: "AC_SETFUNCTION_EXTENDEDNIR",
		0x1000000: "AC_SETFUNCTION_SPOOLTHREADCOUNT",
		0x2000000: "AC_SETFUNCTION_REGISTERPACK",
}

Andor_GetFunction = {
		0x01: "AC_GETFUNCTION_TEMPERATURE",
		0x02: "AC_GETFUNCTION_TARGETTEMPERATURE",
		0x04: "AC_GETFUNCTION_TEMPERATURERANGE",
		0x08: "AC_GETFUNCTION_DETECTORSIZE",
		0x10: "AC_GETFUNCTION_MCPGAIN",
		0x20: "AC_GETFUNCTION_EMCCDGAIN",
		0x40: "AC_GETFUNCTION_HVFLAG",
		0x80: "AC_GETFUNCTION_GATEMODE",
		0x0100: "AC_GETFUNCTION_DDGTIMES",
		0x0200: "AC_GETFUNCTION_IOC",
		0x0400: "AC_GETFUNCTION_INTELLIGATE",
		0x0800: "AC_GETFUNCTION_INSERTION_DELAY",
		0x1000: "AC_GETFUNCTION_GATESTEP",
		0x2000: "AC_GETFUNCTION_PHOSPHORSTATUS",
		0x4000: "AC_GETFUNCTION_MCPGAINTABLE",
		0x8000: "AC_GETFUNCTION_BASELINECLAMP",
}

Andor_Features = {
		1: "AC_FEATURES_POLLING",
		2: "AC_FEATURES_EVENTS",
		4: "AC_FEATURES_SPOOLING",
		8: "AC_FEATURES_SHUTTER",
		16: "AC_FEATURES_SHUTTEREX",
		32: "AC_FEATURES_EXTERNAL_I2C",
		64: "AC_FEATURES_SATURATIONEVENT",
		128: "AC_FEATURES_FANCONTROL",
		256: "AC_FEATURES_MIDFANCONTROL",
		512: "AC_FEATURES_TEMPERATUREDURINGACQUISITION",
		1024: "AC_FEATURES_KEEPCLEANCONTROL",
		0x0800: "AC_FEATURES_DDGLITE",
		0x1000: "AC_FEATURES_FTEXTERNALEXPOSURE",
		0x2000: "AC_FEATURES_KINETICEXTERNALEXPOSURE",
		0x4000: "AC_FEATURES_DACCONTROL",
		0x8000: "AC_FEATURES_METADATA",
		0x10000: "AC_FEATURES_IOCONTROL",
		0x20000: "AC_FEATURES_PHOTONCOUNTING",
		0x40000: "AC_FEATURES_COUNTCONVERT",
		0x80000: "AC_FEATURES_DUALMODE",
		0x100000: "AC_FEATURES_OPTACQUIRE",
		0x200000: "AC_FEATURES_REALTIMESPURIOUSNOISEFILTER",
		0x400000: "AC_FEATURES_POSTPROCESSSPURIOUSNOISEFILTER",
		0x800000: "AC_FEATURES_DUALPREAMPGAIN",
		0x1000000: "AC_FEATURES_DEFECT_CORRECTION",
		0x2000000: "AC_FEATURES_STARTOFEXPOSURE_EVENT",
		0x4000000: "AC_FEATURES_ENDOFEXPOSURE_EVENT",
		0x8000000: "AC_FEATURES_CAMERALINK",
}

Andor_EMGain = {
		1: "AC_EMGAIN_8BIT",
		2: "AC_EMGAIN_12BIT",
		4: "AC_EMGAIN_LINEAR12",
		8: "AC_EMGAIN_REAL12",
}




class AndorLibError(RuntimeError):
	def __init__(self, func, code):
		self.func=func
		self.code=code
		self.text_code=Andor_statuscodes.get(code,"UNKNOWN")
		msg="function '{}' raised error {}({})".format(func,code,self.text_code)
		RuntimeError.__init__(self,msg)
def errcheck(passing=None):
	passing=set(passing) if passing is not None else set()
	passing.add(20002) # always allow success
	def checker(result, func, arguments):
		if result not in passing:
			# print("function '{}' raised error {}({})".format(func.__name__,result,Andor_statuscodes.get(result,"UNKNOWN")))
			raise AndorLibError(func.__name__,result)
		return Andor_statuscodes[result]
	return checker


def setup_func(func, argtypes, passing=None):
	func.argtypes=argtypes
	func.restype=ctypes.c_uint32
	func.errcheck=errcheck(passing=passing)

def ctf_simple(func, argtypes, argnames, passing=None):
	sign=functions.FunctionSignature(argnames,name=func.__name__)
	setup_func(func,argtypes,passing=passing)
	def wrapped_func(*args):
		func(*args)
	return sign.wrap_function(wrapped_func)

def _get_value(rval):
	try:
		return rval.value
	except AttributeError:
		return rval
def ctf_rval(func, rtype, argtypes, argnames, prep_rval=None, conv_rval=None, passing=None):
	rval_idx=argtypes.index(None)
	argtypes=list(argtypes)
	argtypes[rval_idx]=ctypes.POINTER(rtype)
	sign=functions.FunctionSignature(argnames,name=func.__name__)
	setup_func(func,argtypes,passing=passing)
	def wrapped_func(*args):
		rval=rtype()
		if prep_rval:
			rval=prep_rval(rval,*args)
		nargs=args[:rval_idx]+(ctypes.byref(rval),)+args[rval_idx:]
		func(*nargs)
		if conv_rval:
			return conv_rval(rval,*args)
		else:
			return _get_value(rval)
	return sign.wrap_function(wrapped_func)
def ctf_rval_str(func, maxlen, argtypes, argnames, passing=None):
	rval_idx=argtypes.index(None)
	argtypes=list(argtypes)
	argtypes[rval_idx]=ctypes.c_char_p
	sign=functions.FunctionSignature(argnames,name=func.__name__)
	setup_func(func,argtypes,passing=passing)
	def wrapped_func(*args):
		rval=ctypes.create_string_buffer(maxlen)
		nargs=args[:rval_idx]+(rval,)+args[rval_idx:]
		func(*nargs)
		return rval.value
	return sign.wrap_function(wrapped_func)
def ctf_rvals(func, rtypes, argtypes, argnames, passing=None):
	template=list(argtypes)
	argtypes=list(argtypes)
	ridx=0
	for i,t in enumerate(argtypes):
		if t is None:
			argtypes[i]=ctypes.POINTER(rtypes[ridx])
			ridx+=1
	sign=functions.FunctionSignature(argnames,name=func.__name__)
	setup_func(func,argtypes,passing=passing)
	def wrapped_func(*args):
		rvals=[rt() for rt in rtypes]
		nargs=[]
		ridx=0
		aidx=0
		for i,t in enumerate(template):
			if t is None:
				nargs.append(rvals[ridx])
				ridx+=1
			else:
				nargs.append(args[aidx])
				aidx+=1
		func(*nargs)
		return tuple([_get_value(rv) for rv in rvals])
	return sign.wrap_function(wrapped_func)

def ctf_buff(func, argtypes, argnames, build_buff=None, conv_buff=None, passing=None):
	buff_idx=argtypes.index(None)
	argtypes=list(argtypes)
	argtypes[buff_idx]=ctypes.c_char_p
	sign=functions.FunctionSignature(argnames,name=func.__name__)
	setup_func(func,argtypes,passing=passing)
	def wrapped_func(*args):
		buff=build_buff(*args)
		nargs=args[:buff_idx]+(buff,)+args[buff_idx:]
		func(*nargs)
		return conv_buff(buff,*args)
	return sign.wrap_function(wrapped_func)

def _int_to_enumlst(num, enums):
	lst=[]
	for k,v in enums.items():
		if num&k:
			lst.append(v)
	return lst

class AndorCapabilities(ctypes.Structure):
	_fields_=[  ("Size",ctypes.c_int32),
				("AcqModes",ctypes.c_int32),
				("ReadModes",ctypes.c_int32),
				("TriggerModes",ctypes.c_int32),
				("CameraType",ctypes.c_int32),
				("PixelMode",ctypes.c_int32),
				("SetFunctions",ctypes.c_int32),
				("GetFunctions",ctypes.c_int32),
				("Features",ctypes.c_int32),
				("PCICard",ctypes.c_int32),
				("EMGainCapability",ctypes.c_int32),
				("FTReadModes",ctypes.c_int32) ]
AndorCapabilities_p=ctypes.POINTER(AndorCapabilities)
def AndorCapabilities_prep(val, *args):
	val.Size=ctypes.sizeof(val)
	return val
TAndorCapabilities=collections.namedtuple("TAndorCapabilities",
		["AcqModes", "ReadModes", "TriggerModes", "CameraType", "PixelMode", "SetFunctions", "GetFunctions", "Features", "PCICard", "EMGainCapability", "FTReadModes"])
def AndorCapabilities_conv(val, *args):
	AcqModes=_int_to_enumlst(val.AcqModes,Andor_AcqMode)
	ReadModes=_int_to_enumlst(val.ReadModes,Andor_ReadMode)
	TriggerModes=_int_to_enumlst(val.AcqModes,Andor_TriggerMode)
	CameraType=Andor_CameraType.get(val.CameraType&0x1F,"UNKNOWN")
	PixelMode=_int_to_enumlst(val.PixelMode&0xFFFF,Andor_PixelMode)+[Andor_PixelMode.get(val.PixelMode&0xFFFF0000,"UNKNOWN")]
	SetFunctions=_int_to_enumlst(val.SetFunctions,Andor_SetFunction)
	GetFunctions=_int_to_enumlst(val.GetFunctions,Andor_GetFunction)
	Features=_int_to_enumlst(val.Features,Andor_Features)
	EMGainCapability=_int_to_enumlst(val.EMGainCapability,Andor_EMGain)
	FTReadModes=_int_to_enumlst(val.FTReadModes,Andor_ReadMode)
	return TAndorCapabilities(AcqModes,ReadModes,TriggerModes,CameraType,PixelMode,SetFunctions,GetFunctions,Features,val.PCICard,EMGainCapability,FTReadModes)






try:

	lib_path=os.path.join(default_lib_folder,"atmcd.dll")
	lib=load_lib(lib_path)
	##### Functions definitions #####

	Initialize=ctf_simple(lib.Initialize, [ctypes.c_char_p], ["dir"])
	ShutDown=ctf_simple(lib.ShutDown, [], [])
	GetAvailableCameras=ctf_rval(lib.GetAvailableCameras, ctypes.c_int32, [None], [])
	GetCameraHandle=ctf_rval(lib.GetCameraHandle, ctypes.c_int32, [ctypes.c_uint32,None], ["idx"])
	GetCurrentCamera=ctf_rval(lib.GetCurrentCamera, ctypes.c_int32, [None], [])
	SetCurrentCamera=ctf_simple(lib.SetCurrentCamera, [ctypes.c_int32], ["handle"])

	GetCapabilities=ctf_rval(lib.GetCapabilities, AndorCapabilities, [None], [], prep_rval=AndorCapabilities_prep, conv_rval=AndorCapabilities_conv)
	GetControllerCardModel=ctf_rval_str(lib.GetControllerCardModel, 256, [None], [])
	GetHeadModel=ctf_rval_str(lib.GetHeadModel, 256, [None], [])
	GetCameraSerialNumber=ctf_rval(lib.GetCameraSerialNumber, ctypes.c_int32, [None], [])
	SetFanMode=ctf_simple(lib.SetFanMode, [ctypes.c_int32], ["mode"])

	InAuxPort=ctf_rval(lib.InAuxPort, ctypes.c_int32, [ctypes.c_int32,None], ["port"])
	OutAuxPort=ctf_simple(lib.OutAuxPort, [ctypes.c_int32,ctypes.c_int32], ["port","state"])

	SetTriggerMode=ctf_simple(lib.SetTriggerMode, [ctypes.c_int32], ["mode"])
	GetExternalTriggerTermination=ctf_rval(lib.GetExternalTriggerTermination, ctypes.c_int32, [None], [])
	SetExternalTriggerTermination=ctf_simple(lib.SetExternalTriggerTermination, [ctypes.c_int32], ["termination"])
	GetTriggerLevelRange=ctf_rvals(lib.GetTriggerLevelRange, [ctypes.c_float,ctypes.c_float], [None,None], [])
	SetTriggerLevel=ctf_simple(lib.SetTriggerLevel, [ctypes.c_float], ["mode"])
	SetTriggerInvert=ctf_simple(lib.SetTriggerInvert, [ctypes.c_int32], ["mode"])
	IsTriggerModeAvailable=ctf_simple(lib.IsTriggerModeAvailable, [ctypes.c_int32], ["mode"])
	SendSoftwareTrigger=ctf_simple(lib.SendSoftwareTrigger, [], [])

	setup_func(lib.GetTemperature ,[ctypes.POINTER(ctypes.c_int32)], passing={20034,20035,20036,20037,20040})
	def GetTemperature():
		temp=ctypes.c_int32()
		stat=lib.GetTemperature(ctypes.byref(temp))
		return temp.value,stat
	setup_func(lib.GetTemperatureF ,[ctypes.POINTER(ctypes.c_float)], passing={20034,20035,20036,20037,20040})
	def GetTemperatureF():
		temp=ctypes.c_float()
		stat=lib.GetTemperatureF(ctypes.byref(temp))
		return temp.value,stat
	SetTemperature=ctf_simple(lib.SetTemperature, [ctypes.c_int32], ["temperature"])
	GetTemperatureRange=ctf_rvals(lib.GetTemperatureRange, [ctypes.c_int32,ctypes.c_int32], [None,None], [])
	CoolerON=ctf_simple(lib.CoolerON, [], [])
	CoolerOFF=ctf_simple(lib.CoolerOFF, [], [])
	IsCoolerOn=ctf_rval(lib.IsCoolerOn, ctypes.c_int32, [None], [])

	GetNumberADChannels=ctf_rval(lib.GetNumberADChannels, ctypes.c_int32, [None], [])
	SetADChannel=ctf_simple(lib.SetADChannel, [ctypes.c_int32], ["channel"])
	GetBitDepth=ctf_rval(lib.GetBitDepth, ctypes.c_int32, [ctypes.c_int32,None], ["channel"])
	GetNumberAmp=ctf_rval(lib.GetNumberAmp, ctypes.c_int32, [None], [])
	SetOutputAmplifier=ctf_simple(lib.SetOutputAmplifier, [ctypes.c_int32], ["typ"])
	IsAmplifierAvailable=ctf_simple(lib.IsAmplifierAvailable, [ctypes.c_int32], ["amp"])
	GetNumberPreAmpGains=ctf_rval(lib.GetNumberPreAmpGains, ctypes.c_int32, [None], [])
	GetPreAmpGain=ctf_rval(lib.GetPreAmpGain, ctypes.c_float, [ctypes.c_int32,None], ["index"])
	SetPreAmpGain=ctf_simple(lib.SetPreAmpGain, [ctypes.c_int32], ["index"])
	IsPreAmpGainAvailable=ctf_rval(lib.IsPreAmpGainAvailable, ctypes.c_int32, [ctypes.c_int32,ctypes.c_int32,ctypes.c_int32,ctypes.c_int32,None], ["channel","amplifier","index","preamp"])

	GetNumberHSSpeeds=ctf_rval(lib.GetNumberHSSpeeds, ctypes.c_int32, [ctypes.c_int32,ctypes.c_int32,None], ["channel","typ"])
	GetHSSpeed=ctf_rval(lib.GetHSSpeed, ctypes.c_float, [ctypes.c_int32,ctypes.c_int32,ctypes.c_int32,None], ["channel","typ","index"])
	SetHSSpeed=ctf_simple(lib.SetHSSpeed, [ctypes.c_int32,ctypes.c_int32], ["typ","index"])
	GetNumberVSSpeeds=ctf_rval(lib.GetNumberVSSpeeds, ctypes.c_int32, [None], [])
	GetVSSpeed=ctf_rval(lib.GetVSSpeed, ctypes.c_float, [ctypes.c_int32,None], ["index"])
	SetVSSpeed=ctf_simple(lib.SetVSSpeed, [ctypes.c_int32], ["index"])
	GetFastestRecommendedVSSpeed=ctf_rvals(lib.GetFastestRecommendedVSSpeed, [ctypes.c_int32,ctypes.c_float], [None,None], [])
	GetVSAmplitudeValue=ctf_rval(lib.GetVSAmplitudeValue, ctypes.c_int32, [ctypes.c_int32,None], ["index"])
	SetVSAmplitude=ctf_simple(lib.SetVSAmplitude, [ctypes.c_int32], ["state"])

	GetGateMode=ctf_rval(lib.GetGateMode, ctypes.c_int32, [None], [])
	SetGateMode=ctf_simple(lib.SetGateMode, [ctypes.c_int32], ["mode"])
	SetEMGainMode=ctf_simple(lib.SetEMGainMode, [ctypes.c_int32], ["mode"])
	GetEMGainRange=ctf_rvals(lib.GetEMGainRange, [ctypes.c_int32,ctypes.c_int32], [None,None], [])
	GetEMCCDGain=ctf_rval(lib.GetEMCCDGain, ctypes.c_int32, [None], [])
	SetEMCCDGain=ctf_simple(lib.SetEMCCDGain, [ctypes.c_int32], ["gain"])
	GetEMAdvanced=ctf_rval(lib.GetEMAdvanced, ctypes.c_int32, [None], [])
	SetEMAdvanced=ctf_simple(lib.SetEMAdvanced, [ctypes.c_int32], ["state"])
	# SetMCPGating=ctf_simple(lib.SetMCPGating, [ctypes.c_int32], ["mode"])
	# GetMCPGainRange=ctf_rvals(lib.GetMCPGainRange, [ctypes.c_int32,ctypes.c_int32], [None,None], [])
	# SetMCPGain=ctf_simple(lib.SetMCPGain, [ctypes.c_int32], ["gain"])

	GetShutterMinTimes=ctf_rvals(lib.GetShutterMinTimes, [ctypes.c_int32,ctypes.c_int32], [None,None], [])
	SetShutter=ctf_simple(lib.SetShutter, [ctypes.c_int32,ctypes.c_int32,ctypes.c_int32,ctypes.c_int32], ["typ","mode","closing_time","opening_time"])
	SetShutterEx=ctf_simple(lib.SetShutterEx, [ctypes.c_int32,ctypes.c_int32,ctypes.c_int32,ctypes.c_int32,ctypes.c_int32], ["typ","mode","closing_time","opening_time","extmode"])

	SetAcquisitionMode=ctf_simple(lib.SetAcquisitionMode, [ctypes.c_uint32], ["mode"])
	GetAcquisitionTimings=ctf_rvals(lib.GetAcquisitionTimings, [ctypes.c_float,ctypes.c_float,ctypes.c_float], [None,None,None], [])
	SetExposureTime=ctf_simple(lib.SetExposureTime, [ctypes.c_float], ["time"])
	SetNumberAccumulations=ctf_simple(lib.SetNumberAccumulations, [ctypes.c_int32], ["number"])
	SetNumberKinetics=ctf_simple(lib.SetNumberKinetics, [ctypes.c_int32], ["number"])
	SetNumberPrescans=ctf_simple(lib.SetNumberPrescans, [ctypes.c_int32], ["number"])
	SetKineticCycleTime=ctf_simple(lib.SetKineticCycleTime, [ctypes.c_float], ["time"])
	SetAccumulationCycleTime=ctf_simple(lib.SetAccumulationCycleTime, [ctypes.c_float], ["time"])
	SetFrameTransferMode=ctf_simple(lib.SetFrameTransferMode, [ctypes.c_uint32], ["mode"])
	GetReadOutTime=ctf_rval(lib.GetReadOutTime, ctypes.c_float, [None], [])
	GetKeepCleanTime=ctf_rval(lib.GetKeepCleanTime, ctypes.c_float, [None], [])

	PrepareAcquisition=ctf_simple(lib.PrepareAcquisition, [], [])
	StartAcquisition=ctf_simple(lib.StartAcquisition, [], [])
	AbortAcquisition=ctf_simple(lib.AbortAcquisition, [], [])
	GetAcquisitionProgress=ctf_rvals(lib.GetAcquisitionProgress, [ctypes.c_int32,ctypes.c_int32], [None,None], [])
	GetStatus=ctf_rval(lib.GetStatus, ctypes.c_int32, [None], [])
	WaitForAcquisition=ctf_simple(lib.WaitForAcquisition, [], [])
	WaitForAcquisitionTimeOut=ctf_simple(lib.WaitForAcquisitionTimeOut, [ctypes.c_int32], ["timeout_ms"], passing={20024}) # finish quietly on timeout
	WaitForAcquisitionByHandle=ctf_simple(lib.WaitForAcquisitionByHandle, [ctypes.c_int32], ["handle"])
	WaitForAcquisitionByHandleTimeOut=ctf_simple(lib.WaitForAcquisitionByHandleTimeOut, [ctypes.c_int32,ctypes.c_int32], ["handle","timeout_ms"], passing={20024}) # finish quietly on timeout
	CancelWait=ctf_simple(lib.CancelWait, [], [])

	SetReadMode=ctf_simple(lib.SetReadMode, [ctypes.c_uint32], ["mode"])
	GetMaximumBinning=ctf_rval(lib.GetMaximumBinning, ctypes.c_int32, [ctypes.c_int32,ctypes.c_int32,None], ["read_mode","horiz_vert"])
	GetMinimumImageLength=ctf_rval(lib.GetMinimumImageLength, ctypes.c_int32, [None], [])
	SetSingleTrack=ctf_simple(lib.SetSingleTrack, [ctypes.c_int32,ctypes.c_int32], ["center","height"])
	SetMultiTrack=ctf_rvals(lib.SetMultiTrack, [ctypes.c_int32,ctypes.c_int32], [ctypes.c_int32,ctypes.c_int32,ctypes.c_int32,None,None], ["number","height","offset"])
	setup_func(lib.SetRandomTracks ,[ctypes.c_int32,ctypes.POINTER(ctypes.c_int32)])
	def SetRandomTracks(tracks):
		ntracks=len(tracks)
		areas=(ctypes.c_int32*(ntracks*2))(*[b for t in tracks for b in t])
		lib.SetRandomTracks(ntracks,areas)
	SetImage=ctf_simple(lib.SetImage, [ctypes.c_int32,ctypes.c_int32,ctypes.c_int32,ctypes.c_int32,ctypes.c_int32,ctypes.c_int32], ["hbin","vbin","hstart","hend","vstart","vend"])
	GetDetector=ctf_rvals(lib.GetDetector, [ctypes.c_int32,ctypes.c_int32], [None,None], [])
	GetSizeOfCircularBuffer=ctf_rval(lib.GetSizeOfCircularBuffer, ctypes.c_int32, [None], [])

	def buffer32_prep(size):
		return ctypes.create_string_buffer(size*4)
	def buffer16_prep(size):
		return ctypes.create_string_buffer(size*2)
	def buffer32_conv(buff, size):
		return np.fromstring(ctypes.string_at(buff,size*4),dtype="<u4")
	def buffer16_conv(buff, size):
		return np.fromstring(ctypes.string_at(buff,size*2),dtype="<u2")
	GetOldestImage  =ctf_buff(lib.GetOldestImage  , [None,ctypes.c_uint32], ["size"], build_buff=buffer32_prep, conv_buff=buffer32_conv)
	GetOldestImage16=ctf_buff(lib.GetOldestImage16, [None,ctypes.c_uint32], ["size"], build_buff=buffer16_prep, conv_buff=buffer16_conv)
	GetMostRecentImage  =ctf_buff(lib.GetMostRecentImage  , [None,ctypes.c_uint32], ["size"], build_buff=buffer32_prep, conv_buff=buffer32_conv)
	GetMostRecentImage16=ctf_buff(lib.GetMostRecentImage16, [None,ctypes.c_uint32], ["size"], build_buff=buffer16_prep, conv_buff=buffer16_conv)
	GetNumberNewImages=ctf_rvals(lib.GetNumberNewImages, [ctypes.c_int32,ctypes.c_int32], [None,None], [])
	setup_func(lib.GetImages  ,[ctypes.c_int32,ctypes.c_int32,ctypes.c_char_p,ctypes.c_int32,ctypes.POINTER(ctypes.c_int32),ctypes.POINTER(ctypes.c_int32)])
	setup_func(lib.GetImages16,[ctypes.c_int32,ctypes.c_int32,ctypes.c_char_p,ctypes.c_int32,ctypes.POINTER(ctypes.c_int32),ctypes.POINTER(ctypes.c_int32)])
	def GetImages(first, last, size):
		buffsize=max(last-first+1,1)*size
		buff=buffer32_prep(buffsize)
		vfirst=ctypes.c_int32()
		vlast=ctypes.c_int32()
		lib.GetImages(first,last,buff,size,ctypes.byref(vfirst),ctypes.byref(vlast))
		return buffer32_conv(buff,buffsize),vfirst.value,vlast.value
	def GetImages16(first, last, size):
		buffsize=max(last-first+1,1)*size
		buff=buffer16_prep(buffsize)
		vfirst=ctypes.c_int32()
		vlast=ctypes.c_int32()
		lib.GetImages16(first,last,buff,buffsize,ctypes.byref(vfirst),ctypes.byref(vlast))
		return buffer16_conv(buff,buffsize),vfirst.value,vlast.value






	AmpModeSimple=collections.namedtuple("AmpModeSimple",["channel","oamp","hsspeed","preamp"])
	AmpModeFull=collections.namedtuple("AmpModeFull",["channel","channel_bitdepth","oamp","oamp_kind","hsspeed","hsspeed_MHz","preamp","preamp_gain"])
	_oamp_kinds=["EMCCD/Conventional","CCD/ExtendedNIR"]
	def get_all_amp_modes():
		channels=GetNumberADChannels()
		oamps=GetNumberAmp()
		preamps=GetNumberPreAmpGains()
		modes=[]
		for ch in range(channels):
			bit_depth=GetBitDepth(ch)
			for oamp in range(oamps):
				hsspeeds=GetNumberHSSpeeds(ch,oamp)
				for hssp in range(hsspeeds):
					hsspeed_hz=GetHSSpeed(ch,oamp,hssp)
					for pa in range(preamps):
						preamp_gain=GetPreAmpGain(pa)
						try:
							IsPreAmpGainAvailable(ch,oamp,hssp,pa)
							modes.append(AmpModeFull(ch,bit_depth,oamp,_oamp_kinds[oamp],hssp,hsspeed_hz,pa,preamp_gain))
						except AndorLibError:
							pass
		return modes

	def set_amp_mode(amp_mode):
		if len(amp_mode)==4:
			amp_mode=AmpModeSimple(*amp_mode)
		else:
			amp_mode=AmpModeFull(*amp_mode)
		SetADChannel(amp_mode.channel)
		SetOutputAmplifier(amp_mode.oamp)
		SetHSSpeed(amp_mode.oamp,amp_mode.hsspeed)
		SetPreAmpGain(amp_mode.preamp)

	def get_EMCCD_gain():
		advanced=GetEMAdvanced()
		gain=GetEMCCDGain()
		return advanced, gain
	def set_EMCCD_gain(gain, advanced=False):
		SetEMAdvanced(advanced)
		SetEMCCDGain(gain)



except OSError:
	pass