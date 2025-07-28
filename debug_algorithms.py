#!/usr/bin/env python3
"""
Comprehensive debugging script to identify discrepancies between algorithms
"""

import numpy as np
from sfc_placement_framework import generate_test_instance, SFCPlacementFramework, BaselineAlgorithms
from optimal_solver import OptimalSFCSolver, PULP_AVAILABLE

def debug_single_demand(framework, demand, budget):
    """Debug a single demand placement"""
    print(f"\n=== DEBUGGING DEMAND {demand.id} ===")
    print(f"Path: {demand.path}")
    print(f"SFC: {demand.sfc}")
    print(f"Budget: {budget:.2f}")
    
    # Generate all possible configurations manually
    print("\nAll possible placements:")
    
    # Get associated network
    H, source, sink = framework.build_associated_network(demand)
    print(f"Associated network: {len(H.nodes())} nodes, {len(H.edges())} edges")
    
    # List all valid placements
    valid_placements = []
    
    def enumerate_placements(func_idx, current_path, current_cost, current_throughput, current_delay):
        if func_idx >= len(demand.sfc):
            # Complete placement found
            bottleneck = min(current_throughput) if current_throughput else 0
            total_cost = sum(current_cost)
            total_delay = sum(current_delay)
            
            if total_cost <= budget and bottleneck > 0:
                valid_placements.append({
                    'path': current_path.copy(),
                    'cost': total_cost,
                    'throughput': bottleneck,
                    'delay': total_delay
                })
            return
        
        # Try placing current function on each remaining node
        func_id = demand.sfc[func_idx]
        start_idx = len(current_path)  # Must maintain path order
        
        for node_idx in range(start_idx, len(demand.path)):
            node_id = demand.path[node_idx]
            cost = framework.cost_matrix.get((node_id, func_id), float('inf'))
            throughput = framework.throughput_matrix.get((node_id, func_id), 0)
            delay = framework.delay_matrix.get((node_id, func_id), 0)
            
            if cost != float('inf') and throughput > 0:
                enumerate_placements(
                    func_idx + 1,
                    current_path + [node_id],
                    current_cost + [cost],
                    current_throughput + [throughput],
                    current_delay + [delay]
                )
    
    enumerate_placements(0, [], [], [], [])
    
    print(f"Found {len(valid_placements)} valid placements:")
    for i, placement in enumerate(sorted(valid_placements, key=lambda x: -x['throughput'])):
        print(f"  {i+1}: path={placement['path']}, cost={placement['cost']:.2f}, "
              f"throughput={placement['throughput']:.2f}, delay={placement['delay']:.2f}")
    
    # Now check what each algorithm finds
    print("\nAlgorithm comparisons:")
    
    # CP-pair generation
    configs = framework.generate_cp_pairs_non_delay(demand)
    print(f"CP-pair generation found {len(configs)} configurations:")
    for i, config in enumerate(configs):
        print(f"  Config {i}: cost={config.cost:.2f}, throughput={config.throughput:.2f}")
    
    # Find best manual placement
    if valid_placements:
        best_manual = max(valid_placements, key=lambda x: x['throughput'])
        print(f"Best manual placement: cost={best_manual['cost']:.2f}, throughput={best_manual['throughput']:.2f}")
    else:
        print("No valid manual placements found!")
    
    return valid_placements

