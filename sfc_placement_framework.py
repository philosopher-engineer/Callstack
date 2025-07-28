import numpy as np
import networkx as nx
from typing import List, Tuple, Dict, Set, Optional
import heapq
from dataclasses import dataclass
from collections import defaultdict
import time
import matplotlib.pyplot as plt
import seaborn as sns
from itertools import product
import random
from copy import deepcopy

@dataclass
class NetworkFunction:
    """Represents a cloud-native network function"""
    id: str
    name: str

@dataclass
class Node:
    """Represents a computational node in the network"""
    id: str
    name: str
    
@dataclass
class Demand:
    """Represents an SFC demand with path and function chain"""
    id: str
    path: List[str]  # List of node IDs
    sfc: List[str]   # List of function IDs
    delay_threshold: Optional[float] = None
    
@dataclass
class Configuration:
    """Represents a cost-throughput configuration for a demand"""
    cost: float
    throughput: float
    delay: Optional[float] = None
    placement: Optional[Dict] = None  # Maps function to node

class MCKPItem:
    """Item for Multiple Choice Knapsack Problem"""
    def __init__(self, profit: float, weight: float, group: int, item_id: int):
        self.profit = profit
        self.weight = weight
        self.group = group
        self.item_id = item_id

class SFCPlacementFramework:
    """Main framework for SFC placement with FPTAS algorithms"""
    
    def __init__(self, network: nx.Graph, functions: List[NetworkFunction], 
                 cost_matrix: Dict, throughput_matrix: Dict, delay_matrix: Dict = None):
        self.network = network
        self.functions = {f.id: f for f in functions}
        self.cost_matrix = cost_matrix  # (node_id, function_id) -> cost
        self.throughput_matrix = throughput_matrix  # (node_id, function_id) -> throughput
        self.delay_matrix = delay_matrix or {}  # (node_id, function_id) -> delay
        
    def build_associated_network(self, demand: Demand) -> Tuple[nx.DiGraph, str, str]:
        """Build the associated network H(d) for a demand as described in the paper"""
        H = nx.DiGraph()
        
        # Add source and sink
        source = f"s_{demand.id}"
        sink = f"t_{demand.id}"
        H.add_node(source, cost=0, throughput=float('inf'), delay=0)
        H.add_node(sink, cost=0, throughput=float('inf'), delay=0)
        
        # Create layered structure
        layers = []
        for layer_idx, function_id in enumerate(demand.sfc):
            layer_nodes = []
            for node_idx, node_id in enumerate(demand.path):
                layer_node = f"{node_id}_{layer_idx}"
                
                # Add node attributes (cost, throughput, delay)
                cost = self.cost_matrix.get((node_id, function_id), float('inf'))
                throughput = self.throughput_matrix.get((node_id, function_id), 0)
                delay = self.delay_matrix.get((node_id, function_id), 0)
                
                # Skip nodes with invalid configurations
                if cost == float('inf') or throughput <= 0:
                    continue
                
                H.add_node(layer_node, cost=cost, throughput=throughput, delay=delay,
                          node_id=node_id, function_id=function_id)
                layer_nodes.append(layer_node)
                
            layers.append(layer_nodes)
        
        # Remove empty layers
        layers = [layer for layer in layers if layer]
        
        if not layers:
            # No valid configurations found
            return H, source, sink
        
        # Add edges from source to first layer
        for node in layers[0]:
            H.add_edge(source, node)
            
        # Add edges between layers (maintaining path order)
        for layer_idx in range(len(layers) - 1):
            current_layer = layers[layer_idx]
            next_layer = layers[layer_idx + 1]
            
            for current_node in current_layer:
                for next_node in next_layer:
                    # Extract node indices from node names to maintain path order
                    current_node_id = H.nodes[current_node]['node_id']
                    next_node_id = H.nodes[next_node]['node_id']
                    
                    current_idx = demand.path.index(current_node_id)
                    next_idx = demand.path.index(next_node_id)
                    
                    # Edge exists if next node is at same or later position in path
                    if next_idx >= current_idx:
                        H.add_edge(current_node, next_node)
        
        # Add edges from last layer to sink
        if layers:
            for node in layers[-1]:
                H.add_edge(node, sink)
            
        return H, source, sink
    
    def max_bottleneck_path_dag(self, G: nx.DiGraph, source: str, sink: str) -> Tuple[float, Dict]:
        """Algorithm 1: Maximum bottleneck path in DAG - O(|E| + |V|)"""
        # Topological sort
        topo_order = list(nx.topological_sort(G))
        
        # Initialize bottleneck values
        B = {node: 0 for node in G.nodes()}
        B[source] = float('inf')
        predecessors = {node: None for node in G.nodes()}
        
        # Process nodes in topological order
        for u in topo_order:
            if u not in G.nodes():
                continue
                
            for v in G.neighbors(u):
                if v in G.nodes():
                    # Bottleneck capacity is min of current bottleneck and node throughput
                    if v in G.nodes() and 'throughput' in G.nodes[v]:
                        capacity = G.nodes[v]['throughput']
                    else:
                        capacity = float('inf')  # For source/sink nodes
                        
                    bottleneck = min(B[u], capacity)
                    
                    if bottleneck > B[v]:
                        B[v] = bottleneck
                        predecessors[v] = u
        
        return B[sink], predecessors
    
    def shortest_path_dag(self, G: nx.DiGraph, source: str, sink: str) -> float:
        """Shortest path in DAG using topological sorting"""
        topo_order = list(nx.topological_sort(G))
        
        dist = {node: float('inf') for node in G.nodes()}
        dist[source] = 0
        
        for u in topo_order:
            if dist[u] == float('inf'):
                continue
                
            for v in G.neighbors(u):
                if v in G.nodes() and 'cost' in G.nodes[v]:
                    edge_cost = G.nodes[v]['cost']
                    if dist[u] + edge_cost < dist[v]:
                        dist[v] = dist[u] + edge_cost
        
        return dist[sink] if dist[sink] != float('inf') else float('inf')
    
    def rsp_fptas(self, G: nx.DiGraph, source: str, sink: str, 
                  delay_threshold: float, epsilon: float) -> float:
        """
        Restricted Shortest Path FPTAS (Ergun et al.)
        Returns (1+ε)-approximation of minimum cost path with delay ≤ delay_threshold
        """
        if delay_threshold <= 0:
            return float('inf')
            
        # Get topological order
        topo_order = list(nx.topological_sort(G))
        
        # Compute delay bounds
        max_delay = max(G.nodes[v].get('delay', 0) for v in G.nodes() if 'delay' in G.nodes[v])
        if max_delay == 0:
            max_delay = 1
            
        # Scale delays
        delta = epsilon * max_delay / len(G.nodes())
        if delta <= 0:
            delta = 1
        
        # DP table: dp[v][scaled_delay] = minimum cost
        max_scaled_delay = int(delay_threshold / delta) + 1
        dp = defaultdict(lambda: defaultdict(lambda: float('inf')))
        dp[source][0] = 0
        
        # Process nodes in topological order
        for u in topo_order:
            for v in G.neighbors(u):
                if v in G.nodes() and 'cost' in G.nodes[v] and 'delay' in G.nodes[v]:
                    node_cost = G.nodes[v]['cost']
                    node_delay = G.nodes[v]['delay']
                    scaled_delay = int(node_delay / delta)
                    
                    for prev_delay in range(max_scaled_delay):
                        if dp[u][prev_delay] != float('inf'):
                            new_delay = prev_delay + scaled_delay
                            if new_delay <= max_scaled_delay:
                                new_cost = dp[u][prev_delay] + node_cost
                                if new_cost < dp[v][new_delay]:
                                    dp[v][new_delay] = new_cost
        
        # Find minimum cost path satisfying delay constraint
        min_cost = float('inf')
        max_allowed_scaled_delay = int(delay_threshold / delta)
        
        for delay in range(max_allowed_scaled_delay + 1):
            if dp[sink][delay] < min_cost:
                min_cost = dp[sink][delay]
        
        return min_cost if min_cost != float('inf') else float('inf')
    
    def generate_cp_pairs_non_delay(self, demand: Demand) -> List[Configuration]:
        """Algorithm 2: CP Pair Generation (Non-Delay) from the paper"""
        H, source, sink = self.build_associated_network(demand)
        configurations = []
        min_cost = float('inf')
        
        # Make a copy to modify
        H_prime = H.copy()
        
        iteration = 0
        max_iterations = len(H.edges()) + 1  # Safety bound
        
        while H_prime.has_node(source) and H_prime.has_node(sink) and iteration < max_iterations:
            try:
                # Check if path exists
                if not nx.has_path(H_prime, source, sink):
                    break
                    
                # Find maximum bottleneck path
                bottleneck, predecessors = self.max_bottleneck_path_dag(H_prime, source, sink)
                
                if bottleneck <= 0:
                    break
                
                # Create subgraph with throughput >= bottleneck
                G_tau = H_prime.copy()
                nodes_to_remove = []
                for node in G_tau.nodes():
                    if ('throughput' in G_tau.nodes[node] and 
                        G_tau.nodes[node]['throughput'] < bottleneck):
                        nodes_to_remove.append(node)
                
                G_tau.remove_nodes_from(nodes_to_remove)
                
                # Find shortest path in G_tau
                if G_tau.has_node(source) and G_tau.has_node(sink):
                    cost = self.shortest_path_dag(G_tau, source, sink)
                    
                    if cost < min_cost and cost != float('inf'):
                        config = Configuration(cost=cost, throughput=bottleneck)
                        configurations.append(config)
                        min_cost = cost
                
                # Remove edges with throughput = bottleneck
                edges_to_remove = []
                for node in H_prime.nodes():
                    if ('throughput' in H_prime.nodes[node] and 
                        H_prime.nodes[node]['throughput'] == bottleneck):
                        # Remove all edges connected to this node
                        edges_to_remove.extend(list(H_prime.in_edges(node)))
                        edges_to_remove.extend(list(H_prime.out_edges(node)))
                
                H_prime.remove_edges_from(edges_to_remove)
                
                iteration += 1
                
            except Exception as e:
                print(f"Error in iteration {iteration}: {e}")
                break
        
        return configurations
    
    def generate_cp_pairs_delay_aware(self, demand: Demand, epsilon: float) -> List[Configuration]:
        """Algorithm 3: CP Pair Generation (Delay-Aware) from the paper"""
        if demand.delay_threshold is None:
            return self.generate_cp_pairs_non_delay(demand)
            
        H, source, sink = self.build_associated_network(demand)
        configurations = []
        min_cost = float('inf')
        
        # Make a copy to modify
        H_prime = H.copy()
        
        iteration = 0
        max_iterations = len(H.edges()) + 1
        
        while H_prime.has_node(source) and H_prime.has_node(sink) and iteration < max_iterations:
            try:
                if not nx.has_path(H_prime, source, sink):
                    break
                    
                # Find maximum bottleneck path
                bottleneck, predecessors = self.max_bottleneck_path_dag(H_prime, source, sink)
                
                if bottleneck <= 0:
                    break
                
                # Create subgraph with throughput >= bottleneck
                G_tau = H_prime.copy()
                nodes_to_remove = []
                for node in G_tau.nodes():
                    if ('throughput' in G_tau.nodes[node] and 
                        G_tau.nodes[node]['throughput'] < bottleneck):
                        nodes_to_remove.append(node)
                
                G_tau.remove_nodes_from(nodes_to_remove)
                
                # Use RSP-FPTAS for delay-constrained shortest path
                if G_tau.has_node(source) and G_tau.has_node(sink):
                    cost_approx = self.rsp_fptas(G_tau, source, sink, 
                                               demand.delay_threshold, epsilon)
                    
                    if cost_approx < min_cost and cost_approx != float('inf'):
                        config = Configuration(cost=cost_approx, throughput=bottleneck,
                                             delay=demand.delay_threshold)
                        configurations.append(config)
                        min_cost = cost_approx
                
                # Remove edges with throughput = bottleneck
                edges_to_remove = []
                for node in H_prime.nodes():
                    if ('throughput' in H_prime.nodes[node] and 
                        H_prime.nodes[node]['throughput'] == bottleneck):
                        edges_to_remove.extend(list(H_prime.in_edges(node)))
                        edges_to_remove.extend(list(H_prime.out_edges(node)))
                
                H_prime.remove_edges_from(edges_to_remove)
                
                iteration += 1
                
            except Exception as e:
                print(f"Error in delay-aware iteration {iteration}: {e}")
                break
        
        return configurations
    
    def mckp_fptas(self, groups: List[List[MCKPItem]], capacity: float, epsilon: float) -> Tuple[float, List[int]]:
        """
        FPTAS for Multiple Choice Knapsack Problem (Bansal & Venkaiah)
        Returns (1-ε)-approximation in O(nm/ε) time
        """
        if not groups or capacity <= 0:
            return 0, []
            
        m = len(groups)  # number of groups
        n = sum(len(group) for group in groups)  # total items
        
        if n == 0:
            return 0, []
        
        # Find maximum profit
        all_profits = [item.profit for group in groups for item in group if item.profit > 0]
        if not all_profits:
            return 0, []
        
        P_max = max(all_profits)
        if P_max <= 0:
            return 0, []
        
        # Scaling factor
        delta = epsilon * P_max / m
        if delta <= 0:
            delta = 1
        
        # Scale profits
        scaled_groups = []
        for group in groups:
            scaled_group = []
            for item in group:
                scaled_profit = int(item.profit / delta) if item.profit > 0 else 0
                scaled_item = MCKPItem(scaled_profit, item.weight, item.group, item.item_id)
                scaled_group.append(scaled_item)
            scaled_groups.append(scaled_group)
        
        # Compute maximum scaled profit value
        V_prime = sum(max(item.profit for item in group) for group in scaled_groups if group)
        V_prime = max(1, int(V_prime))
        
        # DP table: f[j][v] = minimum weight to achieve scaled profit v using first j groups
        f = [[float('inf')] * (V_prime + 1) for _ in range(m + 1)]
        f[0][0] = 0
        
        # Fill DP table
        for j in range(1, m + 1):
            group = scaled_groups[j - 1]
            for v in range(V_prime + 1):
                # Option 1: don't select any item from group j
                f[j][v] = f[j-1][v]
                
                # Option 2: select an item from group j
                for item in group:
                    if v >= item.profit and f[j-1][v - item.profit] != float('inf'):
                        weight = f[j-1][v - item.profit] + item.weight
                        if weight <= capacity:
                            f[j][v] = min(f[j][v], weight)
        
        # Find optimal solution
        best_v = 0
        for v in range(V_prime + 1):
            if f[m][v] <= capacity:
                best_v = v
        
        # Backtrack to find solution
        solution = []
        j, v = m, best_v
        
        while j > 0 and v > 0:
            group = scaled_groups[j - 1]
            
            # Check if we selected an item from this group
            selected_item = None
            for item in group:
                if (v >= item.profit and 
                    f[j-1][v - item.profit] != float('inf') and
                    f[j-1][v - item.profit] + item.weight == f[j][v]):
                    selected_item = item
                    break
            
            if selected_item:
                solution.append(selected_item.item_id)
                v -= selected_item.profit
            
            j -= 1
        
        # Convert back to original profit scale
        actual_profit = 0
        for i, item_id in enumerate(solution):
            if i < len(groups) and 0 <= item_id < len(groups[i]):
                actual_profit += groups[i][item_id].profit
        
        return actual_profit, solution
    
    def solve_non_delay_aware(self, demands: List[Demand], budget: float, epsilon: float) -> Tuple[List[Demand], float]:
        """Solve the non-delay-aware RC-CNF-SFC placement problem"""
        # Generate configurations for each demand
        all_configs = {}
        mckp_groups = []
        
        for i, demand in enumerate(demands):
            configs = self.generate_cp_pairs_non_delay(demand)
            all_configs[i] = configs
            
            # Create MCKP group for this demand
            group = []
            for j, config in enumerate(configs):
                if config.cost <= budget and config.throughput > 0:
                    item = MCKPItem(profit=config.throughput, weight=config.cost, 
                                  group=i, item_id=j)
                    group.append(item)
            
            # Add "no selection" option
            group.append(MCKPItem(profit=0, weight=0, group=i, item_id=-1))
            mckp_groups.append(group)
        
        # Solve MCKP
        total_throughput, solution = self.mckp_fptas(mckp_groups, budget, epsilon)
        
        # Extract selected demands
        selected_demands = []
        for i, item_id in enumerate(solution):
            if i < len(demands) and item_id != -1 and item_id < len(all_configs[i]):
                selected_demands.append(demands[i])
        
        return selected_demands, total_throughput
    
    def solve_delay_aware(self, demands: List[Demand], budget: float, epsilon: float) -> Tuple[List[Demand], float]:
        """Solve the delay-aware RC-CNF-SFC placement problem"""
        epsilon1 = epsilon / 2  # For RSP-FPTAS
        epsilon2 = epsilon / 2  # For MCKP-FPTAS
        
        # Generate configurations for each demand
        all_configs = {}
        mckp_groups = []
        
        for i, demand in enumerate(demands):
            configs = self.generate_cp_pairs_delay_aware(demand, epsilon1)
            all_configs[i] = configs
            
            # Create MCKP group for this demand
            group = []
            for j, config in enumerate(configs):
                if config.cost <= budget and config.throughput > 0:
                    item = MCKPItem(profit=config.throughput, weight=config.cost, 
                                  group=i, item_id=j)
                    group.append(item)
            
            # Add "no selection" option
            group.append(MCKPItem(profit=0, weight=0, group=i, item_id=-1))
            mckp_groups.append(group)
        
        # Solve MCKP
        total_throughput, solution = self.mckp_fptas(mckp_groups, budget, epsilon2)
        
        # Extract selected demands
        selected_demands = []
        for i, item_id in enumerate(solution):
            if i < len(demands) and item_id != -1 and item_id < len(all_configs[i]):
                selected_demands.append(demands[i])
        
        return selected_demands, total_throughput


