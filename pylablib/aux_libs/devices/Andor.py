from .Andor_lib import lib, AndorLibError

from ...core.devio.interface import IDevice
from ...core.utils import funcargparse, py3

_depends_local=[".Andor_lib","...core.devio.interface"]

import numpy as np
import collections
import contextlib

class AndorError(RuntimeError):
    "Generic Andor camera error."
class AndorTimeoutError(AndorError):
    "Timeout while waiting."
class AndorNotSupportedError(AndorError):
    "Option not supported."

def get_cameras_number():
    """Get number of connected Andor cameras"""
    lib.initlib()
    return lib.GetAvailableCameras()

class AndorCamera(IDevice):
    """
    Andor camera.

    Caution: the manufacturer DLL is designed such that if the camera is not closed on the program termination, the allocated resources are never released.
    If this happens, these resources are blocked until the complete OS restart.

    Args:
        idx(int): camera index (use :func:`get_cameras_number` to get the total number of connected cameras)
        ini_path(str): path to .ini file, if required by the camera
    """
    def __init__(self, idx=0, ini_path=""):
        IDevice.__init__(self)
        lib.initlib()
        self.idx=idx
        self.ini_path=ini_path
        self.handle=None
        self.open()
        
        self._nodes_ignore_error={"get":(AndorNotSupportedError,),"set":(AndorNotSupportedError,)}
        self._add_full_info_node("model_data",self.get_model_data)
        self._add_full_info_node("capabilities",self.get_capabilities)
        self._add_full_info_node("amp_modes",self.get_all_amp_modes,ignore_error=AndorLibError)
        self._add_settings_node("temperature",lambda: self.temperature_setpoint,self.set_temperature)
        self._add_status_node("temperature_monitor",self.get_temperature,ignore_error=AndorLibError)
        self._add_status_node("temperature_status",self.get_temperature_status,ignore_error=AndorLibError)
        self._add_settings_node("cooler",self.is_cooler_on,self.set_cooler,ignore_error=AndorLibError)
        self._add_settings_node("channel",lambda:self.channel,lambda x:self.set_amp_mode(channel=x))
        self._add_settings_node("oamp",lambda:self.oamp,lambda x:self.set_amp_mode(oamp=x))
        self._add_settings_node("hsspeed",lambda:self.hsspeed,lambda x:self.set_amp_mode(hsspeed=x))
        self._add_settings_node("preamp",lambda:self.preamp,lambda x:self.set_amp_mode(preamp=x),ignore_error=AndorLibError)
        self._add_settings_node("vsspeed",lambda:self.vsspeed,self.set_vsspeed)
        self._add_settings_node("EMCCD_gain",lambda:self.EMCCD_gain,self.set_EMCCD_gain)
        self._add_settings_node("shutter",lambda:self.shutter_mode,self.set_shutter)
        self._add_settings_node("fan_mode",lambda:self.fan_mode,self.set_fan_mode)
        self._add_settings_node("trigger_mode",lambda:self.trigger_mode,self.set_trigger_mode)
        self._add_settings_node("acq_parameters/accum",lambda:self.acq_params["accum"],self.setup_accum_mode)
        self._add_settings_node("acq_parameters/kinetics",lambda:self.acq_params["kinetics"],self.setup_kinetic_mode)
        self._add_settings_node("acq_parameters/fast_kinetics",lambda:self.acq_params["fast_kinetics"],self.setup_fast_kinetic_mode)
        self._add_settings_node("acq_parameters/cont",lambda:self.acq_params["cont"],self.setup_cont_mode)
        self._add_settings_node("acq_mode",lambda:self.acq_mode,self.set_acquisition_mode)
        self._add_status_node("acq_status",self.get_status)
        self._add_settings_node("frame_transfer",lambda:self.frame_transfer_mode,self.enable_frame_transfer_mode)
        self._add_settings_node("exposure",self.get_exposure,self.set_exposure)
        self._add_status_node("timings",self.get_timings)
        self._add_status_node("readout_time",self.get_readout_time)
        self._add_settings_node("read_parameters/single_track",lambda:self.read_params["single_track"],self.setup_single_track_mode)
        self._add_settings_node("read_parameters/multi_track",lambda:self.read_params["multi_track"],self.setup_multi_track_mode)
        self._add_settings_node("read_parameters/random_track",lambda:self.read_params["random_track"],self.setup_random_track_mode)
        self._add_settings_node("read_parameters/image",lambda:self.read_params["image"],self.setup_image_mode)
        self._add_settings_node("read_mode",lambda:self.read_mode,self.set_read_mode)
        self._add_status_node("data_dimensions",self.get_data_dimensions)
        self._add_status_node("ring_buffer_size",self.get_ring_buffer_size,ignore_error=AndorLibError)
        self._add_full_info_node("detector_size",self.get_detector_size)

    def _setup_default_settings(self):
        self.capabilities=self.get_capabilities()
        self.model_data=self.get_model_data()
        try:
            self._strict_option_check=False
            self.temperature_setpoint=None
            self.set_temperature(-100)
            self.channel=None
            self.oamp=None
            self.hsspeed=None
            self.preamp=None
            self.vsspeed=None
            self.init_speeds()
            self.EMCCD_gain=None
            self.set_EMCCD_gain(0)
            self.set_EMCCD_gain(0,False)
            self.fan_mode=None
            self.set_fan_mode("off")
            self.shutter_mode=None
            self.set_shutter("close")
            self.trigger_mode=None
            self.set_trigger_mode("int")
            self.set_exposure(10E-3)
            self.acq_mode=None
            self.set_acquisition_mode("cont")
            self.acq_params=dict(zip(self._acq_modes,[()]*len(self._acq_modes)))
            self.setup_accum_mode(1)
            self.setup_kinetic_mode(1)
            self.setup_fast_kinetic_mode(1)
            self.setup_cont_mode()
            self.frame_transfer_mode=None
            self.enable_frame_transfer_mode(False)
            self.read_mode=None
            self.set_read_mode("image")
            self.read_params=dict(zip(self._read_modes,[()]*len(self._read_modes)))
            self.setup_image_mode()
            self.setup_single_track_mode()
            self.setup_multi_track_mode()
            self.setup_random_track_mode()
            self.flush_buffer()
        finally:
            self._strict_option_check=True

    def _camsel(self):
        if self.handle is None:
            raise AndorError("camera is not opened")
        if lib.GetCurrentCamera()!=self.handle:
            lib.SetCurrentCamera(self.handle)
    def _has_option(self, kind, option):
        if kind=="acq":
            opt=self.capabilities.AcqModes
        elif kind=="read":
            opt=self.capabilities.ReadModes
        elif kind=="trig":
            opt=self.capabilities.TriggerModes
        elif kind=="set":
            opt=self.capabilities.SetFunctions
        elif kind=="get":
            opt=self.capabilities.GetFunctions
        elif kind=="feat":
            opt=self.capabilities.Features
        else:
            raise AndorError("unknown option kind: {}".format(kind))
        return option in opt
    def _check_option(self, kind, option):
        has_option=self._has_option(kind,option)
        if (not has_option) and self._strict_option_check:
            raise AndorNotSupportedError("option {}.{} is not supported by {}".format(kind,option,self.model_data.head_model))
        return has_option
    def open(self):
        """Open connection to the camera"""
        ncams=get_cameras_number()
        if self.idx>=ncams:
            raise AndorError("camera index {} is not available ({} cameras exist)".format(self.idx,ncams))
        self.handle=lib.GetCameraHandle(self.idx)
        self._camsel()
        lib.Initialize(py3.as_builtin_bytes(self.ini_path))
        self._setup_default_settings()
    def close(self):
        """Close connection to the camera"""
        try:
            self._camsel()
        except AndorError:
            return
        try:
            lib.ShutDown()
        except AndorLibError as e:
            if e.text_code!="DRV_NOT_INITIALIZED":
                raise
        self.handle=None
    def is_opened(self):
        """Check if the device is connected"""
        return self.handle is not None

    ModelData=collections.namedtuple("ModelData",["controller_model","head_model","serial_number"])
    def get_model_data(self):
        """
        Get camera model data.

        Return tuple ``(controller_mode, head_model, serial_number)``.
        """
        self._camsel()
        control_model=py3.as_str(lib.GetControllerCardModel())
        head_model=py3.as_str(lib.GetHeadModel())
        serial_number=lib.GetCameraSerialNumber()
        return self.ModelData(control_model,head_model,serial_number)
        

    ### Generic controls ###
    def get_status(self):
        """
        Get camera status.

        Return either ``"idle"`` (no acquisition), ``"acquiring"`` (acquisition in progress) or ``"temp_cycle"`` (temperature cycle in progress).
        """
        self._camsel()
        if not self._check_option("feat","AC_FEATURES_POLLING"): return
        status=lib.GetStatus()
        text_status=lib.Andor_statuscodes[status]
        if text_status=="DRV_IDLE":
            return "idle"
        if text_status=="DRV_TEMPCYCLE":
            return "temp_cycle"
        if text_status=="DRV_ACQUIRING":
            return "acquiring"
        raise AndorLibError("GetStatus",status)
    def get_capabilities(self):
        """
        Get camera capabilities.

        For description of the structure, see Andor SDK manual.
        """
        self._camsel()
        return lib.GetCapabilities()

    ### Cooler controls ###
    def is_cooler_on(self):
        """Check if the cooler is on"""
        self._camsel()
        if not self._check_option("set","AC_SETFUNCTION_TEMPERATURE"): return
        return bool(lib.IsCoolerOn())
    def set_cooler(self, on=True):
        """Set the cooler on or off"""
        self._camsel()
        if not self._check_option("get","AC_GETFUNCTION_TEMPERATURE"): return
        if on:
            lib.CoolerON()
        else:
            lib.CoolerOFF()
    _temp_status={"DRV_TEMPERATURE_OFF":"off","DRV_TEMPERATURE_NOT_REACHED":"not_reached","DRV_TEMPERATURE_NOT_STABILIZED":"not_stabilized",
                    "DRV_TEMPERATURE_DRIFT":"drifted","DRV_TEMPERATURE_STABILIZED":"stabilized",}
    def get_temperature_status(self):
        """
        Get temperature status.

        Can return ``"off"`` (cooler off), ``"not_reached"`` (cooling in progress), ``"not_stabilized"`` (reached but not stabilized yet),
        ``"stabilized"`` (completely stabilized) or ``"drifted"``.
        """
        self._camsel()
        if not self._check_option("get","AC_GETFUNCTION_TEMPERATURE"): return
        status=lib.GetTemperature()[1]
        return self._temp_status[status]
    def get_temperature(self):
        """Get the current camera temperature"""
        self._camsel()
        if not self._check_option("get","AC_GETFUNCTION_TEMPERATURE"): return
        return lib.GetTemperatureF()[0]
    def set_temperature(self, temperature, enable_cooler=True):
        """
        Change the temperature setpoint.

        If ``enable_cooler==True``, turn the cooler on automatically.
        """
        self._camsel()
        if not self._check_option("set","AC_SETFUNCTION_TEMPERATURE"): return
        if not self._check_option("get","AC_GETFUNCTION_TEMPERATURERANGE"): return
        rng=lib.GetTemperatureRange()
        temperature=max(temperature,rng[0])
        temperature=min(temperature,rng[1])
        self.temperature_setpoint=int(temperature)
        lib.SetTemperature(self.temperature_setpoint)
        if enable_cooler:
            self.set_cooler(True)
    
    ### Amplifiers/shift speeds controls ###
    def get_all_amp_modes(self):
        """
        Get all available pream modes.

        Each preamp mode is characterized by an AD channel index, amplifier index, channel speed (horizontal scan speed) index and preamp gain index.
        Return list of tuples ``(channel, channel_bitdepth, oamp, oamp_kind, hsspeed, hsspeed_MHz, preamp, preamp_gain)``,
        where ``channel``, ``oamp``, ``hsspeed`` and ``preamp`` are indices, while ``channel_bitdepth``, ``oamp_kind``, ``hsspeed_MHz`` and ``preamp_gain`` are descriptions.
        """
        self._camsel()
        return lib.get_all_amp_modes()
    def get_max_vsspeed(self):
        """Get  maximal recommended vertical scan speed"""
        self._camsel()
        return lib.GetFastestRecommendedVSSpeed()[0]
    def set_amp_mode(self, channel=None, oamp=None, hsspeed=None, preamp=None):
        """
        Setup preamp mode.

        Can specify AD channel index, amplifier index, channel speed (horizontal scan speed) index and preamp gain index.
        ``None`` (default) means leaving the current value.
        """
        self._camsel()
        channel=self.channel if channel is None else channel
        oamp=self.oamp if oamp is None else oamp
        hsspeed=self.hsspeed if hsspeed is None else hsspeed
        preamp=self.preamp if preamp is None else preamp
        if not self._has_option("set","AC_SETFUNCTION_PREAMPGAIN"):
            preamp=None
        if not self._has_option("set","AC_SETFUNCTION_HREADOUT"):
            hsspeed=None
        lib.set_amp_mode((channel,oamp,hsspeed,preamp))
        self.channel=channel
        self.oamp=oamp
        self.hsspeed=hsspeed
        self.preamp=preamp
    def set_vsspeed(self, vsspeed):
        """Set vertical scan speed index"""
        self._camsel()
        if not self._check_option("set","AC_SETFUNCTION_VREADOUT"): return
        lib.SetVSSpeed(vsspeed)
        self.vsspeed=vsspeed

    def get_channel_bitdepth(self, channel=None):
        """Get channel bit depth corresponding to the given channel index (current by default)"""
        self._camsel()
        return lib.GetBitDepth(self.channel if channel is None else channel)
    def get_oamp_desc(self, oamp=None):
        """Get output amplifier kind corresponding to the given oamp index (current by default)"""
        return lib._oamp_kinds[self.oamp if oamp is None else oamp]
    def get_hsspeed_frequency(self, hsspeed=None):
        """Get horizontal scan frequency (in Hz) corresponding to the given hsspeed index (current by default)"""
        self._camsel()
        return lib.GetHSSpeed(self.channel,self.oamp,self.hsspeed if hsspeed is None else hsspeed)*1E6
    def get_preamp_gain(self, preamp=None):
        """Get preamp gain corresponding to the given preamp index (current by default)"""
        self._camsel()
        return lib.GetPreAmpGain(self.preamp if preamp is None else preamp)
    def get_vsspeed_period(self, vsspeed=None):
        """Get vertical scan period corresponding to the given vsspeed index (current by default)"""
        self._camsel()
        return lib.GetVSSpeed(self.vsspeed if vsspeed is None else vsspeed)

    def get_EMCCD_gain(self):
        """
        Get current EMCCD gain.

        Return tuple ``(gain, advanced)``.
        """
        self._camsel()
        if not self._check_option("get","AC_GETFUNCTION_EMCCDGAIN"): return
        return lib.get_EMCCD_gain()
    def set_EMCCD_gain(self, gain, advanced=None):
        """
        Set EMCCD gain.

        Gain goes up to 300 if ``advanced==False`` or higher if ``advanced==True`` (in this mode the sensor can be permanently damaged by strong light).
        """
        self._camsel()
        gain=int(gain)
        if not self._check_option("set","AC_SETFUNCTION_EMCCDGAIN"): return
        if (advanced is not None) and not self._check_option("set","AC_SETFUNCTION_EMADVANCED"): return
        lib.set_EMCCD_gain(gain,advanced)
        self.EMCCD_gain=(gain,advanced)

    def init_speeds(self):
        """Initialize the camera channel, frequencies and amp settings to some default mode"""
        mode=self.get_all_amp_modes()[0]
        self.set_amp_mode(mode.channel,mode.oamp,mode.hsspeed,mode.preamp)
        vsspeed=self.get_max_vsspeed()
        self.set_vsspeed(vsspeed)
        self.set_EMCCD_gain(0,advanced=False)

    ### Shutter controls ###
    def get_min_shutter_times(self):
        """Get minimal shutter opening and closing times"""
        self._camsel()
        if not self._check_option("feat","AC_FEATURES_SHUTTER"): return
        return lib.GetShutterMinTimes()
    def set_shutter(self, mode, ttl_mode=0, open_time=None, close_time=None):
        """
        Setup shutter.

        `mode` can be ``"auto"``, ``"open"`` or ``"close"``, ttl_mode can be 0 (low is open) or 1 (high is open),
        `open_time` and `close_time` specify opening and closing times (required to calculate the minimal exposure times).
        By default, these time are minimal allowed times.
        """
        self._camsel()
        if not self._check_option("feat","AC_FEATURES_SHUTTER"): return
        if mode in [0,False]:
            mode="close"
        if mode in [1,True]:
            mode="open"
        shutter_modes=["auto","open","close"]
        funcargparse.check_parameter_range(mode,"state",shutter_modes)
        min_open_time,min_close_time=self.get_min_shutter_times()
        open_time=min_open_time if open_time is None else open_time
        close_time=min_close_time if close_time is None else close_time
        lib.SetShutter(ttl_mode,shutter_modes.index(mode),open_time,close_time)
        self.shutter_mode=mode

    ### Misc controls ###
    def set_fan_mode(self, mode):
        """
        Set fan mode.

        Can be ``"full"``, ``"low"`` or ``"off"``.
        """
        self._camsel()
        if not self._check_option("feat","AC_FEATURES_FANCONTROL"): return
        text_modes=["full","low","off"]
        funcargparse.check_parameter_range(mode,"mode",text_modes)
        lib.SetFanMode(text_modes.index(mode))
        self.fan_mode=mode

    def read_in_aux_port(self, port):
        """Get state at a given auxiliary port"""
        self._camsel()
        return lib.InAuxPort(port)
    def set_out_aux_port(self, port, state):
        """Set state at a given auxiliary port"""
        self._camsel()
        return lib.OutAuxPort(port,state)

    ### Trigger controls ###
    def set_trigger_mode(self, mode):
        """
        Set trigger mode.

        Can be ``"int"`` (internal), ``"ext"`` (external), ``"ext_start"`` (external start), ``"ext_exp"`` (external exposure),
        ``"ext_fvb_em"`` (external FVB EM), ``"software"`` (software trigger) or ``"ext_charge_shift"`` (external charge shifting).

        For description, see Andor SDK manual.
        """
        trigger_modes={"int":0,"ext":1,"ext_start":6,"ext_exp":7,"ext_fvb_em":9,"software":10,"ext_charge_shift":12}
        trigger_modes_cap={"int":"AC_TRIGGERMODE_INTERNAL","ext":"AC_TRIGGERMODE_EXTERNAL",
            "ext_start":"AC_TRIGGERMODE_EXTERNALSTART","ext_exp":"AC_TRIGGERMODE_EXTERNALEXPOSURE",
            "ext_fvb_em":"AC_TRIGGERMODE_EXTERNAL_FVB_EM","software":"AC_TRIGGERMODE_INTERNAL"}
        funcargparse.check_parameter_range(mode,"mode",trigger_modes.keys())
        self._camsel()
        if not self._check_option("trig",trigger_modes_cap[mode]): return
        lib.SetTriggerMode(trigger_modes[mode])
        self.trigger_mode=mode
    def get_trigger_level_limits(self):
        """Get limits on the trigger level"""
        self._camsel()
        return lib.GetTriggerLevelRange()
    def setup_ext_trigger(self, level, invert, term_highZ=True):
        """Setup external trigger (level, inversion, and high-Z termination)"""
        self._camsel()
        lib.SetTriggerLevel(level)
        lib.SetTriggerInvert(invert)
        lib.SetExternalTriggerTermination(term_highZ)
    def send_software_trigger(self):
        """Send software trigger signal"""
        self._camsel()
        lib.SendSoftwareTrigger()

    ### Acquisition mode controls ###
    _acq_modes={"single":1,"accum":2,"kinetics":3,"fast_kinetics":4,"cont":5}
    _acq_modes_cap={"single":"AC_ACQMODE_SINGLE", "accum":"AC_ACQMODE_ACCUMULATE",
        "kinetics":"AC_ACQMODE_KINETIC", "fast_kinetics":"AC_ACQMODE_FASTKINETICS",
        "cont":"AC_ACQMODE_VIDEO"}
    def set_acquisition_mode(self, mode):
        """
        Set acquisition mode.

        Can be ``"single"``, ``"accum"``, ``"kinetics"``, ``"fast_kinetics"`` or ``"cont"`` (continuous).
        For description of each mode, see Andor SDK manual and corresponding setup_*_mode functions.
        """
        funcargparse.check_parameter_range(mode,"mode",self._acq_modes.keys())
        self._camsel()
        if not self._check_option("acq",self._acq_modes_cap[mode]): return
        lib.SetAcquisitionMode(self._acq_modes[mode])
        self.acq_mode=mode
    def setup_accum_mode(self, num, cycle_time=0):
        """
        Setup accum acquisition mode.
        
        `num` is the number of accumulated frames, `cycle_time` is the acquisition period
        (by default the minimal possible based on exposure and transfer time).
        """
        self._camsel()
        if not self._check_option("acq","AC_ACQMODE_ACCUMULATE"): return
        self.set_acquisition_mode("accum")
        lib.SetNumberAccumulations(num)
        lib.SetAccumulationCycleTime(cycle_time)
        self.acq_params["accum"]=(num,cycle_time)
    def setup_kinetic_mode(self, num, cycle_time=0., num_acc=1, cycle_time_acc=0, num_prescan=0):
        """
        Setup kinetic acquisition mode.
        
        `num` is the number of kinetic cycles frames, `cycle_time` is the acquisition period between accum frames,
        `num_accum` is the number of accumulated frames, `cycle_time_acc` is the accum acquisition period,
        `num_prescan` is the number of prescans.
        """
        self._camsel()
        if not self._check_option("acq","AC_ACQMODE_KINETIC"): return
        self.set_acquisition_mode("kinetics")
        lib.SetNumberKinetics(num)
        lib.SetNumberAccumulations(num_acc)
        lib.SetNumberPrescans(num_prescan)
        lib.SetKineticCycleTime(cycle_time)
        lib.SetAccumulationCycleTime(cycle_time_acc)
        self.acq_params["kinetics"]=(num,cycle_time,num_acc,cycle_time_acc,num_prescan)
    def setup_fast_kinetic_mode(self, num, cycle_time_acc=0.):
        """
        Setup fast kinetic acquisition mode.
        
        `num` is the number of accumulated frames, `cycle_time` is the acquisition period
        (by default the minimal possible based on exposure and transfer time).
        """
        self._camsel()
        if not self._check_option("acq","AC_ACQMODE_FASTKINETICS"): return
        self.set_acquisition_mode("fast_kinetics")
        lib.SetNumberKinetics(num)
        lib.SetAccumulationCycleTime(cycle_time_acc)
        self.acq_params["fast_kinetics"]=(num,cycle_time_acc)
    def setup_cont_mode(self, cycle_time=0):
        """
        Setup continuous acquisition mode.
        
        `cycle_time` is the acquisition period (by default the minimal possible based on exposure and transfer time).
        """
        self._camsel()
        if not self._check_option("acq","AC_ACQMODE_VIDEO"): return
        self.set_acquisition_mode("cont")
        lib.SetKineticCycleTime(cycle_time)
        self.acq_params["cont"]=cycle_time
    def _setup_acqusition(self, acq_mode=None, params=None):
        acq_mode=acq_mode or self.acq_mode
        params=params or self.acq_params[self.acq_mode]
        if acq_mode=="accum":
            self.setup_accum_mode(*params)
        elif acq_mode=="kinetics":
            self.setup_kinetic_mode(*params)
        elif acq_mode=="fast_kinetics":
            self.setup_fast_kinetic_mode(*params)
        elif acq_mode=="cont":
            self.setup_cont_mode(params)
    def set_exposure(self, exposure):
        """Set camera exposure"""
        self._camsel()
        lib.SetExposureTime(exposure)
    def get_exposure(self):
        """Get current exposure"""
        return self.get_timings()[0]
    def enable_frame_transfer_mode(self, enable=True):
        """
        Enable frame transfer mode.

        For description, see Andor SDK manual.
        """
        self._camsel()
        if not self._check_option("acq","AC_ACQMODE_FRAMETRANSFER"): return
        lib.SetFrameTransferMode(enable)
        self.frame_transfer_mode=enable
    AcqTimes=collections.namedtuple("AcqTimes",["exposure","accum_cycle_time","kinetic_cycle_time"])
    def get_timings(self):
        """
        Get acquisition timing.

        Return tuple ``(exposure, accum_cycle_time, kinetic_cycle_time)``.
        In continuous mode, the relevant cycle time is ``kinetic_cycle_time``.
        """
        self._camsel()
        return self.AcqTimes(*lib.GetAcquisitionTimings())
    def get_readout_time(self):
        """Get frame readout time"""
        self._camsel()
        return lib.GetReadOutTime()
    def get_keepclean_time(self):
        """Get sensor keep-clean time"""
        self._camsel()
        return lib.GetKeepCleanTime()

    ### Acquisition process controls ###
    def prepare_acquisition(self):
        """
        Prepare acquisition.
        
        Isn't required (called automatically on acquisition start), but decreases time required for starting acquisition later.
        """
        self._camsel()
        lib.PrepareAcquisition()
    def start_acquisition(self, setup=True):
        """
        Start acquisition.

        If ``setup==True``, setup the acquisition parameters before the start
        (they don't apply automatically when the mode is changed).
        """
        self._camsel()
        if setup:
            self._setup_acqusition()
        lib.StartAcquisition()
    def stop_acquisition(self):
        """Stop acquisition"""
        self._camsel()
        if self.get_status()=="acquiring":
            lib.AbortAcquisition()
    AcqProgress=collections.namedtuple("AcqProgress",["frames_done","cycles_done"])
    def get_progress(self):
        """
        Get acquisition progress.

        Return tuple ``(frames_done, cycles_done)`` (these are different in accum or kinetic mode).
        """
        self._camsel()
        return self.AcqProgress(*lib.GetAcquisitionProgress())
    def wait_for_frame(self, since="lastwait", timeout=20.):
        """
        Wait for a new camera frame.

        `since` specifies what constitutes a new frame.
        Can be ``"lastread"`` (wait for a new frame after the last read frame), ``"lastwait"`` (wait for a new frame after last :func:`wait_for_frame` call),
        or ``"now"`` (wait for a new frame acquired after this function call).
        If `timeout` is exceeded, raise :exc:`AndorTimeoutError`.
        """
        funcargparse.check_parameter_range(since,"since",{"lastread","lastwait","now"})
        if since=="lastwait":
            self._camsel()
            if timeout is None:
                lib.WaitForAcquisitionByHandle(self.handle)
            else:
                try:
                    lib.WaitForAcquisitionByHandleTimeOut(self.handle,int(timeout*1E3))
                except AndorLibError as e:
                    if e.text_code=="DRV_NO_NEW_DATA":
                        raise AndorTimeoutError
                    else:
                        raise
        elif since=="lastread":
            self._camsel()
            while not self.get_new_images_range():
                self.wait_for_frame(since="lastwait",timeout=timeout)
        else:
            rng=self.get_new_images_range()
            last_img=rng[1] if rng else None
            while True:
                self.wait_for_frame(since="lastwait",timeout=timeout)
                rng=self.get_new_images_range()
                if rng and (last_img is None or rng[1]>last_img):
                    return
    def cancel_wait(self):
        """Cancel wait"""
        self._camsel()
        lib.CancelWait()
    @contextlib.contextmanager
    def pausing_acquisition(self):
        """
        Context manager which temporarily pauses acquisition during execution of ``with`` block.

        Useful for applying certain settings which can't be changed during the acquisition.
        """
        acq=self.get_status()=="acquiring"
        try:
            self.stop_acquisition()
            yield
        finally:
            if acq:
                self.start_acquisition()

    ### Image settings and transfer controls ###
    def get_detector_size(self):
        """Get camera detector size (in pixels)"""
        self._camsel()
        if not self._check_option("get","AC_GETFUNCTION_DETECTORSIZE"): return
        return lib.GetDetector()
    _read_modes=["fvb","multi_track","random_track","single_track","image"]
    _read_modes_cap={"fvb":"AC_READMODE_FVB", "multi_track":"AC_READMODE_MULTITRACK",
        "random_track":"AC_READMODE_RANDOMTRACK", "single_track":"AC_READMODE_SINGLETRACK",
        "image":"AC_READMODE_FULLIMAGE"}
    def set_read_mode(self, mode):
        """
        Set camera read mode.

        Can be ``"fvb"`` (average all image vertically and return it as one row), ``"single_track"`` (read a single row or several rows averaged together),
        ``"multi_track"`` (read multiple rows or averaged sets of rows), ``"random_track"`` (read several arbitrary lines),
        or ``"image"`` (read a whole image or its rectangular part).
        """
        funcargparse.check_parameter_range(mode,"mode",self._read_modes)
        self._camsel()
        if not self._check_option("read",self._read_modes_cap[mode]): return
        lib.SetReadMode(self._read_modes.index(mode))
        self.read_mode=mode
    def setup_single_track_mode(self, center=0, width=1):
        """
        Setup singe-track read mode.

        `center` and `width` specify selection of the rows to be averaged together.
        """
        self._camsel()
        if not self._check_option("read","AC_READMODE_FULLIMAGE"): return
        lib.SetSingleTrack(center+1,width)
        self.read_params["single_track"]=(center,width)
    def setup_multi_track_mode(self, number=1, height=1, offset=1):
        """
        Setup multi-track read mode.

        `number` is the number of rows (or row sets) to read, `height` is number of one row set (1 for a single row),
        `offset` is the distance between the row sets.
        """
        self._camsel()
        if not self._check_option("read","AC_READMODE_MULTITRACK"): return
        res=lib.SetMultiTrack(number,height,offset)
        self.read_params["multi_track"]=(number,height,offset)
        return res
    def setup_random_track_mode(self, tracks=None):
        """
        Setup random track read mode.

        `tracks` is a list of tuples ``(start, stop)`` specifying track span (start are inclusive, stop are exclusive, starting from 0)
        """
        self._camsel()
        if not self._check_option("read","AC_READMODE_RANDOMTRACK"): return
        tracks=tracks or [(0,1)]
        lib.SetRandomTracks([(t[0]+1,t[1]) for t in tracks])
        self.read_params["random_track"]=list(tracks)
    def setup_image_mode(self, hstart=0, hend=None, vstart=0, vend=None, hbin=1, vbin=1):
        """
        Setup image read mode.

        `hstart` and `hend` specify horizontal image extent, `vstart` and `vend` specify vertical image extent
        (start are inclusive, stop are exclusive, starting from 0), `hbin` and `vbin` specify binning.
        """
        hdet,vdet=self.get_detector_size()
        if not self._check_option("read","AC_READMODE_FULLIMAGE"): return
        hend=hdet if hend is None else hend
        vend=vdet if vend is None else vend
        hend=min(hdet,hend) # truncate the image size
        vend=min(vdet,vend)
        if (hstart,hend,vstart,vend)!=(0,hdet,0,vdet):
            if not self._check_option("read","AC_READMODE_SUBIMAGE"): return
        hend-=(hend-hstart)%hbin # make size divisible by bin
        vend-=(vend-vstart)%vbin
        lib.SetImage(hbin,vbin,hstart+1,hend,vstart+1,vend)
        self.read_params["image"]=(hstart,hend,vstart,vend,hbin,vbin)
    
    def get_roi(self):
        """
        Get current ROI.

        Return tuple ``(hstart, hend, vstart, vend, hbin, vbin)``.
        """
        return self.read_params["image"]
    def set_roi(self, hstart=0, hend=None, vstart=0, vend=None, hbin=1, vbin=1):
        """
        Setup camera ROI.

        `hstart` and `hend` specify horizontal image extent, `vstart` and `vend` specify vertical image extent
        (start are inclusive, stop are exclusive, starting from 0), `hbin` and `vbin` specify binning.
        By default, all non-supplied parameters take extreme values.
        """
        self.setup_image_mode(hstart,hend,vstart,vend,hbin,vbin)
        self.set_read_mode("image")

    def get_data_dimensions(self, mode=None, params=None):
        """Get readout data dimensions for given read mode and read parameters (current by default)"""
        if mode is None:
            mode=self.read_mode
        if params is None:
            params=self.read_params[mode]
        hdet,_=self.get_detector_size()
        if mode in {"fvb","single_track"}:
            return (1,hdet)
        if mode=="multi_track":
            return (params[0],hdet)
        if mode=="random_track":
            return (len(params),hdet)
        if mode=="image":
            (hstart,hend,vstart,vend,hbin,vbin)=params
            return (vend-vstart)//vbin,(hend-hstart)//hbin
    def read_newest_image(self, dim=None, peek=False):
        """
        Read the newest image.

        `dim` specifies image dimensions (by default use dimensions corresponding to the current camera settings).
        If ``peek==True``, return the image but not mark it as read.
        """
        if dim is None:
            dim=self.get_data_dimensions()
        self._camsel()
        if peek:
            data=lib.GetMostRecentImage16(dim[0]*dim[1])
            return data.reshape((dim[0],dim[1])).transpose()
        else:
            rng=self.get_new_images_range()
            if rng:
                return self.read_multiple_images([rng[1],rng[1]],dim=dim)[0,:,:]
    def read_oldest_image(self, dim=None):
        """
        Read the oldest un-read image in the buffer.

        `dim` specifies image dimensions (by default use dimensions corresponding to the current camera settings).
        """
        if dim is None:
            dim=self.get_data_dimensions()
        self._camsel()
        data=lib.GetOldestImage16(dim[0]*dim[1])
        return data.reshape((dim[0],dim[1])).transpose()
    def get_ring_buffer_size(self):
        """Get the size of the image ring buffer"""
        self._camsel()
        return lib.GetSizeOfCircularBuffer()
    def get_new_images_range(self):
        """
        Get the range of the new images.
        
        Return tuple ``(first, last)`` with images range (inclusive).
        If no images are available, return ``None``.
        """
        self._camsel()
        try:
            rng=lib.GetNumberNewImages()
            return (rng[0]-1,rng[1]-1)
        except AndorLibError as e:
            if e.text_code=="DRV_NO_NEW_DATA":
                return None
            raise
    def read_multiple_images(self, rng=None, dim=None):
        """
        Read multiple images specified by `rng` (by default, all un-read images).

        `dim` specifies images dimensions (by default use dimensions corresponding to the current camera settings).
        """
        self._camsel()
        if rng is None:
            rng=self.get_new_images_range()
        if dim is None:
            dim=self.get_data_dimensions()
        if rng is None:
            return np.zeros((0,dim[1],dim[0]))
        data,vmin,vmax=lib.GetImages16(rng[0]+1,rng[1]+1,dim[0]*dim[1]*(rng[1]-rng[0]+1))
        return np.transpose(data.reshape((-1,dim[0],dim[1])),axes=[0,2,1])

    def flush_buffer(self):
        """Flush the camera buffer (restart the acquisition)"""
        acq_mode=self.acq_mode
        if acq_mode=="cont":
            self.set_acquisition_mode("single")
        else:
            self.set_acquisition_mode("cont")
        self.prepare_acquisition()
        self.set_acquisition_mode(acq_mode)
        self.prepare_acquisition()

    ### Combined functions ###
    def snap(self):
        """Snap a single image (with preset image read mode parameters)"""
        self.set_acquisition_mode("single")
        self.set_read_mode("image")
        self.start_acquisition()
        self.wait_for_frame()
        self.stop_acquisition()
        return self.read_newest_image()