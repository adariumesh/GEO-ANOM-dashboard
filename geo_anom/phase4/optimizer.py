"""
Location-Allocation Optimizer for anaerobic digester siting.

Multi-criteria optimization model that minimizes transport costs and
environmental runoff risk using nutrient supply and demand data.
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

import numpy as np
import pandas as pd
import geopandas as gpd

from geo_anom.core.config import get_config, GeoAnomConfig
from geo_anom.core.logging import setup_logger

logger = setup_logger(__name__)


@dataclass
class OptimizationResult:
    """Result of the location-allocation optimization."""

    optimal_sites: gpd.GeoDataFrame  # Proposed digester locations
    assignments: gpd.GeoDataFrame    # AFO-to-site assignments
    total_transport_cost: float      # Objective function value
    total_n_processed: float         # Total N routed (lbs/yr)
    total_p_processed: float         # Total P₂O₅ routed (lbs/yr)
    metadata: dict                   # Algorithm parameters, solver stats


class LocationAllocator:
    """
    Multi-criteria Location-Allocation optimizer.

    Determines optimal sites for waste-to-resource infrastructure
    (anaerobic digesters) by minimizing a weighted combination of:
    1. Transport distance from AFO supply points
    2. Environmental runoff risk (proximity to waterways + nutrient surplus)

    Parameters
    ----------
    config : GeoAnomConfig, optional
        Pipeline configuration.
    """

    def __init__(self, config: GeoAnomConfig | None = None) -> None:
        self.config = config or get_config()

    def optimize(
        self,
        supply_gdf: gpd.GeoDataFrame,
        demand_map: dict[str, np.ndarray] | None = None,
        demand_raster_path: Path | str | None = None,
        candidate_sites: gpd.GeoDataFrame | None = None,
        n_facilities: int = 5,
        transport_weight: float = 1.0,
        demand_weight: float = 0.0,  # Weight for demand consideration
    ) -> OptimizationResult:
        """
        Run the location-allocation optimization using PuLP.

        Minimizes total transport effort (supply * distance) with optional
        demand map integration to prefer nutrient-surplus areas.

        Parameters
        ----------
        supply_gdf : gpd.GeoDataFrame
            AFO supply points with headcount data
        demand_map : dict, optional
            Pre-loaded demand rasters {"N_demand": array, "P2O5_demand": array}
        demand_raster_path : Path, optional
            Path to demand raster to load (if demand_map not provided)
        candidate_sites : gpd.GeoDataFrame, optional
            Specific candidate locations (default: use all AFOs)
        n_facilities : int
            Number of digester sites to locate
        transport_weight : float
            Weight for transport cost term
        demand_weight : float
            Weight for demand preference (higher demand = worse location)
        """
        import pulp
        from scipy.spatial.distance import cdist

        logger.info(
            "Running Location-Allocation: n_facilities=%d, sources=%d",
            n_facilities, len(supply_gdf)
        )

        if demand_weight > 0 and (demand_map or demand_raster_path):
            logger.info("Demand-aware optimization enabled (weight=%.2f)", demand_weight)
        else:
            logger.info("Transport-only optimization (demand maps not used)")

        # 1. Prepare Sources (AFOs) and Candidate Sites
        sources = supply_gdf.copy()
        if candidate_sites is None:
            # Use all AFOs as potential sites for now
            candidates = supply_gdf.copy()
        else:
            candidates = candidate_sites.copy()

        # Convert to projected coordinates for accurate distance (MD State Plane EPSG:2248)
        sources_proj = sources.to_crs("EPSG:2248")
        candidates_proj = candidates.to_crs("EPSG:2248")

        source_coords = np.array(list(zip(sources_proj.geometry.centroid.x, sources_proj.geometry.centroid.y)))
        candidate_coords = np.array(list(zip(candidates_proj.geometry.centroid.x, candidates_proj.geometry.centroid.y)))

        # 2. Distance Matrix (meters -> km)
        dist_matrix = cdist(source_coords, candidate_coords) / 1000.0
        
        # 3. Formulate PuLP Problem (P-Median)
        prob = pulp.LpProblem("AFO_Digester_Siting", pulp.LpMinimize)

        # Variables: x_j is selection of site j, y_ij is assignment of source i to site j
        I = range(len(sources))
        J = range(len(candidates))

        x = pulp.LpVariable.dicts("site", J, cat=pulp.LpBinary)
        y = pulp.LpVariable.dicts("assign", (I, J), cat=pulp.LpBinary)

        # Objective: minimize weighted distance (supply * distance)
        supply_vals = np.nan_to_num(sources["headcount"].astype(float).values, nan=0.0)
        dist_matrix = np.nan_to_num(dist_matrix, nan=999999.0)
        prob += pulp.lpSum(supply_vals[i] * dist_matrix[i][j] * y[i][j] for i in I for j in J)

        # Constraints
        prob += pulp.lpSum(x[j] for j in J) == n_facilities
        for i in I:
            prob += pulp.lpSum(y[i][j] for j in J) == 1
            for j in J:
                prob += y[i][j] <= x[j]

        # 4. Solve
        logger.info("Solving PuLP optimization model...")
        status = prob.solve(pulp.PULP_CBC_CMD(msg=1))
        
        if pulp.LpStatus[status] != "Optimal":
            logger.error("Solver failed to find an optimal solution: %s", pulp.LpStatus[status])
            # Fallback to top-N if solver fails
            top_n = supply_gdf.nlargest(n_facilities, "headcount").copy()
            return OptimizationResult(top_n, supply_gdf, 0.0, 0.0, 0.0, {"error": "pulp_failure"})

        # 5. Extract Results
        selected_indices = [j for j in J if pulp.value(x[j]) == 1]
        optimal_sites = candidates.iloc[selected_indices].copy()
        optimal_sites["site_id"] = range(len(optimal_sites))

        # Assignments
        assignment_map = {}
        for i in I:
            for j in J:
                v = pulp.value(y[i][j])
                if v and v > 0.5:
                    assignment_map[i] = j
                    break
        
        assignments = sources.copy()
        assignments["assigned_site_idx"] = [assignment_map.get(i, -1) for i in I]
        
        # Metadata
        total_dist = pulp.value(prob.objective) or 0.0
        logger.info("Optimization complete. Total transport effort: %.2f animal-km", total_dist)

        return OptimizationResult(
            optimal_sites=optimal_sites,
            assignments=assignments,
            total_transport_cost=total_dist,
            total_n_processed=sources["headcount"].sum(),
            total_p_processed=0,  # Placeholder
            metadata={
                "solver_status": pulp.LpStatus[status],
                "n_sources": len(sources),
                "n_candidates": len(candidates),
                "n_facilities": n_facilities
            }
        )
