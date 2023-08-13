import amaranth as am
from amaranth.sim import Simulator
from counter import Top
from types import SimpleNamespace

hold_power = 0 # Instead of None use 0
hold_factor = 1 << hold_power

# Mock platform
class SimPlatform():
    def __init__(self):
        self.button0 = am.Signal()
        self.button1 = am.Signal()
        self.button = [self.button0, self.button1]
        self.aled = am.Signal(4)
        self.kled = am.Signal(4)

    def request(self, name, id=None, *_):
        if name=="kled":
            return SimpleNamespace(oe=self.kled[id], o=am.Signal())
        if name=="aled":
            return SimpleNamespace(o=self.aled)
        if name=="button":
            return self.button[id]
        if name=="mcu":
            return am.Signal(4)
        return am.Signal(1)

platform = SimPlatform()
dut = Top(hold_power, button_watcher_power=4, ffwd_animate_power=5, debug=True)

def bench():
    for _ in range(64*hold_factor):
        yield
    for r in range(4):
        downtime = ((r+1)*4)
        watchtime = 64*hold_factor
        for i in range(downtime):
            yield platform.button[0].eq(i%2 == 0)
            yield
        for _ in range(watchtime-downtime):
            yield
    for r in range(1):
        downtime = 64*hold_factor
        for i in range(downtime):
            yield platform.button[1].eq(i%2 == 0)
            yield
    for _ in range(128*hold_factor):
        yield

sim = Simulator(am.Fragment.get(dut, platform))
sim.add_clock(1e-6) # 1 MHz
sim.add_sync_process(bench)
with sim.write_vcd("up_counter.vcd", traces=[dut.grid, platform.button[0], platform.button[1], dut.button_step_edge.fire, dut.button_ffwd_down.overflow, dut.may_scroll, platform.aled, platform.kled]):
    sim.run()
