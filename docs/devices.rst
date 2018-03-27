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

The devices usually have ``get_settings`` and ``apply_settings`` methods which return Python dictionaries with the most common settings or take these dictionaries and apply them. ``get_settings`` can be particularly useful to check the device status and see if it is connected.

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

Currently there are classes for these devices:

    - Agilent AWG33220A arbitrary wave generator, AMP33502A amplifier, N9310A microwave generator, HP8712B and HP8722D vector network analyzers. Located in :mod:`pylablib.aux_libs.devices.AgilentElectronics`.
    - Agilent HP8168F laser. Located in :mod:`pylablib.aux_libs.devices.AgilentLasers`.
    - Andor cameras (tested with Andor IXON). Located in :mod:`pylablib.aux_libs.devices.Andor`.
    - Arcus PerforMax translational stages. Located in :mod:`pylablib.aux_libs.devices.Arcus`.
    - Attocube ANC300 controller. Located in :mod:`pylablib.aux_libs.devices.Attocube`.
    - Cryomagnetics LM500/510 cryogenic level meters. Located in :mod:`pylablib.aux_libs.devices.Cryomagnetics`.
    - HighFinesse WS/6 and WS/7 wavemeters. Located in :mod:`pylablib.aux_libs.devices.HighFinesse`.
    - Low-level IMAQdx camera controller, and more specific IMAQdx controller for PhotonFocus cameras. Located in :mod:`pylablib.aux_libs.devices.IMAQdx`.
    - Lakeshore 218 and 370 temperature controllers. Located in :mod:`pylablib.aux_libs.devices.Lakeshore`.
    - M squared ICE BLOC laser controller for SolsTiS lasers. Located in :mod:`pylablib.aux_libs.devices.M2`.
    - MKS 9xx pressure gauge. Located in :mod:`pylablib.aux_libs.devices.MKS`.
    - National Instruments DAQ devices. This is a restricted but simplified wrapper for the :mod:`nidaqmx` package, and should only be used for simple application. Located in :mod:`pylablib.aux_libs.devices.NI`.
    - Nuphoton NP2000 EDFA. Located in :mod:`pylablib.aux_libs.devices.NuPhoton`.
    - Ophir Vega power meter. Located in :mod:`pylablib.aux_libs.devices.Ophir`.
    - OZ Optics fiber-coupled devices: TF100 tunable filter, DD100 variable attenuator, and EPC04 polarization controller. Located in :mod:`pylablib.aux_libs.devices.OZOptics`.
    - Pfeiffer TPG261 pressure gauge. Located in :mod:`pylablib.aux_libs.devices.Pfeiffer`.
    - Pure Photonics PPCL200 laser in CBDX1 chassis. Located in :mod:`pylablib.aux_libs.devices.PurePhotonics`.
    - Rigol DSA1030A spectrum analyzer. Located in :mod:`pylablib.aux_libs.devices.Rigol`.
    - SmarAct SCU3D translational stage controller. Located in :mod:`pylablib.aux_libs.devices.SmarAct`.
    - Tektronix DPO2014, TDS2000, and MDO3000 scopes. Located in :mod:`pylablib.aux_libs.devices.Tektronix`.
    - Thorlabs PM100D power meter, FW102/202 motorized filter wheels, MDT693/4A high voltage sources, and MFF motorized flip mount. Located in :mod:`pylablib.aux_libs.devices.Thorlabs`.
    - Trinamic TMCM1100 stepper motor controller. Located in :mod:`pylablib.aux_libs.devices.Trinamic`.
    - Vaunix LMS (Lab Brick) microwave generators. Located in :mod:`pylablib.aux_libs.devices.Vaunix`.
    - Zurich Instruments HF2 / UHF Lock-In amplifiers. Located in :mod:`pylablib.aux_libs.devices.ZurichInstruments`.

------------------------
Additional requirements
------------------------

First, any device using :mod:`PyVISA` require NI VISA to be installed. See :mod:`PyVISA` for details.

Second, some devices need dlls supplied by the manufacturer:

    - Andor cameras: require `atmcd.dll` (currently supplied for x64 and x86).
    - Arcus PerforMax translational stages: require `PerformaxCom.dll` (currently supplied only for x64).
    - HighFinesse WS/6 and WS/7 wavemeters: require `wlmData.dll`. Each device needs a unique dll supplied by the manufacturer. Currently generic version for WS/6 and WS/7 are given, but they might not work properly.
    - SmarAct SCU3D translational stage controller: requires `SCU3DControl.dll` (currently supplied only for x64).

Many of these are supplied with this library, but they can be removed in future versions (e.g., for compatibility or legal reasons), and not all of them are present for x86 applications.

Third, some devices need additional software installed:

    - IMAQdx cameras: National Instruments IMAQdx library.
    - HighFinesse: manufacturer-provided drivers and software.
    - Thorlabs MFF: Kinesis software.
    - Zurich Instruments: manufacturer provided software and Python libraries.

The list might be incomplete, and it does not include drivers for USB devices.