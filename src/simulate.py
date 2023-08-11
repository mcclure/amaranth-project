import amaranth as am
from amaranth.sim import Simulator
from counter import Top
from types import SimpleNamespace

# Mock platform
class SimPlatform():
    def __init__(self):
        self.button0 = am.Signal(1)
        self.aled = am.Signal(4)
        self.kled = am.Signal(4)

    def request(self, name, id=None, *_):
        if name=="kled":
            return SimpleNamespace(o=self.kled[id], oe=am.Signal())
        if name=="aled":
            return SimpleNamespace(o=self.aled)
        if name=="button" and id==0:
            return self.button0
        return am.Signal(1)

platform = SimPlatform()
dut = Top(0,1, button_watcher_power=4, debug=True)

def bench():
    for _ in range(64):
        yield
    for i in range(64):
        yield platform.button0.eq(i%2 == 0)
        yield
    for _ in range(128):
        yield

sim = Simulator(am.Fragment.get(dut, platform))
sim.add_clock(1e-6) # 1 MHz
sim.add_sync_process(bench)
with sim.write_vcd("up_counter.vcd", traces=[dut.grid, platform.button0, dut.debug_button_ffwd_watcher_overflow, platform.aled, platform.kled]):
    sim.run()
