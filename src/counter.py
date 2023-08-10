import amaranth as am
from doppler import DopplerPlatform


class Counter(am.Elaboratable):
    def __init__(self, n, need_overflow=False):
        # Store an n-bit register for the count value
        self.count = am.Signal(n)

        # Output a single-bit output signal
        self._has_overflow = need_overflow
        if need_overflow:
            self.overflow = am.Signal()

    def elaborate(self, platform):
        m = am.Module()
        # Count up each clock cycle
        m.d.sync += self.count.eq(self.count + 1)
        # Output overflow on cycles where the count is 0
        if self._has_overflow:
            m.d.comb += self.overflow.eq(self.count == 0)
        return m


class Top(am.Elaboratable):
    def __init__(self, attenuate_power, highlight_power):
        assert highlight_power > 0

        # State
        # 0-1: Must be 0 to display;
        # next bit: highlight
        # next 2 bits: row
        # next 2 bits: column
        # last b
        self.current_led = Counter(4+attenuate_power+highlight_power)
        self._led_attenuate = attenuate_power > 0
        self._aled_bits = slice(0, 2)
        self._kled_bits = slice(2, 4)
        if self._led_attenuate:
            self._led_attenuate_bits = slice(4, 4+attenuate_power)
        self._highlight_bits = slice(4+attenuate_power, 4+attenuate_power+highlight_power) # active 0

        self.may_light = am.Signal(1)

    def elaborate(self, platform):
        m = am.Module()

        m.submodules.current_led = self.current_led

        # Interface
        #button = platform.request("button", 0)
        kleds = [platform.request("kled", i) for i in range(4)]
        aled = platform.request("aled", 0)

        # Logic
        m.d.comb += self.may_light.eq(
            self.current_led.count[self._led_attenuate_bits] == 0
                if self._led_attenuate else am.C(1)
        )

        # Source: https://github.com/dadamachines/doppler-FPGA-firmware/blob/a3d57bb/doppler_simple_io/doppler_simple_io.v#L153-L168
        # Anode looks like (inverted) column select:
        # * 1110 for LEDs 0, 4,  8, 12
        # * 1101 for LEDs 1, 5,  9, 13
        # * 1011 for LEDs 2, 6, 10, 14
        # * 0111 for LEDs 3, 7, 11, 15
        for i in range(4):
            counter_match = self.may_light
            counter_match = counter_match & (self.current_led.count[self._aled_bits] == i)
            m.d.comb += \
                aled.o[i].eq(counter_match)

        # Cathode looks like row select, but to turn off, we put it in high
        # impedance, rather than grounding it:

        m.d.comb += [kled.o.eq(1) for kled in kleds]
        for i in range(4):
            counter_match = self.may_light
            if i != 1:
                counter_match = counter_match & (self.current_led.count[self._highlight_bits] == 0) # Slowest-changing bit(s)
            counter_match = counter_match & (self.current_led.count[self._kled_bits] == i)
            m.d.comb += \
                kleds[i].oe.eq(counter_match)

        # This button isn't debounced, so it'll probably skip a whole lot every time you press it.
#        button_last = am.Signal()
#        m.d.sync += button_last.eq(button.i)
#        with m.If(~button.i & button_last):
#            m.d.sync += selected_led.eq(selected_led + 1)

        return m


if __name__ == "__main__":
    top = Top(2,3)
    plat = DopplerPlatform()
    plat.build(top)
