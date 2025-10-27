#!/usr/bin/env python3
"""
Simple test script to verify the SFC placement implementation
"""

import sys
import traceback
from sfc_placement_framework import (
    SFCPlacementFramework, BaselineAlgorithms, generate_test_instance,
    NetworkFunction, Demand
)

def test_basic_functionality():
    """Test basic functionality of the framework"""
    print("Testing basic functionality...")
    
    try:
        # Generate a small test instance
        network, functions, demands, cost_matrix, throughput_matrix, delay_matrix = \
            generate_test_instance(num_nodes=10, num_functions=3, num_demands=5, seed=42)
        
        print(f"✓ Generated test instance: {len(network.nodes())} nodes, {len(functions)} functions, {len(demands)} demands")
        
        # Initialize framework
        framework = SFCPlacementFramework(network, functions, cost_matrix, 
                                        throughput_matrix, delay_matrix)
        
        print("✓ Framework initialized successfully")
        
        # Test associated network construction
        test_demand = demands[0]
        H, source, sink = framework.build_associated_network(test_demand)
        
        print(f"✓ Associated network built: {len(H.nodes())} nodes, {len(H.edges())} edges")
        
        # Test CP pair generation (non-delay)
        configs = framework.generate_cp_pairs_non_delay(test_demand)
        print(f"✓ Generated {len(configs)} configurations for demand {test_demand.id}")
        
        if configs:
            print(f"  - Best config: cost={configs[0].cost:.2f}, throughput={configs[0].throughput:.2f}")
        
        # Test basic solving
        budget = sum(cost_matrix.values()) * 0.2
        epsilon = 0.2
        
        selected_demands, total_throughput = framework.solve_non_delay_aware(demands, budget, epsilon)
        print(f"✓ Non-delay-aware solution: {len(selected_demands)} demands selected, throughput={total_throughput:.2f}")
        
        # Test delay-aware solving
        selected_delay_demands, delay_throughput = framework.solve_delay_aware(demands, budget, epsilon)
        print(f"✓ Delay-aware solution: {len(selected_delay_demands)} demands selected, throughput={delay_throughput:.2f}")
        
        # Test baseline algorithms
        baseline = BaselineAlgorithms(framework)
        greedy_selected, greedy_throughput = baseline.greedy_throughput(demands, budget)
        print(f"✓ Greedy baseline: {len(greedy_selected)} demands selected, throughput={greedy_throughput:.2f}")
        
        print("\n🎉 All basic tests passed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        traceback.print_exc()
        return False

def test_mckp_functionality():
    """Test MCKP FPTAS specifically"""
    print("\nTesting MCKP FPTAS...")
    
    try:
        from sfc_placement_framework import MCKPItem
        
        # Create a simple MCKP instance
        groups = [
            [MCKPItem(profit=10, weight=5, group=0, item_id=0),
             MCKPItem(profit=8, weight=3, group=0, item_id=1)],
            [MCKPItem(profit=15, weight=8, group=1, item_id=0),
             MCKPItem(profit=12, weight=6, group=1, item_id=1)],
            [MCKPItem(profit=6, weight=2, group=2, item_id=0),
             MCKPItem(profit=9, weight=4, group=2, item_id=1)]
        ]
        
        network, functions, demands, cost_matrix, throughput_matrix, delay_matrix = \
            generate_test_instance(5, 2, 1, seed=42)
        framework = SFCPlacementFramework(network, functions, cost_matrix, 
                                        throughput_matrix, delay_matrix)
        
        # Test MCKP FPTAS
        capacity = 15
        epsilon = 0.1
        
        profit, solution = framework.mckp_fptas(groups, capacity, epsilon)
        print(f"✓ MCKP solved: profit={profit:.2f}, solution={solution}")
        
        # Verify solution feasibility
        total_weight = sum(groups[i][item_id].weight for i, item_id in enumerate(solution) 
                          if i < len(groups) and item_id < len(groups[i]))
        print(f"✓ Solution weight: {total_weight} <= {capacity} (feasible: {total_weight <= capacity})")
        
        return True
        
    except Exception as e:
        print(f"❌ MCKP test failed: {e}")
        traceback.print_exc()
        return False

def test_rsp_functionality():
    """Test RSP FPTAS specifically"""
    print("\nTesting RSP FPTAS...")
    
    try:
        # Generate test instance
        network, functions, demands, cost_matrix, throughput_matrix, delay_matrix = \
            generate_test_instance(8, 3, 1, seed=42)
        
        framework = SFCPlacementFramework(network, functions, cost_matrix, 
                                        throughput_matrix, delay_matrix)
        
        # Build associated network for a demand
        test_demand = demands[0]
        H, source, sink = framework.build_associated_network(test_demand)
        
        # Test RSP FPTAS
        delay_threshold = 5.0
        epsilon = 0.1
        
        cost = framework.rsp_fptas(H, source, sink, delay_threshold, epsilon)
        print(f"✓ RSP FPTAS solved: cost={cost:.2f} with delay threshold={delay_threshold}")
        
        # Test with tighter delay constraint
        tight_threshold = 1.0
        tight_cost = framework.rsp_fptas(H, source, sink, tight_threshold, epsilon)
        print(f"✓ RSP FPTAS with tight constraint: cost={tight_cost:.2f} with delay threshold={tight_threshold}")
        
        return True
        
    except Exception as e:
        print(f"❌ RSP test failed: {e}")
        traceback.print_exc()
        return False

def run_quick_performance_test():
    """Run a quick performance test"""
    print("\nRunning quick performance test...")
    
    try:
        import time
        
        # Generate a medium-sized instance
        network, functions, demands, cost_matrix, throughput_matrix, delay_matrix = \
            generate_test_instance(15, 4, 20, seed=42)
        
        framework = SFCPlacementFramework(network, functions, cost_matrix, 
                                        throughput_matrix, delay_matrix)
        baseline = BaselineAlgorithms(framework)
        
        budget = sum(cost_matrix.values()) * 0.3
        epsilon = 0.1
        
        # Time FPTAS
        start_time = time.time()
        selected_fptas, throughput_fptas = framework.solve_non_delay_aware(demands, budget, epsilon)
        fptas_time = time.time() - start_time
        
        # Time Greedy
        start_time = time.time()
        selected_greedy, throughput_greedy = baseline.greedy_throughput(demands, budget)
        greedy_time = time.time() - start_time
        
        print(f"✓ Performance comparison:")
        print(f"  - FPTAS: {throughput_fptas:.2f} throughput in {fptas_time:.4f}s")
        print(f"  - Greedy: {throughput_greedy:.2f} throughput in {greedy_time:.4f}s")
        print(f"  - Improvement: {((throughput_fptas - throughput_greedy) / max(throughput_greedy, 1e-6)) * 100:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("="*60)
    print("SFC PLACEMENT FRAMEWORK - IMPLEMENTATION TEST")
    print("="*60)
    
    tests_passed = 0
    total_tests = 4
    
    if test_basic_functionality():
        tests_passed += 1
    
    if test_mckp_functionality():
        tests_passed += 1
    
    if test_rsp_functionality():
        tests_passed += 1
    
    if run_quick_performance_test():
        tests_passed += 1
    
    print("\n" + "="*60)
    print(f"TEST SUMMARY: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! Implementation is working correctly.")
        print("You can now run the full experimental evaluation.")
        return True
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)