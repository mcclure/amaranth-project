import amaranth as am
from doppler import DopplerPlatform

SCREEN_TEST = False

class Counter(am.Elaboratable):
    def __init__(self, n, overflow_at_value=None, single_shot=False, observe_reset_value=None):
        # Store an n-bit register for the count value
        self.count = am.Signal(n)

        # Output a single-bit output signal
        self._overflow_at_value = overflow_at_value
        if overflow_at_value is not None:
            self.overflow = am.Signal()

        # Must reset to 1 to do anything -- use with observe
        self._single_shot = single_shot

        # Observe signal going high
        self._observe_reset_value = observe_reset_value
        if observe_reset_value is not None:
            self.observe_input = am.Signal()

    def elaborate(self, platform):
        m = am.Module()
        # Count up each clock cycle

        should_observe = self._observe_reset_value is not None

        single_shot_condition = self.count > 0 if self._single_shot else am.C(1) # FIXME use overflow_at_value?
        observe_condition = self.observe_input if should_observe else am.C(0)

        if should_observe:
            with m.If(observe_condition):
                m.d.sync += self.count.eq(self._observe_reset_value)
        with m.If(~observe_condition & single_shot_condition): # FIXME way to use Elif here? (Once Yosys bug is fixed)
            m.d.sync += self.count.eq(self.count + 1)

        # Output overflow on cycles where the count is 0
        if self._overflow_at_value is not None:
            m.d.comb += self.overflow.eq(self.count == self._overflow_at_value)
        return m

class Edger(am.Elaboratable):
    def __init__(self): # FIXME variable for initial fire?
        # Will output high when this hits rising edge
        self.observe_input = am.Signal()
        self.last_value = am.Signal()
        self.fire = am.Signal()

    def elaborate(self, platform):
        m = am.Module()
        m.d.sync += self.last_value.eq(self.observe_input)
        m.d.comb += self.fire.eq(self.observe_input & (~self.last_value))

        return m

