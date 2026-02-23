"""
FIRE-C2 Validation Test Script

This script runs a quick validation test with a smaller grid to verify:
- C2 backdoor activation logic
- Fire propagation dynamics
- Network communication channels
- Data collection pipeline

Used for pre-flight checks before full dataset generation.

Copyright (c) 2025 FIRE-C2 Research Team
"""

from ns import ns
import cppyy
import random
import numpy as np
from FireAlarmSimulation import FireAlarmSimulation
from Config import Config

def setup_cppyy_callbacks():
    """
    Setup C++ callback trampolines for ns-3 Python bindings.

    Identical to main.py setup - required for validation test to run
    independently.
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

def validate_simulation():
    """
    Run validation test with reduced grid size for faster execution.

    Test configuration:
    - 4x5 grid (20 nodes instead of 80)
    - 60-second simulation time
    - 3 attacker nodes
    - Fire node at ID 7

    Returns:
        True if validation passed (at least 1 attacker activated)
        False otherwise
    """
    print("🧪 RUNNING VALIDATION TEST")

    Config.N_ROWS, Config.N_COLS = 4, 5
    Config.N_NODES = Config.N_ROWS * Config.N_COLS
    Config.STOP_TIME = 60.0
    Config.ATTACKER_IDS = [3, 8, 12]
    Config.FIRE_NODE_ID = 7

    test_seed = 42
    ns.RngSeedManager.SetSeed(test_seed)
    ns.RngSeedManager.SetRun(0)
    random.seed(test_seed)
    np.random.seed(test_seed)

    sim = FireAlarmSimulation()
    sim.run_id = "validation_test"

    try:
        sim.run()

        activated_attackers = sum(1 for node in sim.nodes
                                if node.is_attacker and node.attack_triggered)
        total_attackers = sum(1 for node in sim.nodes if node.is_attacker)

        print(f"✅ Validation Results:")
        print(f"   Attackers configured: {total_attackers}")
        print(f"   Attackers activated: {activated_attackers}")
        print(f"   C2 active: {sim.c2_active}")

        return activated_attackers > 0

    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False

if __name__ == "__main__":
    setup_cppyy_callbacks()

    success = validate_simulation()
    if success:
        print("🎉 VALIDATION PASSED - Ready for dataset generation!")
    else:
        print("🚨 VALIDATION FAILED - Check configuration")
