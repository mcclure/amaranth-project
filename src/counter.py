import amaranth as am
from doppler import DopplerPlatform


class Counter(am.Elaboratable):
    def __init__(self, n, need_overflow=False):
        # Store an n-bit register for the count value
        self.count = am.Signal(n)

        # Output a single-bit output signal
        self.has_overflow = need_overflow
        if need_overflow:
            self.overflow = am.Signal()

    def elaborate(self, platform):
        m = am.Module()
        # Count up each clock cycle
        m.d.sync += self.count.eq(self.count + 1)
        # Output overflow on cycles where the count is 0
        if self.has_overflow:
            m.d.comb += self.overflow.eq(self.count == 0)
        return m


class Top(am.Elaboratable):
    def __init__(self):
        # State
        self.current_led = Counter(4)

    def elaborate(self, platform):
        m = am.Module()

        m.submodules.current_led = self.current_led

        # Interface
        #button = platform.request("button", 0)
        kleds = [platform.request("kled", i) for i in range(4)]
        aled = platform.request("aled", 0)

        # Source: https://github.com/dadamachines/doppler-FPGA-firmware/blob/a3d57bb/doppler_simple_io/doppler_simple_io.v#L153-L168
        # Anode looks like (inverted) column select:
        # * 1110 for LEDs 0, 4,  8, 12
        # * 1101 for LEDs 1, 5,  9, 13
        # * 1011 for LEDs 2, 6, 10, 14
        # * 0111 for LEDs 3, 7, 11, 15
        for i in range(4):
            m.d.comb += \
                aled.o[0].eq(self.current_led.count % 4 == i)

        # Cathode looks like row select, but to turn off, we put it in high
        # impedance, rather than grounding it:

        m.d.comb += [kled.o.eq(1) for kled in kleds]
        for i in range(4):
            m.d.comb += \
                kleds[i].oe.eq(self.current_led.count // 4 == i)

        # This button isn't debounced, so it'll probably skip a whole lot every time you press it.
#        button_last = am.Signal()
#        m.d.sync += button_last.eq(button.i)
#        with m.If(~button.i & button_last):
#            m.d.sync += selected_led.eq(selected_led + 1)

        return m


if __name__ == "__main__":
    top = Top()
    plat = DopplerPlatform()
    plat.build(top)
