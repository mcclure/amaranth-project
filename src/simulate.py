import amaranth as am
from amaranth.sim import Simulator
from counter import Top
from types import SimpleNamespace

def bench():
    for _ in range(256):
        yield

# Mock platform
class Platform():
    def request(self, name, *_):
        if name=="kled":
            return SimpleNamespace(o=am.Signal(), oe=am.Signal())
        if name=="aled":
            return SimpleNamespace(o=am.Signal(4))
        return am.Signal(1)

dut = Top(0,1, platform_override = Platform())

sim = Simulator(dut)
sim.add_clock(1e-6) # 1 MHz
sim.add_sync_process(bench)
with sim.write_vcd("up_counter.vcd"):
    sim.run()

