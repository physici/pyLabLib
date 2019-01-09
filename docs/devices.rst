.. _devices:

=======================
Specific device classes
=======================

.. note::
    Currently only available in the `dev` version of the library. See :ref:`install-github` for how to install this version.

----------------
General concepts
----------------

Most devices share common methods and approach to make them more predictable and easier to use.

First, the device identifier / address needs to be provided by user during the device object creation, and it is automatically connected. The devices have ``open`` and ``close`` methods but the device also works as a resource (with Python ``with`` statement), so these usually aren't used explicitly.

The devices usually have ``get_settings`` and ``apply_settings`` methods which return Python dictionaries with the most common settings or take these dictionaries and apply them.
In addition, there are ``get_full_status`` and ``get_full_info`` functions, which return progressively more information (``get_full_status`` adds variable status information which cannot be changed by user, and ``get_full_info`` adds constant device information, such as model name and serial number).
``get_full_info`` can be particularly useful to check the device status and see if it is connected and working properly.

Devices of the same kind (e.g., cameras or translation stages) aim to have consistent overlapping interfaces (where it makes sense), so different devices are fairly interchangeable in simple applications.

--------
Examples
--------

Connecting to a Cryomagnetics LM500 level meter and reading out the level at the first channel::

    from pylablib.aux_libs.devices import Cryomagnetics  # import the device library
    # Next, create the device object and connect to the device;
    #   the connection is automatically opened on creation, and closed when the ``with`` block is ended
    with Cryomagnetics.LM500("COM1") as lm:
        level = lm.get_level(1)  # read the level

Stepping the M squared laser wavelength and recording an image from the Andor IXON camera at each step::

    from pylablib.aux_libs.devices import M2, Andor  # import the device libraries
    with M2.M2ICE("192.168.0.1", 39933) as laser, Andor.AndorCamera() as cam:  # connect to the devices
        # change some camera parameters
        cam.set_shutter("open")
        cam.set_exposure(50E-3)
        cam.set_amp_mode(preamp=2)
        cam.set_EMCCD_gain(128)
        cam.setup_image_mode(vbin=2, hbin=2)
        # setup acquisition mode
        cam.set_acquisition_mode("cont")
        cam.setup_cont_mode()
        # start camera acquisition
        cam.start_acquisition()
        wavelength = 740E-9  # initial wavelength (in meters)
        images = []
        while wavelength < 770E-9:
            laser.tune_wavelength_table(wavelength)  # tune the laser frequency (using coarse tuning)
            time.sleep(0.5)  # wait until the laser stabilizes
            cam.wait_for_frame()  # ensure that there's a frame in the camera queue
            frame = cam.read_newest_image()
            images.append(frame)
            wavelength += 0.5E-9


---------------
List of devices
---------------

