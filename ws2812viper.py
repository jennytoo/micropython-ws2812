# -*- coding: utf-8 -*-

from array import array
import gc
import pyb


class WS2812(object):
    """
    Driver for WS2812 RGB LEDs. May be used for controlling single LED or chain
    of LEDs.

    Example of use:

        chain = WS2812(spi_bus=1, led_count=4)
        data = [
            (255, 0, 0),    # red
            (0, 255, 0),    # green
            (0, 0, 255),    # blue
            (85, 85, 85),   # white
        ]
        chain.show(data)

    This is completely separate from the normal ws2812 module. While it
    implements the same methods the actual implementation differs slightly
    and is not a drop-in replacement in all cases.

    Version: 1.5
    """
    def __init__(self, spi_bus=1, led_count=1, intensity=1):
        """
        Params:
        * spi_bus = SPI bus ID (1 or 2)
        * led_count = count of LEDs
        * intensity = light intensity (float up to 1)
        """
        self.led_count = led_count
        self.intensity = intensity

        # prepare SPI data buffer (4 bytes for each color)
        self.buf_length = self.led_count * 3 * 4
        self.buf = array('B', (0 for _ in range(self.buf_length)))

        # intermediate work buffer where data is buffered in the correct order
        self.work_buf_length = self.led_count * 3
        self.work_buf = array('B', (0 for _ in range(self.work_buf_length)))

        # SPI init
        self.spi = pyb.SPI(spi_bus, pyb.SPI.MASTER, baudrate=3200000, polarity=0, phase=0)

        # turn LEDs off
        self.show([])

    @property
    def intensity(self):
        """
        Return intensity as a float.
        """
        return float(self._intensity) / 256

    @intensity.setter
    def intensity(self, value):
        """
        Setting for intensity to store the actual value as an int.
        """
        self._intensity = int(min(1, value)*256+0.5)

    def show(self, data):
        """
        Show RGB data on LEDs. Expected data = [(R, G, B), ...] where R, G and B
        are intensities of colors in range from 0 to 255. One RGB tuple for each
        LED. Count of tuples may be less than count of connected LEDs.
        """
        self.fill_buf(data)
        self.send_buf()

    @staticmethod
    @micropython.viper
    def _prep_buf(src:ptr8, dst:ptr8, intensity:int, count:int):
        """
        Fill the send buffer from the work buffer. Only needs to be called
        prior to actually sending data.

        This routine is designed to make use of the viper emitter and as such
        must follow certain conventions. Most notably, there can only be 4
        parameters (3 prior to 23 Jul 2015) and parameters need type hints.
        """
        index = 0
        for i in range(count):
            value = ((src[i] * intensity) >> 8)
            dst[index] = (value >> 5) & 0x02 | (value >> 2) & 0x20 | 0x11
            index += 1
            dst[index] = (value >> 3) & 0x02 | (value)      & 0x20 | 0x11
            index += 1
            dst[index] = (value >> 1) & 0x02 | (value << 2) & 0x20 | 0x11
            index += 1
            dst[index] = (value << 1) & 0x02 | (value << 4) & 0x20 | 0x11
            index += 1

    def prep_buf(self):
        """
        Fill the send buffer from the work buffer.
        """
        self._prep_buf(
            self.work_buf,
            self.buf,
            self._intensity,
            self.work_buf_length)

    def send_buf(self):
        """
        Send buffer over SPI.
        """
        self.prep_buf()
        self.spi.send(self.buf)
        gc.collect()

    @micropython.native
    def update_buf(self, data, start=0):
        """
        Copy the buffer into the intermediate work buffer.
        """
        work_buf = self.work_buf
        index = start * 3
        for red, green, blue in data:
            work_buf[index] = green
            index += 1
            work_buf[index] = red
            index += 1
            work_buf[index] = blue
            index += 1
        return index // 3

    def fill_buf(self, data):
        """
        Fill buffer with RGB data.

        All LEDs after the data are turned off.
        """
        end = self.update_buf(data)

        # turn off the rest of the LEDs
        work_buf = self.work_buf
        for index in range(end * 3, self.work_buf_length):
            work_buf[index] = 0
