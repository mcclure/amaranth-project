import amaranth as am
from doppler import DopplerPlatform


class Counter(am.Elaboratable):
    def __init__(self, n, need_overflow=False, single_shot=False, observe=None, observe_reset=0):
        # Store an n-bit register for the count value
        self.count = am.Signal(n)

        # Output a single-bit output signal
        self._has_overflow = need_overflow
        if need_overflow:
            self.overflow = am.Signal()

        # Must reset to 1 to do anything -- use with observe
        self._single_shot = single_shot

        # Observe signal going high
        self.observe = observe
        self._observe_reset = observe_reset

    def elaborate(self, platform):
        m = am.Module()
        # Count up each clock cycle

        single_shot_condition = self.count > 0 if self._single_shot else am.C(1)
        observe_condition = self.observe if self.observe is not None else am.C(0)

        with m.If(observe_condition):
            m.d.sync += self.count.eq(self._observe_reset)
        with m.If(~observe_condition & single_shot_condition): # FIXME elif would be better
            m.d.sync += self.count.eq(self.count + 1)

        # Output overflow on cycles where the count is 0
        if self._has_overflow:
            m.d.comb += self.overflow.eq(self.count == 0)
        return m


class Top(am.Elaboratable):
    def __init__(self, attenuate_power, highlight_power, button_watcher_power=8, debug=False):
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

        self.grid = am.Signal(16)

        # Helpers
        self.may_light = am.Signal(1)
        self.may_scroll = am.Signal(1)

        self._button_watcher_power = button_watcher_power

        self._debug = debug
        if debug:
            self.debug_button_ffwd_watcher_overflow = am.Signal(1)

    # Debounce. .overflow field will be 0 iff button pressed in last 2^8 cycles
    def button_watcher(self, observe):
        return Counter(self._button_watcher_power, True, True, observe, 1)

    def elaborate(self, platform):
        m = am.Module()

        m.submodules.current_led = self.current_led

        # Interface
        button_ffwd = platform.request("button", 0)
        button_ffwd_watcher = self.button_watcher(button_ffwd)
        m.submodules.button_ffwd_watcher = button_ffwd_watcher

        button_step = platform.request("button", 1)
        button_step_watcher = self.button_watcher(button_step)
        m.submodules.button_step_watcher = button_step_watcher

        if self._debug:
            m.d.comb += self.debug_button_ffwd_watcher_overflow.eq(button_ffwd_watcher.overflow)

        kleds = [platform.request("kled", i) for i in range(4)]
        aled = platform.request("aled", 0)

        # Logic
        m.d.comb += self.may_light.eq(
            self.current_led.count[self._led_attenuate_bits] == 0
                if self._led_attenuate else am.C(1)
        )

        m.d.comb += self.may_scroll.eq(
            ~button_ffwd_watcher.overflow | ~button_step_watcher.overflow
        )

        # Source: https://github.com/dadamachines/doppler-FPGA-firmware/blob/a3d57bb/doppler_simple_io/doppler_simple_io.v#L153-L168
        # Anode looks like (inverted) column select:
        # * 1110 for LEDs 0, 4,  8, 12
        # * 1101 for LEDs 1, 5,  9, 13
        # * 1011 for LEDs 2, 6, 10, 14
        # * 0111 for LEDs 3, 7, 11, 15

        row = self.current_led.count[self._aled_bits]
        col = self.current_led.count[self._kled_bits]

        for i in range(4): # Iterate rows
            counter_match = self.may_light
            if i != 3: # Highlight final row
                counter_match = counter_match & (self.current_led.count[self._highlight_bits] == 0) # Slowest-changing bit(s)
            counter_match = counter_match & (row == i)

            grid_match = am.C(0)
            for c in range(4): # Iterate cols
                grid_match = grid_match | ((col == c) & self.grid[i*4 + c])
            counter_match = counter_match & grid_match

            m.d.comb += \
                aled.o[i].eq(~counter_match)

        # Cathode looks like row select, but to turn off, we put it in high
        # impedance, rather than grounding it:

        m.d.comb += [kled.o.eq(1) for kled in kleds]
        for i in range(4): # Iterate columns
            counter_match = self.may_light
            counter_match = counter_match & (col == i)

            grid_match = am.C(0)
            for c in range(4): # Iterate rows
                grid_match = grid_match | ((row == c) & self.grid[c*4 + i])
            counter_match = counter_match & grid_match

            m.d.comb += \
                kleds[i].oe.eq(counter_match)

        with m.If(~button_ffwd_watcher.overflow):
            m.d.sync += \
                self.grid[12:16].eq(self.grid[12:16] + 1)

        with m.If(self.may_scroll):
            m.d.sync += \
                self.grid[0:12].eq(self.grid[4:16])

        # This button isn't debounced, so it'll probably skip a whole lot every time you press it.
#        button_last = am.Signal()
#        m.d.sync += button_last.eq(button.i)
#        with m.If(~button.i & button_last):
#            m.d.sync += selected_led.eq(selected_led + 1)

        return m


if __name__ == "__main__":
    top = Top(0,1)
    plat = DopplerPlatform()
    plat.build(top) # , debug_verilog=True
