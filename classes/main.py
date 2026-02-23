"""
FIRE-C2: Fire-Triggered C2 Backdoor Simulation Framework

This is the main entry point for running FIRE-C2 simulations. It provides:
- Command-line argument parsing for simulation parameters
- C++ callback setup for ns-3 Python bindings
- RNG seeding for reproducibility
- Simulation orchestration and cleanup

Usage:
    python main.py [OPTIONS]

Options:
    --stop SECONDS    Simulation duration (default: from Config.STOP_TIME)
    --rows INT        Grid rows (default: from Config.N_ROWS)
    --cols INT        Grid columns (default: from Config.N_COLS)
    --seed INT        RNG seed (default: 12345)
    --run INT         RNG run number (default: 0)
    --output DIR      Output directory (default: from Config.DATA_OUTPUT_DIR)
    --c2 {0,1}        Enable C2 backdoor: 1=enabled, 0=benign-only (default: from Config)
"""

from ns import ns
import random
import numpy as np
import cppyy
from FireAlarmSimulation import FireAlarmSimulation
from Config import Config
import argparse, time
import sys

def parse_args():
    """
    Parse command-line arguments for simulation configuration.

    Returns:
        Namespace object with parsed arguments
    """
    p = argparse.ArgumentParser()
    p.add_argument("--stop", type=float, default=Config.STOP_TIME, help="NS-3 sim time (s)")
    p.add_argument("--rows", type=int, default=Config.N_ROWS)
    p.add_argument("--cols", type=int, default=Config.N_COLS)
    p.add_argument("--seed", type=int, default=12345)
    p.add_argument("--run",  type=int, default=0)
    p.add_argument("--output", type=str, default=Config.DATA_OUTPUT_DIR)
    p.add_argument("--c2", type=int, choices=[0,1], default=int(Config.C2_ENABLED),
                   help="1=enable C2 backdoor, 0=benign-only")
    return p.parse_args()

def setup_cppyy_callbacks():
    """
    Setup C++ callback trampolines for ns-3 Python bindings.

    This function defines C++ helper functions that enable Python callbacks
    to be invoked from ns-3 C++ code. Required for:
    - Event scheduling (pythonMakeEvent)
    - Socket receive callbacks (PythonRecvTrampoline)
    - C2 socket callbacks (PythonRecvTrampolineC2)

    Uses shared_ptr for automatic memory management to prevent leaks.
    """
    import os
    ns3_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
    cppyy.add_include_path(os.path.join(ns3_root, "build/include"))

    ns.cppyy.cppdef(r"""
    #include "ns3/event-id.h"
    #include "ns3/make-event.h"
    #include "ns3/ptr.h"
    #include "ns3/socket.h"
    #include <vector>
    #include <functional>
    #include <memory>
    using namespace ns3;

    static std::vector<std::shared_ptr<std::function<void()>>> _py_store;

    EventImpl* pythonMakeEvent(std::function<void()> f) {
        auto func_ptr = std::make_shared<std::function<void()>>(std::move(f));
        _py_store.push_back(func_ptr);
        return MakeEvent(*func_ptr);
    }

    static std::function<void(Ptr<Socket>)> _py_recv;
    static std::function<void(Ptr<Socket>)> _py_recv_c2;

    void PythonRecvTrampoline(Ptr<Socket> s) {
        if (_py_recv) _py_recv(s);
    }

    void PythonRecvTrampolineC2(Ptr<Socket> s) {
        if (_py_recv_c2) _py_recv_c2(s);
    }

    void ClearPythonCallbacks() {
        _py_store.clear();
        _py_recv = nullptr;
        _py_recv_c2 = nullptr;
    }
    """)

def run_simulation():
    """
    Execute a single FIRE-C2 simulation run with configured parameters.

    This function:
    1. Parses command-line arguments
    2. Applies configuration overrides
    3. Seeds all RNGs (ns-3, Python random, numpy) for reproducibility
    4. Creates and runs the simulation
    5. Performs cleanup on success or failure
    """
    args = parse_args()

    Config.STOP_TIME = float(args.stop)
    Config.N_ROWS, Config.N_COLS = args.rows, args.cols
    Config.DATA_OUTPUT_DIR = args.output
    Config.C2_ENABLED = bool(args.c2)

    print(f"🔧 Configuration: C2_ENABLED={Config.C2_ENABLED}, ATTACKER_IDS={getattr(Config, 'ATTACKER_IDS', [])}")

    ns.RngSeedManager.SetSeed(args.seed)
    ns.RngSeedManager.SetRun(args.run)

    random.seed(args.seed)
    np.random.seed(args.seed)

    print("Starting Fire Alarm Simulation with Data Collection...")

    try:
        sim = FireAlarmSimulation()

        sim.run_id = f"{time.strftime('%Y%m%d_%H%M%S')}_seed{args.seed}_run{args.run}_c2{int(Config.C2_ENABLED)}"

        sim.run()
        print("✅ Simulation completed successfully")

        if hasattr(sim, 'cleanup'):
            sim.cleanup()

    except Exception as e:
        print(f"❌ Simulation failed: {e}")
        import traceback
        traceback.print_exc()

        try:
            if hasattr(ns.cppyy.gbl, 'ClearPythonCallbacks'):
                ns.cppyy.gbl.ClearPythonCallbacks()

            ns.Simulator.Destroy()
        except:
            pass
        raise

if __name__ == "__main__":
    setup_cppyy_callbacks()
    run_simulation()
