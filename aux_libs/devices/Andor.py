from . import Andor_lib as lib

from ...core.devio import backend
from ...core.utils import funcargparse

import collections

class AndorError(RuntimeError):
    "Generic Andor camera error."


def get_cameras_number():
    return lib.GetAvailableCameras()

class AndorCamera(backend.IBackendWrapper):
    def __init__(self, idx=0, ini_path=""):
        backend.IBackendWrapper.__init__(self,idx)
        self.idx=idx
        self.ini_path=ini_path
        self.handle=None
        self.open()
        self.channel=None
        self.oamp=None
        self.hsspeed=None
        self.preamp=None
        self.vsspeed=None
        self.init_speeds()
        self.EMCCD_gain=None
        self.set_EMCCD_gain(0,False)
        self.shutter_mode=None
        self.set_shutter("close")
        self.trigger_mode=None
        self.set_trigger_mode("int")
        self.acq_mode=None
        self.set_acquisition_mode("cont")
        self.setup_cont_mode()
        self.set_exposure(10E-3)
        self.frame_transfer_mode=None
        self.enable_frame_transfer_mode(False)
        self.read_mode=None
        self.set_read_mode("image")
        self.read_params=dict(zip(self._read_modes,[None]*len(self._read_modes)))
        self.setup_image_mode()
        self.setup_single_track_mode(1,1)
        self.setup_multi_track_mode(1,1,1)
        self.setup_random_track_mode([(1,1)])
        self.flush_buffer()

        self._add_settings_node("model_data",lambda: tuple(self.get_model_data()))
        self._add_settings_node("temperature",self.get_temperature,self.set_temperature)
        self._add_settings_node("cooler",self.is_cooler_on,self.set_cooler)
        self._add_settings_node("channel",lambda:self.channel,lambda x:self.set_amp_mode(channel=x))
        self._add_settings_node("oamp",lambda:self.oamp,lambda x:self.set_amp_mode(oamp=x))
        self._add_settings_node("hsspeed",lambda:self.hsspeed,lambda x:self.set_amp_mode(hsspeed=x))
        self._add_settings_node("preamp",lambda:self.preamp,lambda x:self.set_amp_mode(preamp=x))
        self._add_settings_node("vsspeed",lambda:self.vsspeed,self.set_vsspeed)
        self._add_settings_node("EMCCD_gain",lambda:self.EMCCD_gain,lambda x: self.set_EMCCD_gain(*x))
        self._add_settings_node("shutter",lambda:self.shutter_mode,self.set_shutter)
        self._add_settings_node("trigger_mode",lambda:self.trigger_mode,self.set_trigger_mode)
        self._add_settings_node("acq_mode",lambda:self.acq_mode,self.set_acquisition_mode)
        self._add_settings_node("frame_transfer",lambda:self.frame_transfer_mode,self.enable_frame_transfer_mode)
        self._add_settings_node("exposure",lambda:self.get_timings()[0],self.set_exposure)
        self._add_settings_node("read_mode",lambda:self.read_mode,self.set_read_mode)
        self._add_settings_node("read_parameters",lambda:self.read_params[self.read_mode],self._setup_read_parameters)
        self._add_settings_node("detector_size",self.get_detector_size)

    def _camsel(self):
        if self.handle is None:
            raise AndorError("camera is not opened")
        if lib.GetCurrentCamera()!=self.handle:
            lib.SetCurrentCamera(self.handle)
    def open(self):
        ncams=get_cameras_number()
        if self.idx>=ncams:
            raise AndorError("camera index {} is not available ({} cameras exist)".format(self.idx,ncams))
        self.handle=lib.GetCameraHandle(self.idx)
        self._camsel()
        lib.Initialize(self.ini_path)
    def close(self):
        try:
            self._camsel()
        except AndorError:
            return
        try:
            lib.ShutDown()
        except lib.AndorLibError as e:
            if e.text_code!="DRV_NOT_INITIALIZED":
                raise
        self.handle=None

    ModelData=collections.namedtuple("ModelData",["controller_model","head_model","serial_number"])
    def get_model_data(self):
        self._camsel()
        control_model=lib.GetControllerCardModel()
        head_model=lib.GetHeadModel()
        serial_number=lib.GetCameraSerialNumber()
        return self.ModelData(control_model,head_model,serial_number)
        

    ### Generic controls ###
    def get_status(self):
        self._camsel()
        status=lib.GetStatus()
        text_status=lib.Andor_statuscodes[status]
        if text_status=="DRV_IDLE":
            return "idle"
        if text_status=="DRV_TEMPCYCLE":
            return "temp_cycle"
        if text_status=="DRV_ACQUIRING":
            return "acquiring"
        raise lib.AndorLibError("GetStatus",status)
    def get_capibilities(self):
        self._camsel()
        return lib.GetCapabilities()

    ### Cooler controls ###
    def is_cooler_on(self):
        self._camsel()
        return bool(lib.IsCoolerOn())
    def set_cooler(self, on=True):
        self._camsel()
        if on:
            lib.CoolerON()
        else:
            lib.CoolerOFF()
    _temp_status={"DRV_TEMPERATURE_OFF":"off","DRV_TEMPERATURE_NOT_REACHED":"not_reached","DRV_TEMPERATURE_NOT_STABILIZED":"not_stabilized",
                    "DRV_TEMPERATURE_DRIFT":"drifted","DRV_TEMPERATURE_STABILIZED":"stabilized",}
    def get_temperature_status(self):
        self._camsel()
        status=lib.GetTemperature()[1]
        return self._temp_status[status]
    def get_temperature(self):
        self._camsel()
        return lib.GetTemperatureF()[0]
    def set_temperature(self, temperature, enable_cooler=True):
        self._camsel()
        rng=lib.GetTemperatureRange()
        temperature=max(temperature,rng[0])
        temperature=min(temperature,rng[1])
        lib.SetTemperature(temperature)
        if enable_cooler:
            self.set_cooler(True)
    
    ### Amplifiers/shift speeds controls ###
    def get_all_amp_modes(self):
        self._camsel()
        return lib.get_all_amp_modes()
    def get_max_vsspeed(self):
        self._camsel()
        return lib.GetFastestRecommendedVSSpeed()[0]
    def set_amp_mode(self, channel=None, oamp=None, hsspeed=None, preamp=None):
        self._camsel()
        channel=self.channel if channel is None else channel
        oamp=self.oamp if oamp is None else oamp
        hsspeed=self.hsspeed if hsspeed is None else hsspeed
        preamp=self.preamp if preamp is None else preamp
        lib.set_amp_mode((channel,oamp,hsspeed,preamp))
        self.channel=channel
        self.oamp=oamp
        self.hsspeed=hsspeed
        self.preamp=preamp
    def set_vsspeed(self, vsspeed):
        self._camsel()
        lib.SetVSSpeed(vsspeed)
        self.vsspeed=vsspeed
    def set_EMCCD_gain(self, gain, advanced=False):
        self._camsel()
        lib.set_EMCCD_gain(gain,advanced)
        self.EMCCD_gain=(gain,advanced)

    def get_channel_bitdepth(self, channel=None):
        self._camsel()
        return lib.GetBitDepth(self.channel if channel is None else channel)
    def get_oamp_desc(self, oamp=None):
        return lib._oamp_kinds[self.oamp if oamp is None else oamp]
    def get_hsspeed_frequency(self, hsspeed=None):
        self._camsel()
        return lib.GetHSSpeed(self.hsspeed if hsspeed is None else hsspeed)*1E6
    def get_preamp_gain(self, preamp=None):
        self._camsel()
        return lib.GetPreAmpGain(self.preamp if preamp is None else preamp)
    def get_vsspeed_period(self, vsspeed=None):
        self._camsel()
        return lib.GetVSSpeed(self.vsspeed if vsspeed is None else vsspeed)
    def get_EMCCD_gain(self):
        self._camsel()
        return lib.get_EMCCD_gain()

    def init_speeds(self):
        mode=self.get_all_amp_modes()[0]
        self.set_amp_mode(mode.channel,mode.oamp,mode.hsspeed,mode.preamp)
        vsspeed=self.get_max_vsspeed()
        self.set_vsspeed(vsspeed)
        self.set_EMCCD_gain(0,advanced=False)

    ### Shutter controls ###
    def get_min_shutter_times(self):
        self._camsel()
        return lib.GetShutterMinTimes()
    def set_shutter(self, mode, ttl_mode=0, open_time=None, close_time=None):
        if mode in [0,False]:
            mode="close"
        if mode in [1,True]:
            mode="open"
        shutter_modes=["auto","open","close"]
        funcargparse.check_parameter_range(mode,"state",shutter_modes)
        self._camsel()
        min_open_time,min_close_time=self.get_min_shutter_times()
        open_time=min_open_time if open_time is None else open_time
        close_time=min_close_time if close_time is None else close_time
        lib.SetShutter(ttl_mode,shutter_modes.index(mode),open_time,close_time)
        self.shutter_mode=mode

    ### Misc controls ###
    def set_fan_mode(self, mode):
        text_modes=["full","low","off"]
        funcargparse.check_parameter_range(mode,"mode",text_modes)
        self._camsel()
        lib.SetFanMode(mode)

    def read_in_aux_port(self, port):
        self._camsel()
        return lib.InAuxPort(port)
    def set_out_aux_port(self, port, state):
        self._camsel()
        return lib.OutAuxPort(port,state)

    ### Trigger controls ###
    def set_trigger_mode(self, mode):
        trigger_modes={"int":0,"ext":1,"ext_start":6,"ext_exp":7,"ext_fvb_em":9,"software":10,"ext_charge_shift":12}
        funcargparse.check_parameter_range(mode,"mode",trigger_modes.keys())
        self._camsel()
        lib.SetTriggerMode(trigger_modes[mode])
        self.trigger_mode=mode
    def get_trigger_level_limits(self):
        self._camsel()
        return lib.GetTriggerLevelRange()
    def setup_ext_trigger(self, level, invert, term_highZ=True):
        self._camsel()
        lib.SetTriggerLevel(level)
        lib.SetTriggerInvert(invert)
        lib.SetExternalTriggerTermination(term_highZ)
    def send_software_trigger(self):
        self._camsel()
        lib.SendSoftwareTrigger()

    ### Acquisition mode controls ###
    def set_acquisition_mode(self, mode):
        acq_modes={"single":1,"accum":2,"kinetics":3,"fast_kinetics":4,"cont":5}
        funcargparse.check_parameter_range(mode,"mode",acq_modes.keys())
        self._camsel()
        lib.SetAcquisitionMode(acq_modes[mode])
        self.acq_mode=mode
    def setup_accum_mode(self, num, cycle_time=0):
        self._camsel()
        lib.SetNumberAccumulations(num)
        lib.SetAccumulationCycleTime(cycle_time)
    def setup_kinetic_mode(self, num, cycle_time=0., num_acc=1, cycle_time_acc=0., num_prescan=0):
        self._camsel()
        lib.SetNumberKinetics(num)
        lib.SetNumberAccumulations(num_acc)
        lib.SetNumberPrescans(num_prescan)
        lib.SetKineticCycleTime(cycle_time)
        lib.SetAccumulationCycleTime(cycle_time_acc)
    def setup_fast_kinetic_mode(self, num, cycle_time_acc=0):
        self._camsel()
        lib.SetNumberKinetics(num)
        lib.SetAccumulationCycleTime(cycle_time_acc)
    def setup_cont_mode(self, cycle_time=0):
        self._camsel()
        lib.SetKineticCycleTime(cycle_time)
    def set_exposure(self, exposure):
        self._camsel()
        lib.SetExposureTime(exposure)
    def enable_frame_transfer_mode(self, enable=True):
        self._camsel()
        lib.SetFrameTransferMode(enable)
        self.frame_transfer_mode=enable
    AcqTimes=collections.namedtuple("AcqTimes",["exposure","accum_cycle_time","kinetic_cycle_time"])
    def get_timings(self):
        self._camsel()
        return self.AcqTimes(*lib.GetAcquisitionTimings())
    def get_readout_time(self):
        self._camsel()
        return lib.GetReadOutTime()
    def get_keepclean_time(self):
        self._camsel()
        return lib.GetKeepCleanTime()

    ### Acquisition process controls ###
    def prepare_acquisition(self):
        self._camsel()
        lib.PrepareAcquisition()
    def start_acquisition(self):
        self._camsel()
        lib.StartAcquisition()
    def stop_acquisition(self):
        self._camsel()
        lib.AbortAcquisition()
    AcqProgress=collections.namedtuple("AcqProgress",["frames_done","cycles_done"])
    def get_progress(self):
        self._camsel()
        return self.AcqProgress(lib.GetAcquisitionProgress())
    def wait_for_frame(self, timeout=None):
        self._camsel()
        if timeout is None:
            lib.WaitForAcquisitionByHandle(self.handle)
        else:
            lib.WaitForAcquisitionByHandleTimeOut(self.handle,int(timeout*1E3))
    def cancel_waut(self):
        self._camsel()
        lib.CancelWait()

    ### Image settings and transfer controls ###
    def get_detector_size(self):
        self._camsel()
        return lib.GetDetector()
    _read_modes=["fvb","multi_track","random_track","single_track","image"]
    def set_read_mode(self, mode):
        funcargparse.check_parameter_range(mode,"mode",self._read_modes)
        self._camsel()
        lib.SetReadMode(self._read_modes.index(mode))
        self.read_mode=mode
    def setup_single_track_mode(self, center, width):
        self._camsel()
        lib.SetSingleTrack(center,width)
        self.read_params["single_track"]=(center,width)
    def setup_multi_track_mode(self, number, height, offset):
        self._camsel()
        res=lib.SetMultiTrack(number,height,offset)
        self.read_params["multi_track"]=(number,height,offset)
        return res
    def setup_random_track_mode(self, tracks):
        self._camsel()
        lib.SetRandomTracks(tracks)
        self.read_params["random_track"]=list(tracks)
    def setup_image_mode(self, hstart=1, hend=None, vstart=1, vend=None, hbin=1, vbin=1):
        hdet,vdet=self.get_detector_size()
        hend=hdet if hend is None else hend
        vend=vdet if vend is None else vend
        lib.SetImage(hbin,vbin,hstart,hend,vstart,vend)
        self.read_params["image"]=(hstart,hend,vstart,vend,hbin,vbin)
    def _setup_read_parameters(self, params):
        if self.read_mode=="multi_track":
            self.setup_multi_track_mode(*params)
        elif self.read_mode=="random_track":
            self.setup_random_track_mode(*params)
        elif self.read_mode=="single_track":
            self.setup_single_track_mode(*params)
        elif self.read_mode=="image":
            self.setup_image_mode(*params)

    def get_data_dimensions(self, mode=None, params=None):
        if mode is None:
            mode=self.read_mode
        if params is None:
            params=self.read_params[mode]
        hdet,vdet=self.get_detector_size()
        if mode in {"fvb","single_track"}:
            return (1,hdet)
        if mode=="multi_track":
            return (params[0],hdet)
        if mode=="random_track":
            return (len(params),hdet)
        if mode=="image":
            (hstart,hend,vstart,vend,hbin,vbin)=params
            return ((hend-hstart+1)//hbin,(vend-vstart+1)//vbin)
    def read_newest_image(self, dim=None):
        if dim is None:
            dim=self.get_data_dimensions()
        self._camsel()
        data=lib.GetMostRecentImage16(dim[0]*dim[1])
        return data.reshape((dim[0],dim[1]))
    def read_oldest_image(self, dim=None):
        if dim is None:
            dim=self.get_data_dimensions()
        self._camsel()
        data=lib.GetOldestImage16(dim[0]*dim[1])
        return data.reshape((dim[0],dim[1]))
    def get_ring_buffer_size(self):
        self._camsel()
        return lib.GetSizeOfCircularBuffer()
    def get_new_images_range(self):
        self._camsel()
        return lib.GetNumberNewImages()
    def read_multiple_images(self, rng=None, dim=None):
        self._camsel()
        if rng is None:
            rng=self.get_new_images_range()
        if dim is None:
            dim=self.get_data_dimensions()
        data,vmin,vmax=lib.GetImages16(rng[0],rng[1],dim[0]*dim[1])
        return data.reshape((-1,dim[0],dim[1]))

    def flush_buffer(self):
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
        self.set_acquisition_mode("single")
        self.set_read_mode("image")
        self.start_acquisition()
        self.wait_for_frame()
        self.stop_acquisition()
        return self.read_newest_image()