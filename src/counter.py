import amaranth as am
from doppler import DopplerPlatform


class Counter(am.Elaboratable):
    def __init__(self, n):
        # Store an n-bit register for the count value
        self.count = am.Signal(n)

        # Output a single-bit output signal
        self.overflow = am.Signal()

    def elaborate(self, platform):
        m = am.Module()
        # Count up each clock cycle
        m.d.sync += self.count.eq(self.count + 1)
        # Output overflow on cycles where the count is 0
        m.d.comb += self.overflow.eq(self.count == 0)
        return m


class Top(am.Elaboratable):
    def elaborate(self, platform):
        m = am.Module()

        button = platform.request("button", 0)
        kled = platform.request("kled", 0)
        aled = platform.request("aled", 0)
        m.submodules.counter = counter = Counter(24)
        m.d.comb += kled.o.eq(0b0000), kled.oe.eq(0b1111)
        m.d.comb += aled.o.eq(0b0000), aled.oe.eq(0b1111)
        with m.If(button.i):
            m.d.comb += aled.o[0].eq(counter.overflow)

        return m


if __name__ == "__main__":
    top = Top()
    plat = DopplerPlatform()
    plat.build(top)
