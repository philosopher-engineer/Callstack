#!/usr/bin/env python3
"""
Optimal ILP solver for SFC placement problems using PuLP
Provides exact solutions for comparison with FPTAS algorithms
"""

try:
    import pulp
    PULP_AVAILABLE = True
except ImportError:
    PULP_AVAILABLE = False
    print("PuLP not available. Install with: pip install pulp")

import numpy as np
from typing import List, Tuple, Dict, Optional
from sfc_placement_framework import SFCPlacementFramework, Demand, NetworkFunction

class OptimalSFCSolver:
    """
    Optimal solver for SFC placement using Integer Linear Programming
    Provides exact solutions for small instances
    """
    
    def __init__(self, framework: SFCPlacementFramework):
        if not PULP_AVAILABLE:
            raise ImportError("PuLP is required for optimal solver. Install with: pip install pulp")
        
        self.framework = framework
        self.network = framework.network
        self.functions = framework.functions
        self.cost_matrix = framework.cost_matrix
        self.throughput_matrix = framework.throughput_matrix
        self.delay_matrix = framework.delay_matrix
    
    def solve_optimal_non_delay_aware(self, demands: List[Demand], budget: float, 
                                    time_limit: int = 300) -> Tuple[List[Demand], float, Dict]:
        """
        Solve the non-delay-aware SFC placement problem optimally using ILP
        
        Returns:
            selected_demands: List of selected demands
            total_throughput: Total achieved throughput  
            solution_info: Dictionary with solver details
        """
        print(f"Solving optimal non-delay-aware SFC placement for {len(demands)} demands...")
        
        # Create the optimization problem
        prob = pulp.LpProblem("SFC_Placement_Non_Delay", pulp.LpMaximize)
        
        # Decision variables
        # x[d][v][f] = 1 if function f of demand d is placed on node v
        x = {}
        # y[d] = 1 if demand d is satisfied
        y = {}
        
        # Create variables
        for d_idx, demand in enumerate(demands):
            y[d_idx] = pulp.LpVariable(f"y_{d_idx}", cat='Binary')
            x[d_idx] = {}
            
            for v_idx, node_id in enumerate(demand.path):
                x[d_idx][v_idx] = {}
                for f_idx, func_id in enumerate(demand.sfc):
                    var_name = f"x_{d_idx}_{v_idx}_{f_idx}"
                    x[d_idx][v_idx][f_idx] = pulp.LpVariable(var_name, cat='Binary')
        
        # Auxiliary variables for bottleneck throughput
        throughput_vars = {}
        for d_idx, demand in enumerate(demands):
            throughput_vars[d_idx] = pulp.LpVariable(f"throughput_{d_idx}", lowBound=0)
        
        # Objective: maximize total throughput
        prob += pulp.lpSum([throughput_vars[d_idx] for d_idx in range(len(demands))])
        
        # Constraints
        for d_idx, demand in enumerate(demands):
            # Constraint 1: Each function must be placed exactly once if demand is satisfied
            for f_idx, func_id in enumerate(demand.sfc):
                prob += (pulp.lpSum([x[d_idx][v_idx][f_idx] 
                                   for v_idx in range(len(demand.path))]) == y[d_idx])
            
            # Constraint 2: Path ordering (function j+1 must be placed at same or later position)
            for f_idx in range(len(demand.sfc) - 1):
                for v_idx in range(len(demand.path)):
                    # If function f_idx is placed at position v_idx,
                    # then function f_idx+1 can only be placed at positions >= v_idx
                    prob += (pulp.lpSum([x[d_idx][u_idx][f_idx + 1] 
                                       for u_idx in range(v_idx)]) <= 
                           1 - x[d_idx][v_idx][f_idx])
            
            # Constraint 3: Bottleneck throughput calculation
            # throughput_vars[d_idx] <= min over all functions of their throughput
            for f_idx, func_id in enumerate(demand.sfc):
                for v_idx, node_id in enumerate(demand.path):
                    node_throughput = self.throughput_matrix.get((node_id, func_id), 0)
                    if node_throughput > 0:
                        # If function is placed on this node, throughput is bounded by node capacity
                        prob += (throughput_vars[d_idx] <= 
                               node_throughput + (1 - x[d_idx][v_idx][f_idx]) * 1000)
        
        # Constraint 4: Budget constraint
        total_cost = []
        for d_idx, demand in enumerate(demands):
            for f_idx, func_id in enumerate(demand.sfc):
                for v_idx, node_id in enumerate(demand.path):
                    node_cost = self.cost_matrix.get((node_id, func_id), float('inf'))
                    if node_cost != float('inf'):
                        total_cost.append(node_cost * x[d_idx][v_idx][f_idx])
        
        if total_cost:
            prob += pulp.lpSum(total_cost) <= budget
        
        # Solve the problem
        print("Solving ILP...")
        solver = pulp.PULP_CBC_CMD(msg=1, timeLimit=time_limit)
        prob.solve(solver)
        
        # Extract solution
        solution_info = {
            'status': pulp.LpStatus[prob.status],
            'objective_value': pulp.value(prob.objective),
            'solve_time': None,  # PuLP doesn't provide solve time directly
            'num_variables': len(prob.variables()),
            'num_constraints': len(prob.constraints)
        }
        
        selected_demands = []
        total_throughput = 0
        
        if prob.status == pulp.LpStatusOptimal:
            for d_idx, demand in enumerate(demands):
                if y[d_idx].varValue and y[d_idx].varValue > 0.5:
                    selected_demands.append(demand)
                    if throughput_vars[d_idx].varValue:
                        total_throughput += throughput_vars[d_idx].varValue
            
            # PuLP reports negative objective for maximization, so take absolute value
            if solution_info['objective_value']:
                total_throughput = abs(solution_info['objective_value'])
            
            print(f"Optimal solution found!")
            print(f"Selected demands: {len(selected_demands)}")
            print(f"Total throughput: {total_throughput:.2f}")
        else:
            print(f"Solver status: {solution_info['status']}")
        
        return selected_demands, total_throughput, solution_info
    
    def solve_optimal_delay_aware(self, demands: List[Demand], budget: float,
                                time_limit: int = 300) -> Tuple[List[Demand], float, Dict]:
        """
        Solve the delay-aware SFC placement problem optimally using ILP
        """
        print(f"Solving optimal delay-aware SFC placement for {len(demands)} demands...")
        
        # Create the optimization problem
        prob = pulp.LpProblem("SFC_Placement_Delay_Aware", pulp.LpMaximize)
        
        # Decision variables (same structure as non-delay-aware)
        x = {}
        y = {}
        throughput_vars = {}
        
        # Create variables
        for d_idx, demand in enumerate(demands):
            y[d_idx] = pulp.LpVariable(f"y_{d_idx}", cat='Binary')
            throughput_vars[d_idx] = pulp.LpVariable(f"throughput_{d_idx}", lowBound=0)
            x[d_idx] = {}
            
            for v_idx, node_id in enumerate(demand.path):
                x[d_idx][v_idx] = {}
                for f_idx, func_id in enumerate(demand.sfc):
                    var_name = f"x_{d_idx}_{v_idx}_{f_idx}"
                    x[d_idx][v_idx][f_idx] = pulp.LpVariable(var_name, cat='Binary')
        
        # Objective: maximize total throughput
        prob += pulp.lpSum([throughput_vars[d_idx] for d_idx in range(len(demands))])
        
        # Add all constraints from non-delay-aware version
        for d_idx, demand in enumerate(demands):
            # Function placement constraints
            for f_idx, func_id in enumerate(demand.sfc):
                prob += (pulp.lpSum([x[d_idx][v_idx][f_idx] 
                                   for v_idx in range(len(demand.path))]) == y[d_idx])
            
            # Path ordering constraints
            for f_idx in range(len(demand.sfc) - 1):
                for v_idx in range(len(demand.path)):
                    prob += (pulp.lpSum([x[d_idx][u_idx][f_idx + 1] 
                                       for u_idx in range(v_idx)]) <= 
                           1 - x[d_idx][v_idx][f_idx])
            
            # Bottleneck throughput constraints
            for f_idx, func_id in enumerate(demand.sfc):
                for v_idx, node_id in enumerate(demand.path):
                    node_throughput = self.throughput_matrix.get((node_id, func_id), 0)
                    if node_throughput > 0:
                        prob += (throughput_vars[d_idx] <= 
                               node_throughput + (1 - x[d_idx][v_idx][f_idx]) * 1000)
            
            # Delay constraint (NEW)
            if demand.delay_threshold is not None:
                total_delay = []
                for f_idx, func_id in enumerate(demand.sfc):
                    for v_idx, node_id in enumerate(demand.path):
                        node_delay = self.delay_matrix.get((node_id, func_id), 0)
                        total_delay.append(node_delay * x[d_idx][v_idx][f_idx])
                
                if total_delay:
                    prob += (pulp.lpSum(total_delay) <= 
                           demand.delay_threshold + (1 - y[d_idx]) * 1000)
        
        # Budget constraint
        total_cost = []
        for d_idx, demand in enumerate(demands):
            for f_idx, func_id in enumerate(demand.sfc):
                for v_idx, node_id in enumerate(demand.path):
                    node_cost = self.cost_matrix.get((node_id, func_id), float('inf'))
                    if node_cost != float('inf'):
                        total_cost.append(node_cost * x[d_idx][v_idx][f_idx])
        
        if total_cost:
            prob += pulp.lpSum(total_cost) <= budget
        
        # Solve
        print("Solving delay-aware ILP...")
        solver = pulp.PULP_CBC_CMD(msg=1, timeLimit=time_limit)
        prob.solve(solver)
        
        # Extract solution
        solution_info = {
            'status': pulp.LpStatus[prob.status],
            'objective_value': pulp.value(prob.objective),
            'solve_time': None,
            'num_variables': len(prob.variables()),
            'num_constraints': len(prob.constraints)
        }
        
        selected_demands = []
        total_throughput = 0
        
        if prob.status == pulp.LpStatusOptimal:
            for d_idx, demand in enumerate(demands):
                if y[d_idx].varValue and y[d_idx].varValue > 0.5:
                    selected_demands.append(demand)
                    if throughput_vars[d_idx].varValue:
                        total_throughput += throughput_vars[d_idx].varValue
            
            # PuLP reports negative objective for maximization, so take absolute value
            if solution_info['objective_value']:
                total_throughput = abs(solution_info['objective_value'])
            
            print(f"Optimal delay-aware solution found!")
            print(f"Selected demands: {len(selected_demands)}")
            print(f"Total throughput: {total_throughput:.2f}")
        else:
            print(f"Solver status: {solution_info['status']}")
        
        return selected_demands, total_throughput, solution_info