class Top(am.Elaboratable):
    def __init__(self, led_hold_power=0, led_full_intensity=None, led_dim_intensity=None, button_watcher_power=5, ffwd_animate_power=21, debug=False):
        # State
        # button_watcher_power bits of delay
        # next 2 bits: row
        # next 2 bits: column
        # Start
        bit = 0
        
        field = led_hold_power
        self._led_hold_bits = slice(bit, bit+field) if field > 0 else None
        bit += field

        field = 2
        self._aled_bits = slice(bit, bit+field)
        bit += field

        self._kled_bits = slice(bit, bit+field)
        bit += field

        self.current_led = Counter(bit)
        # End
        
        self._led_full_intensity = led_full_intensity # No full => always full
        self._led_dim_intensity = led_dim_intensity or led_full_intensity # No dim => follow full behavior

        self.grid = am.Signal(16)

        # Helpers
        self.may_light_full = am.Signal()
        self.may_light_dim = am.Signal()
        self.may_light_current = am.Signal()

        self.may_scroll = am.Signal() # Only used if not SCREEN_TEST 

        self._button_watcher_power = button_watcher_power

        self.row = am.Signal(2)
        self.col = am.Signal(2)

        # Objects
        self.button_ffwd_watcher = self.button_watcher()
        self.button_step_watcher = self.button_watcher()

         # Only used if not SCREEN_TEST 
        self.button_step_edge = Edger()
        self.button_ffwd_down = Counter(ffwd_animate_power, overflow_at_value=1, observe_reset_value=0)

        self._debug = debug

    # Debounce. .overflow field will be 0 iff button pressed in last 2^8 cycles
    def button_watcher(self):
        return Counter(self._button_watcher_power,
            overflow_at_value=0, single_shot=True, observe_reset_value=1)

    def elaborate(self, platform):
        m = am.Module()

        m.submodules.current_led = self.current_led

        # Interface
        button_step = platform.request("button", 0) # Right
        m.d.comb += self.button_step_watcher.observe_input.eq(button_step)
        m.submodules.button_step_watcher = self.button_step_watcher

        button_ffwd = platform.request("button", 1) #Left
        m.d.comb += self.button_ffwd_watcher.observe_input.eq(button_ffwd)
        m.submodules.button_ffwd_watcher = self.button_ffwd_watcher

        kleds = [platform.request("kled", i) for i in range(4)]
        aled = platform.request("aled", 0)

        # Logic
        m.d.comb += [
            self.row.eq(self.current_led.count[self._aled_bits]),
            self.col.eq(self.current_led.count[self._kled_bits])
        ]

        any_hold = self._led_hold_bits is not None
        any_intensity_full = any_hold and self._led_full_intensity is not None
        any_intensity_dim = any_hold and self._led_dim_intensity is not None
        m.d.comb += [
            self.may_light_full.eq(
                self.current_led.count[self._led_hold_bits] < self._led_full_intensity
                    if any_intensity_full
                    else am.C(1)
            ),

            self.may_light_dim.eq(
                self.current_led.count[self._led_hold_bits] < self._led_dim_intensity
                    if any_intensity_dim
                    else am.C(1)
            ),

            self.may_light_current.eq(
                am.Mux(self.row == 3, self.may_light_full, self.may_light_dim)
                    if any_intensity_full or any_intensity_dim
                    else am.C(1)
            )
        ]

        # LED operation
        # Source: https://github.com/dadamachines/doppler-FPGA-firmware/blob/a3d57bb/doppler_simple_io/doppler_simple_io.v#L153-L168
        # Anode looks like (inverted) column select:
        # * 1110 for LEDs 0, 4,  8, 12
        # * 1101 for LEDs 1, 5,  9, 13
        # * 1011 for LEDs 2, 6, 10, 14
        # * 0111 for LEDs 3, 7, 11, 15

        for i in range(4): # Iterate rows
            counter_match = self.may_light_current

            counter_match = counter_match & (self.row == i)

            grid_match = am.C(0)
            for c in range(4): # Iterate cols
                grid_match = grid_match | ((self.col == c) & self.grid[i*4 + c])
            counter_match = counter_match & grid_match

            m.d.comb += \
                aled.o[i].eq(~counter_match)

        # Cathode looks like row select, but to turn off, we put it in high
        # impedance, rather than grounding it:

        m.d.comb += [kled.o.eq(1) for kled in kleds]
        for i in range(4): # Iterate columns
            counter_match = self.may_light_current

            counter_match = counter_match & (self.col == i)

            grid_match = am.C(0)
            for c in range(4): # Iterate rows
                grid_match = grid_match | ((self.row == c) & self.grid[c*4 + i])
            counter_match = counter_match & grid_match

            m.d.comb += \
                kleds[i].oe.eq(counter_match)

        if not SCREEN_TEST:
            m.submodules.button_step_edge = self.button_step_edge
            m.submodules.button_ffwd_down = self.button_ffwd_down

            m.d.comb += [
                self.button_step_edge.observe_input.eq(~self.button_step_watcher.overflow),
                self.button_ffwd_down.observe_input.eq(self.button_ffwd_watcher.overflow),

                self.may_scroll.eq(
                    self.button_step_edge.fire | self.button_ffwd_down.overflow
                )
            ]

            # FIXME: Maybe don't update grid except at refresh edge?
            with m.If(self.may_scroll):
                m.d.sync += \
                    self.grid[12:16].eq(self.grid[12:16] + 1)

                m.d.sync += \
                    self.grid[0:12].eq(self.grid[4:16])
        else: # SCREEN_TEST
            m.d.comb += \
                self.grid.eq(am.C(0b1010010100111100, shape=am.unsigned(16)))

        # This button isn't debounced, so it'll probably skip a whole lot every time you press it.
#        button_last = am.Signal()
#        m.d.sync += button_last.eq(button.i)
#        with m.If(~button.i & button_last):
#            m.d.sync += selected_led.eq(selected_led + 1)

        return m


if __name__ == "__main__":
    top = Top(5, led_full_intensity=24, led_dim_intensity=4)
    plat = DopplerPlatform()
    plat.build(top) # , debug_verilog=True