class BaselineAlgorithms:
    """Baseline algorithms for comparison"""
    
    def __init__(self, framework: SFCPlacementFramework):
        self.framework = framework
    
    def greedy_throughput(self, demands: List[Demand], budget: float) -> Tuple[List[Demand], float]:
        """Greedy algorithm that selects demands by throughput/cost ratio"""
        # Calculate efficiency for each demand
        demand_efficiency = []
        
        for demand in demands:
            configs = self.framework.generate_cp_pairs_non_delay(demand)
            if configs:
                # Use the best configuration (highest throughput for lowest cost)
                best_config = max(configs, key=lambda c: c.throughput / max(c.cost, 1e-6))
                efficiency = best_config.throughput / max(best_config.cost, 1e-6)
                demand_efficiency.append((demand, best_config, efficiency))
        
        # Sort by efficiency (descending)
        demand_efficiency.sort(key=lambda x: x[2], reverse=True)
        
        # Greedily select demands
        selected = []
        total_cost = 0
        total_throughput = 0
        
        for demand, config, _ in demand_efficiency:
            if total_cost + config.cost <= budget:
                selected.append(demand)
                total_cost += config.cost
                total_throughput += config.throughput
        
        return selected, total_throughput
    
    def random_selection(self, demands: List[Demand], budget: float) -> Tuple[List[Demand], float]:
        """Random selection baseline"""
        shuffled = demands.copy()
        random.shuffle(shuffled)
        
        selected = []
        total_cost = 0
        total_throughput = 0
        
        for demand in shuffled:
            configs = self.framework.generate_cp_pairs_non_delay(demand)
            if configs:
                config = random.choice(configs)
                if total_cost + config.cost <= budget:
                    selected.append(demand)
                    total_cost += config.cost
                    total_throughput += config.throughput
        
        return selected, total_throughput


