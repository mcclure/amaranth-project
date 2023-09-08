# Board file for OpenFPGA/Analogue Pocket. Incomplete.
# Modeled on amaranth-boards de10-nano.py
# TODO:
#   1. Consider making Pocket a subclass.
#   2. Upstream to amaranth-boards 

import os
import subprocess

from amaranth.build import *
from amaranth.vendor.intel import *

__all__ = ["OpenFPGAPlatform"]

class OpenFPGAPlatform(IntelPlatform):
    device      = "5CEBA4"  # Quartus Lite identifies the physical device as a "5CEBA4F23C8" 
    package     = "F23"
    speed       = "C8"
    default_clk = "clk_74a"

    resources   = [
        Resource("clk_74a", 0, Pins("PIN_V15", dir="i"), # Notional main clock
                 Clock(74.25e6), Attrs(io_standard="3.3-V LVCMOS")), # -period 13.468 => 74.25 MHz
        Resource("clk_74b", 1, Pins("H16", dir="i"),     # Non-phase-aligned copy of main clock
                 Clock(74.25e6), Attrs(io_standard="1.8 V")),
    ]

    def toolchain_program(self, products, name):
    	sys.exit("toolchain_program for OpenFPGAPlatform is not yet known to work / be safe")
        quartus_pgm = os.environ.get("QUARTUS_PGM", "quartus_pgm")
        with products.extract("{}.sof".format(name)) as bitstream_filename:
            # The @2 selects the second device in the JTAG chain, because this chip
            # puts the ARM cores first.
            # THIS IS FROM THE DE10 CORE AND IT DOES *NOT* LOOK RIGHT HERE !!!
            subprocess.check_call([quartus_pgm, "--haltcc", "--mode", "JTAG",
                                   "--operation", "P;" + bitstream_filename + "@2"])

if __name__ == "__main__":
	sys.exit("No default program for OpenFPGA board") # No LED, unless debug cart turns out to offer one