===================================    ==============================    ====================================================   ====================================================
Device                                 Kind                              Module                                                 Comments
===================================    ==============================    ====================================================   ====================================================
Msquared ICE BLOC                      Laser                             :mod:`pylablib.aux_libs.devices.M2`
Photonics PPCL200                      Laser                             :mod:`pylablib.aux_libs.devices.PurePhotonics`         In CBDX1 chassis
Lighthouse Photonics SproutG           Laser                             :mod:`pylablib.aux_libs.devices.LighthousePhotonics`
Agilent HP8168F                        Laser                             :mod:`pylablib.aux_libs.devices.AgilentLasers`
Nuphoton NP2000                        EDFA                              :mod:`pylablib.aux_libs.devices.NuPhoton`
HighFinesse WS/6 and WS/7              Wavemeter                         :mod:`pylablib.aux_libs.devices.HighFinesse`
Andor                                  Camera                            :mod:`pylablib.aux_libs.devices.Andor`                 Tested with Andor IXON and Luca
Hamamatsu DCAM interface               Camera                            :mod:`pylablib.aux_libs.devices.DCAM`                  Tested with ORCA-Flash 4.0 (C11440-22CU)
NI IMAQdx interface                    Camera                            :mod:`pylablib.aux_libs.devices.IMAQdx`                Tested with Pure Photonics AG with Ethernet connection
Ophir Vega                             Optical power meter               :mod:`pylablib.aux_libs.devices.Ophir`
Thorlabs PM100D                        Optical power meter               :mod:`pylablib.aux_libs.devices.Thorlabs`
OZ Optics TF100                        Tunable optical filter            :mod:`pylablib.aux_libs.devices.OZOptics`
OZ Optics DD100                        Variable optical attenuator       :mod:`pylablib.aux_libs.devices.OZOptics`
OZ Optics EPC04                        Polarization controller           :mod:`pylablib.aux_libs.devices.OZOptics`
Agilent AWG33220A                      Arbitrary wave generator          :mod:`pylablib.aux_libs.devices.AgilentElectronics`
Agilent N9310A                         Microwave generator               :mod:`pylablib.aux_libs.devices.AgilentElectronics`
Vaunix LMS (Lab Brick)                 Microwave generator               :mod:`pylablib.aux_libs.devices.Vaunix`
Thorlabs MDT693/4A                     High voltage source               :mod:`pylablib.aux_libs.devices.Thorlabs`
Agilent AMP33502A                      DC amplifier                      :mod:`pylablib.aux_libs.devices.AgilentElectronics`
Rigol DSA1030A                         Microwave spectrum analyzer       :mod:`pylablib.aux_libs.devices.Rigol`
Agilent HP8712B, HP8722D               Vector network analyzers          :mod:`pylablib.aux_libs.devices.AgilentElectronics`
Tektronix DPO2014, TDS2000, MDO3000    Oscilloscopes                     :mod:`pylablib.aux_libs.devices.Tektronix`
NI DAQ interface                       NI DAQ devices                    :mod:`pylablib.aux_libs.devices.NI`                    Wrapper around the :mod:`nidaqmx` package. Tested with NI USB-6008 and NI PCIe-6323
Zurich Instruments HF2 / UHF           Lock-in amplifiers                :mod:`pylablib.aux_libs.devices.ZurichInstruments`
Arcus PerforMax                        Translation stage                 :mod:`pylablib.aux_libs.devices.Arcus`                 Tested with PMX-4EX-SA stage.
SmarAct SCU3D                          Translation stage                 :mod:`pylablib.aux_libs.devices.SmarAct`
Attocube ANC300                        Piezo slider controller           :mod:`pylablib.aux_libs.devices.Attocube`
Trinamic TMCM1110                      Stepper motor controller          :mod:`pylablib.aux_libs.devices.Trinamic`
Thorlabs KDC101                        DC servo motor controller         :mod:`pylablib.aux_libs.devices.Thorlabs`
Thorlabs FW102/202                     Motorized filter wheel            :mod:`pylablib.aux_libs.devices.Thorlabs`
Thorlabs MFF                           Motorized flip mount              :mod:`pylablib.aux_libs.devices.Thorlabs`
Cryomagnetics LM500/510                Cryogenic level meter             :mod:`pylablib.aux_libs.devices.Cryomagnetics`
Lakeshore 218 and 370                  Temperature controllers           :mod:`pylablib.aux_libs.devices.Lakeshore`
MKS 9xx                                Pressure gauge                    :mod:`pylablib.aux_libs.devices.MKS`
Pfeiffer TPG261                        Pressure gauge                    :mod:`pylablib.aux_libs.devices.Pfeiffer`
===================================    ==============================    ====================================================   ====================================================


------------------------
Additional requirements
------------------------

First, any device using :mod:`PyVISA` require NI VISA to be installed. See :mod:`PyVISA` for details.

Second, some devices need dlls supplied by the manufacturer:

    - Andor cameras: require `atmcd.dll` (currently supplied for x64 and x86).
    - Arcus PerforMax translation stages: require `PerformaxCom.dll` and `SiUSBXp.dll` (currently supplied only for x64).
    - HighFinesse WS/6 and WS/7 wavemeters: require `wlmData.dll`. Each device needs a unique dll supplied by the manufacturer. Currently generic version for WS/6 and WS/7 are given, but they might not work properly.
    - SmarAct SCU3D translation stage controller: requires `SCU3DControl.dll` (currently supplied only for x64).

Many of these are supplied with this library (only on GitHub), but they can be removed in future versions (e.g., for compatibility or legal reasons), and not all of them are present for x86 applications. If you installed the library using pip, you can download the dll's on GitHub (they are located in ``pylablib/aux_libs/devices/libs/``) and place them into the package folder (correspondingly, into ``aux_libs/devices/libs/`` inside the main package folder, which is usually something like ``Python36/Lib/site-packages/pylablib/``).

Third, some devices need additional software installed:

    - IMAQdx cameras: National Instruments IMAQdx library.
    - Hamamatsu DCAM cameras: DCAM software and drivers.
    - NI DAQs: National Instruments NI-DAQmx library (with C support).
    - HighFinesse: manufacturer-provided drivers and software (specific to the particular wavemeter).
    - Thorlabs MFF: Kinesis/APT software.
    - Trinamic hardware: Trinamic TMCL-IDE (needed to install device drivers)
    - Arcus PerforMax sofrware: Arcus Drivers and Tools, Arcus USB Series and Arcus Performax Series software (needed to install device drivers).
    - Zurich Instruments: manufacturer provided software and Python libraries.

The list might be incomplete, and it does not include drivers for all USB devices.