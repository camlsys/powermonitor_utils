"""
Power Monitor Utilities

High-level wrapper around Monsoon Power Monitor library.
"""
from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import sys
import time
import socket
import pickle
from collections import namedtuple

import numpy as np

import Monsoon
import Monsoon.sampleEngine as sampleEngine
import Monsoon.reflash as reflash
import Monsoon.Operations as op

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
log_format = logging.Formatter(
                fmt='%(asctime)s [%(levelname)s] %(message)s',
                datefmt="%H:%M:%S")
log_handler = logging.StreamHandler()
log_handler.setFormatter(log_format)
logger.addHandler(log_handler)


class PowerMonitor(object):
    """
    LVPM (white Power Monitor) part number FTA22D - Voltage 2.0 - 4.55
    HVPM (black Power Monitor) part number AAA10F - Voltage 0.8 - 13.5
    """
    def __init__(self, model='black'):
        self.model = model

        # TODO: Find a way to detect PM type at run-time
        #   maybe there's something in the status packet?
        # Mon.fillStatusPacket()
        # Mon.statusPacket.firmwareVersion

        if model == 'black':
            self.device = Monsoon.HVPM.Monsoon()
        elif model == 'white':
            self.device = Monsoon.LVPM.Monsoon()
        else:
            logger.error("Device type is not valid.")

    def __enter__(self):
        self.device.setup_usb()
        self.device.fillStatusPacket()
        self.serial_number = self.device.getSerialNumber()

        logger.info("Device Serial Number: {}".format(self.serial_number))

        self.engine = sampleEngine.SampleEngine(self.device)

        self.all_channels = [sampleEngine.channels.MainCurrent,
                             sampleEngine.channels.MainVoltage,
                             sampleEngine.channels.USBCurrent,
                             sampleEngine.channels.USBVoltage,
                             sampleEngine.channels.AuxCurrent,
                             sampleEngine.channels.timeStamp]

        return self

    def __exit__(self, *args):
        self.device.closeDevice()

    def power_off(self):
        self.device.setVout(0)

    def power_on(self, vout=5.0):
        # TODO: Check the range
        self.device.setVout(vout)

    def power_on_for_pi(self):
        """
        Sets the correct voltage on the main channel for Raspberry Pi"
        """
        if self.model == 'white':

            logger.warning(
                "White Power Monsoon's maximum voltage is 4.2V. Raspberry Pi "
                "may still work with this voltage but some parts (e.g. LEDs) "
                "may not work.")

            self.device.setVout(4.2)
        else:
            self.device.setVout(5.0)

    def enable_all_channels(self):
        for channel in self.all_channels:
            self.engine.enableChannel(channel)

    def disable_all_channels(self):
        for channel in self.all_channels:
            self.engine.disableChannel(channel)

    def enable_usb_channels(self):
        self.engine.enableChannel(sampleEngine.channels.USBCurrent)
        self.engine.enableChannel(sampleEngine.channels.USBVoltage)

    def disable_usb_channels(self):
        self.engine.disableChannel(sampleEngine.channels.USBCurrent)
        self.engine.disableChannel(sampleEngine.channels.USBVoltage)

    def enable_main_channels(self):
        self.engine.enableChannel(sampleEngine.channels.MainCurrent)
        self.engine.enableChannel(sampleEngine.channels.MainVoltage)

    def disable_usb_channels(self):
        self.engine.disableChannel(sampleEngine.channels.USBCurrent)
        self.engine.disableChannel(sampleEngine.channels.USBVoltage)

    def enable_timestamp_channel(self):
        self.engine.enableChannel(sampleEngine.channels.timeStamp)

    def disable_timestamp_channel(self):
        self.engine.disableChannel(sampleEngine.channels.timeStamp)

    def live(self, num_samples=sampleEngine.triggers.SAMPLECOUNT_INFINITE):
        """Not particularly useful but good for debugging."""
        self.engine.ConsoleOutput(True)
        self.engine.startSampling(sampleEngine.triggers.SAMPLECOUNT_INFINITE)

    def start_sampling(self, console_output=True, csv_output=None):
        if csv_output is not None:
            self.engine.enableCSVOutput(csv_output)
        else:
            self.engine.disableCSVOutput()

        self.engine.ConsoleOutput(console_output)

        # self.engine.setTriggerChannel(sampleEngine.channels.MainCurrent)
        self.engine.startSampling(sampleEngine.triggers.SAMPLECOUNT_INFINITE)
        # self.engine.startSampling(300)

        if csv_output is None:
            return self.read_samples()

    def read_samples(self):
        samples = self.engine.getSamples()

        parsed = namedtuple(
                'Parsed_Samples', ['timeStamp', 'mainCurrent', 'auxCurrent',
                                   'usbCurrent', 'mainVoltage', 'usbVoltage'])

        # Use sampleEngine.channel to select the appropriate list index.
        parsed.timeStamp = samples[sampleEngine.channels.timeStamp]
        parsed.mainCurrent = samples[sampleEngine.channels.MainCurrent]
        parsed.auxCurrent = samples[sampleEngine.channels.AuxCurrent]
        parsed.usbCurrent = samples[sampleEngine.channels.USBCurrent]
        parsed.mainVoltage = samples[sampleEngine.channels.MainVoltage]
        parsed.usbVoltage = samples[sampleEngine.channels.USBVoltage]

        return parsed

    def set_trigger_from_remote_pi(self):

        # self.device.setUSBPassthroughMode(op.USB_Passthrough.On)

        # TODO: Is it necessary to enable channel for triggering?
        # self.engine.enableChannel(sampleEngine.channels.USBVoltage)
        self.engine.setStartTrigger(sampleEngine.triggers.GREATER_THAN, 3.00)
        self.engine.setStopTrigger(sampleEngine.triggers.LESS_THAN, 1.00)
        self.engine.setTriggerChannel(sampleEngine.channels.USBVoltage)

    def ncs_experiment(self):
        self.enable_all_channels()
        self.set_trigger_from_remote_pi()
        samples = self.start_sampling(console_output=True)
        # test_name = self.get_remote_trigger_details()
        watts = self.compute_power(samples.mainCurrent, samples.mainVoltage)

        total_time_s = (samples.timeStamp[-1] - samples.timeStamp[0])
        total_time_ms = total_time_s * 1000
        print('Total captured time (ms): {}'.format(total_time_ms))

        # total_watts = np.sum(watts)
        # logger.info("Total power: {}".format(total_watts / 5000.0))

        timeStamp_np = np.array(samples.timeStamp)
        time_deltas = timeStamp_np[1:] - timeStamp_np[:-1]
        total_energy = np.sum(np.multiply(watts[:-1], time_deltas))
        logger.info("Total Energy (J): {}".format(total_energy))
        logger.info("Average in Watts: {}".format(total_energy/total_time_s))

    def get_remote_trigger_details(self, remote_ip):
        """ TODO """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((remote_ip, 8887))

            # Pickle uses different default protocols in Python 2 and 3 so we
            # need to explicitly define one
            serialised_message = pickle.dumps("Tell me everything", protocol=0)

            s.sendall(serialised_message)

            # Block and wait for a reply
            serialised_reply = s.recv(4096)
            reply = pickle.loads(serialised_reply)

            logger.info('Received test details from remote tester')

            return reply
        except:
            logger.error('Something wrong with socket connection')
            sys.exit()
        finally:
            s.close()

    @staticmethod
    def compute_power(currents, voltages):
        # convert from mA to Amps
        scaled_currents = np.array(currents) / 1000.0

        # Element-wise multiply to produce Watts.
        power = np.multiply(scaled_currents, voltages)

        return power

    @staticmethod
    def flash(image, serialno=None):
        """based on multiUnitReflashExample.py in PyMonsoon"""

        print("Reflashing unit number " + repr(serialno))
        Mon = Monsoon.HVPM.Monsoon()
        Mon.setup_usb(serialno)
        Mon.resetToBootloader()

        time.sleep(2)  # Gives time for unit re-enumeration.
        Ref = reflash.bootloaderMonsoon()
        Ref.setup_usb()
        Header, Hex = Ref.getHeaderFromFWM(image)
        if(Ref.verifyHeader(Header)):
            Ref.writeFlash(Hex)
        Ref.resetToMainSection()

        # Verify the firmware was flashed properly.
        time.sleep(2)  # Gives time for unit re-enumeration
        Mon.setup_usb(serialno)
        Mon.fillStatusPacket()
        print("Unit number " + repr(Mon.getSerialNumber()) + " finished.  New firmware revision: " + repr(Mon.statusPacket.firmwareVersion))
        Mon.closeDevice()

    @staticmethod
    def upgrade_black_device_firmware():
        """ Reflash white Power Monitor with the new USB Protocol firmware."""
        PowerMonitor.flash('./firmware_images/HVPM_RevE_Prot1_Ver32.fwm')

    @staticmethod
    def upgrade_white_device_firmware():
        """ Reflash white Power Monitor with the new USB Protocol firmware."""
        PowerMonitor.flash('./firmware_images/LVPM_RevE_Prot_1_Ver25_beta.fwm')

    @staticmethod
    def downgrade_white_device_firmware():
        """ Return white Power Monitor firmware to the original serial protocol
        firmware."""
        PowerMonitor.flash('./firmware_images/PM_RevD_Prot17_Ver20.hex')