def debug_small_instance():
    """Debug with very small instance"""
    print("="*60)
    print("DEBUGGING SMALL INSTANCE")
    print("="*60)
    
    # Create minimal instance: 3 nodes, 2 functions, 2 demands
    network, functions, demands, cost_matrix, throughput_matrix, delay_matrix = \
        generate_test_instance(3, 2, 2, seed=42)
    
    framework = SFCPlacementFramework(network, functions, cost_matrix, 
                                    throughput_matrix, delay_matrix)
    
    budget = sum(cost_matrix.values()) * 0.5  # Generous budget
    
    print(f"Network: {list(network.nodes())}")
    print(f"Functions: {[f.id for f in functions]}")
    print(f"Budget: {budget:.2f} (50% of total {sum(cost_matrix.values()):.2f})")
    
    # Debug each demand individually
    all_manual_placements = []
    for demand in demands:
        placements = debug_single_demand(framework, demand, budget)
        all_manual_placements.extend(placements)
    
    print(f"\n=== ALGORITHM COMPARISON ===")
    
    # Test FPTAS
    selected_fptas, throughput_fptas = framework.solve_non_delay_aware(demands, budget, 0.1)
    print(f"FPTAS: {len(selected_fptas)} demands, {throughput_fptas:.2f} throughput")
    
    # Test Greedy
    baseline = BaselineAlgorithms(framework)
    selected_greedy, throughput_greedy = baseline.greedy_throughput(demands, budget)
    print(f"Greedy: {len(selected_greedy)} demands, {throughput_greedy:.2f} throughput")
    
    # Test Optimal
    if PULP_AVAILABLE:
        optimal_solver = OptimalSFCSolver(framework)
        selected_opt, throughput_opt, opt_info = optimal_solver.solve_optimal_non_delay_aware(demands, budget)
        print(f"Optimal: {len(selected_opt)} demands, {throughput_opt:.2f} throughput")
        print(f"Optimal status: {opt_info['status']}")
    
    # Manual upper bound calculation
    print(f"\n=== MANUAL ANALYSIS ===")
    
    # Calculate theoretical upper bound
    if all_manual_placements:
        # Best possible selection under budget
        all_manual_placements.sort(key=lambda x: -x['throughput'])
        total_cost = 0
        total_throughput = 0
        selected_count = 0
        
        for placement in all_manual_placements:
            if total_cost + placement['cost'] <= budget:
                total_cost += placement['cost']
                total_throughput += placement['throughput']
                selected_count += 1
                print(f"  Can add: cost={placement['cost']:.2f}, throughput={placement['throughput']:.2f}")
        
        print(f"Manual upper bound: {selected_count} demands, {total_throughput:.2f} throughput, {total_cost:.2f} cost")

def debug_mckp_directly():
    """Debug MCKP algorithm directly"""
    print("\n" + "="*60)
    print("DEBUGGING MCKP FPTAS DIRECTLY")
    print("="*60)
    
    from sfc_placement_framework import MCKPItem
    
    # Create simple MCKP instance
    groups = [
        [MCKPItem(profit=10, weight=5, group=0, item_id=0),   # Group 0: two items
         MCKPItem(profit=8, weight=3, group=0, item_id=1)],
        [MCKPItem(profit=15, weight=8, group=1, item_id=0),   # Group 1: two items  
         MCKPItem(profit=12, weight=6, group=1, item_id=1)],
        [MCKPItem(profit=6, weight=2, group=2, item_id=0),    # Group 2: two items
         MCKPItem(profit=9, weight=4, group=2, item_id=1)]
    ]
    
    capacity = 15
    epsilon = 0.1
    
    print("MCKP Instance:")
    for i, group in enumerate(groups):
        print(f"  Group {i}:")
        for item in group:
            ratio = item.profit / item.weight
            print(f"    Item {item.item_id}: profit={item.profit}, weight={item.weight}, ratio={ratio:.3f}")
    
    print(f"Capacity: {capacity}")
    print(f"Epsilon: {epsilon}")
    
    # Solve with FPTAS
    network, functions, demands, cost_matrix, throughput_matrix, delay_matrix = \
        generate_test_instance(3, 2, 1, seed=42)
    framework = SFCPlacementFramework(network, functions, cost_matrix, throughput_matrix, delay_matrix)
    
    profit, solution = framework.mckp_fptas(groups, capacity, epsilon)
    print(f"MCKP FPTAS result: profit={profit}, solution={solution}")
    
    # Manual optimal solution
    print("\nManual enumeration:")
    best_profit = 0
    best_selection = []
    
    # Try all combinations (brute force for verification)
    for i0 in range(len(groups[0])):
        for i1 in range(len(groups[1])):
            for i2 in range(len(groups[2])):
                total_weight = groups[0][i0].weight + groups[1][i1].weight + groups[2][i2].weight
                total_profit = groups[0][i0].profit + groups[1][i1].profit + groups[2][i2].profit
                
                if total_weight <= capacity:
                    print(f"  Selection [{i0},{i1},{i2}]: weight={total_weight}, profit={total_profit}")
                    if total_profit > best_profit:
                        best_profit = total_profit
                        best_selection = [i0, i1, i2]
    
    print(f"Manual optimal: profit={best_profit}, selection={best_selection}")

def main():
    """Run all debugging tests"""
    debug_small_instance()
    debug_mckp_directly()

if __name__ == "__main__":
    main()