def compare_algorithms_with_optimal(framework: SFCPlacementFramework, 
                                  demands: List[Demand], budget: float, 
                                  epsilon: float = 0.1) -> Dict:
    """
    Compare FPTAS, Greedy, and Optimal algorithms
    """
    from sfc_placement_framework import BaselineAlgorithms
    import time
    
    print("=" * 60)
    print("COMPREHENSIVE ALGORITHM COMPARISON")
    print("=" * 60)
    
    results = {}
    
    # 1. Optimal Solution
    if PULP_AVAILABLE and len(demands) <= 10:  # Only for small instances
        optimal_solver = OptimalSFCSolver(framework)
        
        start_time = time.time()
        opt_selected, opt_throughput, opt_info = optimal_solver.solve_optimal_non_delay_aware(
            demands, budget, time_limit=300)
        opt_time = time.time() - start_time
        
        results['optimal'] = {
            'selected_demands': len(opt_selected),
            'total_throughput': opt_throughput,
            'runtime': opt_time,
            'status': opt_info['status']
        }
    else:
        results['optimal'] = None
        print("Skipping optimal solution (too many demands or PuLP not available)")
    
    # 2. FPTAS Solution
    start_time = time.time()
    fptas_selected, fptas_throughput = framework.solve_non_delay_aware(demands, budget, epsilon)
    fptas_time = time.time() - start_time
    
    results['fptas'] = {
        'selected_demands': len(fptas_selected),
        'total_throughput': fptas_throughput,
        'runtime': fptas_time,
        'epsilon': epsilon
    }
    
    # 3. Greedy Solution
    baseline = BaselineAlgorithms(framework)
    start_time = time.time()
    greedy_selected, greedy_throughput = baseline.greedy_throughput(demands, budget)
    greedy_time = time.time() - start_time
    
    results['greedy'] = {
        'selected_demands': len(greedy_selected),
        'total_throughput': greedy_throughput,
        'runtime': greedy_time
    }
    
    # 4. Analysis
    print(f"\nRESULTS SUMMARY:")
    print(f"Budget: {budget:.2f}")
    print(f"Number of demands: {len(demands)}")
    
    if results['optimal']:
        opt_tp = results['optimal']['total_throughput']
        print(f"\nOptimal:    {opt_tp:.2f} throughput, {results['optimal']['runtime']:.3f}s")
        print(f"FPTAS:      {results['fptas']['total_throughput']:.2f} throughput, {results['fptas']['runtime']:.3f}s")
        print(f"Greedy:     {results['greedy']['total_throughput']:.2f} throughput, {results['greedy']['runtime']:.3f}s")
        
        if opt_tp > 0:
            fptas_ratio = results['fptas']['total_throughput'] / opt_tp
            greedy_ratio = results['greedy']['total_throughput'] / opt_tp
            print(f"\nApproximation Ratios:")
            print(f"FPTAS:      {fptas_ratio:.3f} ({fptas_ratio*100:.1f}% of optimal)")
            print(f"Greedy:     {greedy_ratio:.3f} ({greedy_ratio*100:.1f}% of optimal)")
            
            results['approximation_ratios'] = {
                'fptas_ratio': fptas_ratio,
                'greedy_ratio': greedy_ratio
            }
    else:
        print(f"\nFPTAS:      {results['fptas']['total_throughput']:.2f} throughput, {results['fptas']['runtime']:.3f}s")
        print(f"Greedy:     {results['greedy']['total_throughput']:.2f} throughput, {results['greedy']['runtime']:.3f}s")
        
        if results['greedy']['total_throughput'] > 0:
            improvement = (results['fptas']['total_throughput'] - results['greedy']['total_throughput']) / results['greedy']['total_throughput']
            print(f"FPTAS vs Greedy: {improvement:.2%} improvement")
    
    print("=" * 60)
    return results


if __name__ == "__main__":
    # Test the optimal solver
    print("Testing Optimal ILP Solver...")
    
    if not PULP_AVAILABLE:
        print("PuLP not available. Please install with: pip install pulp")
    else:
        from sfc_placement_framework import generate_test_instance, SFCPlacementFramework
        
        # Generate small test instance
        network, functions, demands, cost_matrix, throughput_matrix, delay_matrix = \
            generate_test_instance(8, 3, 6, seed=42)
        
        framework = SFCPlacementFramework(network, functions, cost_matrix, 
                                        throughput_matrix, delay_matrix)
        
        budget = sum(cost_matrix.values()) * 0.3
        
        # Run comparison
        results = compare_algorithms_with_optimal(framework, demands, budget)
        
        print("\nTest completed successfully!")