def generate_test_instance(num_nodes: int, num_functions: int, num_demands: int, 
                          seed: int = 42) -> Tuple[nx.Graph, List[NetworkFunction], 
                                                  List[Demand], Dict, Dict, Dict]:
    """Generate a test instance for evaluation"""
    random.seed(seed)
    np.random.seed(seed)
    
    # Create network topology
    network = nx.erdos_renyi_graph(num_nodes, 0.3, seed=seed)
    network = nx.Graph(network)  # Ensure it's undirected
    
    # Add node attributes
    for i, node in enumerate(network.nodes()):
        network.nodes[node]['name'] = f"node_{i}"
    
    # Create functions
    functions = [NetworkFunction(id=f"f_{i}", name=f"function_{i}") 
                for i in range(num_functions)]
    
    # Generate cost, throughput, and delay matrices
    cost_matrix = {}
    throughput_matrix = {}
    delay_matrix = {}
    
    for node in network.nodes():
        for func in functions:
            # Random cost between 1 and 10
            cost_matrix[(str(node), func.id)] = random.uniform(1, 10)
            # Random throughput between 1 and 20
            throughput_matrix[(str(node), func.id)] = random.uniform(1, 20)
            # Random delay between 0.1 and 2.0
            delay_matrix[(str(node), func.id)] = random.uniform(0.1, 2.0)
    
    # Generate demands
    demands = []
    for i in range(num_demands):
        # Random path length between 3 and min(6, num_nodes)
        path_length = random.randint(3, min(6, num_nodes))
        
        # Select random path
        nodes = list(network.nodes())
        path = random.sample(nodes, path_length)
        path = [str(node) for node in sorted(path)]  # Sort to maintain order
        
        # Random SFC length between 1 and min(4, num_functions)
        sfc_length = random.randint(1, min(4, num_functions))
        sfc = random.sample([f.id for f in functions], sfc_length)
        
        # Random delay threshold
        delay_threshold = random.uniform(2.0, 8.0)
        
        demand = Demand(id=f"d_{i}", path=path, sfc=sfc, delay_threshold=delay_threshold)
        demands.append(demand)
    
    return network, functions, demands, cost_matrix, throughput_matrix, delay_matrix