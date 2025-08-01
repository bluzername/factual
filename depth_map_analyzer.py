#!/usr/bin/env python3
"""
Depth Map Analyzer Tool

A standalone tool for analyzing differences between depth maps and computing
integrals over specified rectangular regions.

Author: AI Assistant
Date: 2025-01-20
"""

import numpy as np
import cv2
import argparse
import sys
from typing import Tuple, List, Optional
from pathlib import Path


class DepthMapAnalyzer:
    """
    A tool for analyzing depth map differences and computing regional integrals.
    """
    
    def __init__(self):
        """Initialize the depth map analyzer."""
        self.depth_map_1 = None
        self.depth_map_2 = None
        self.difference_map = None
    
    def load_depth_maps(self, path1: str, path2: str) -> bool:
        """
        Load two depth map images.
        
        Args:
            path1: Path to first depth map image
            path2: Path to second depth map image
            
        Returns:
            bool: True if both images loaded successfully, False otherwise
        """
        try:
            # Load images as grayscale (depth maps are typically single channel)
            self.depth_map_1 = cv2.imread(path1, cv2.IMREAD_GRAYSCALE)
            self.depth_map_2 = cv2.imread(path2, cv2.IMREAD_GRAYSCALE)
            
            if self.depth_map_1 is None:
                print(f"Error: Could not load depth map from {path1}")
                return False
                
            if self.depth_map_2 is None:
                print(f"Error: Could not load depth map from {path2}")
                return False
            
            # Check if dimensions match
            if self.depth_map_1.shape != self.depth_map_2.shape:
                print(f"Error: Depth maps have different dimensions:")
                print(f"  Map 1: {self.depth_map_1.shape}")
                print(f"  Map 2: {self.depth_map_2.shape}")
                return False
            
            print(f"Successfully loaded depth maps with shape: {self.depth_map_1.shape}")
            return True
            
        except Exception as e:
            print(f"Error loading depth maps: {str(e)}")
            return False
    
    def compute_difference(self) -> np.ndarray:
        """
        Compute the difference between the two depth maps.
        
        Returns:
            numpy.ndarray: Difference map (map1 - map2)
        """
        if self.depth_map_1 is None or self.depth_map_2 is None:
            raise ValueError("Depth maps not loaded. Call load_depth_maps() first.")
        
        # Convert to float to handle negative differences properly
        map1_float = self.depth_map_1.astype(np.float32)
        map2_float = self.depth_map_2.astype(np.float32)
        
        # Compute difference
        self.difference_map = map1_float - map2_float
        
        print(f"Computed difference map:")
        print(f"  Min difference: {np.min(self.difference_map):.2f}")
        print(f"  Max difference: {np.max(self.difference_map):.2f}")
        print(f"  Mean difference: {np.mean(self.difference_map):.2f}")
        print(f"  Std difference: {np.std(self.difference_map):.2f}")
        
        return self.difference_map
    
    def validate_coordinates(self, coords: List[Tuple[int, int]]) -> bool:
        """
        Validate that coordinates are within image bounds and form a valid rectangle.
        
        Args:
            coords: List of 4 coordinate tuples (x, y)
            
        Returns:
            bool: True if coordinates are valid, False otherwise
        """
        if len(coords) != 4:
            print(f"Error: Expected 4 coordinates, got {len(coords)}")
            return False
        
        if self.depth_map_1 is None:
            print("Error: No depth map loaded")
            return False
        
        height, width = self.depth_map_1.shape
        
        # Check bounds
        for i, (x, y) in enumerate(coords):
            if x < 0 or x >= width or y < 0 or y >= height:
                print(f"Error: Coordinate {i+1} ({x}, {y}) is out of bounds")
                print(f"  Image dimensions: {width} x {height}")
                return False
        
        # Extract x and y coordinates
        x_coords = [coord[0] for coord in coords]
        y_coords = [coord[1] for coord in coords]
        
        # Check if coordinates can form a rectangle
        if len(set(x_coords)) < 2 or len(set(y_coords)) < 2:
            print("Error: Coordinates don't form a valid rectangle")
            return False
        
        return True
    
    def get_rectangle_bounds(self, coords: List[Tuple[int, int]]) -> Tuple[int, int, int, int]:
        """
        Get the bounding rectangle from 4 coordinates.
        
        Args:
            coords: List of 4 coordinate tuples (x, y)
            
        Returns:
            Tuple: (min_x, min_y, max_x, max_y)
        """
        x_coords = [coord[0] for coord in coords]
        y_coords = [coord[1] for coord in coords]
        
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        
        return min_x, min_y, max_x, max_y
    
    def compute_regional_integral(self, coords: List[Tuple[int, int]]) -> dict:
        """
        Compute the integral of the difference map over the rectangular region
        defined by the 4 input coordinates.
        
        Args:
            coords: List of 4 coordinate tuples (x, y) defining the rectangle
            
        Returns:
            dict: Dictionary containing integral results and statistics
        """
        if self.difference_map is None:
            raise ValueError("Difference map not computed. Call compute_difference() first.")
        
        if not self.validate_coordinates(coords):
            raise ValueError("Invalid coordinates provided")
        
        # Get rectangle bounds
        min_x, min_y, max_x, max_y = self.get_rectangle_bounds(coords)
        
        # Extract the rectangular region from the difference map
        region = self.difference_map[min_y:max_y+1, min_x:max_x+1]
        
        # Compute various integral measures
        integral_sum = np.sum(region)
        integral_mean = np.mean(region)
        integral_abs_sum = np.sum(np.abs(region))
        integral_squared_sum = np.sum(region ** 2)
        
        # Compute region statistics
        region_area = region.size
        region_width = max_x - min_x + 1
        region_height = max_y - min_y + 1
        
        # Regional statistics
        region_min = np.min(region)
        region_max = np.max(region)
        region_std = np.std(region)
        
        results = {
            'coordinates': coords,
            'rectangle_bounds': (min_x, min_y, max_x, max_y),
            'region_dimensions': (region_width, region_height),
            'region_area': region_area,
            'integral_sum': float(integral_sum),
            'integral_mean': float(integral_mean),
            'integral_abs_sum': float(integral_abs_sum),
            'integral_squared_sum': float(integral_squared_sum),
            'region_min': float(region_min),
            'region_max': float(region_max),
            'region_std': float(region_std),
            'region_shape': region.shape
        }
        
        return results
    
    def save_difference_map(self, output_path: str, normalize: bool = True) -> bool:
        """
        Save the difference map as an image.
        
        Args:
            output_path: Path to save the difference map
            normalize: Whether to normalize the difference map for visualization
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        if self.difference_map is None:
            print("Error: No difference map to save")
            return False
        
        try:
            if normalize:
                # Normalize to 0-255 range for visualization
                diff_normalized = cv2.normalize(self.difference_map, None, 0, 255, cv2.NORM_MINMAX)
                diff_to_save = diff_normalized.astype(np.uint8)
            else:
                # Save as-is (may lose information if values exceed uint8 range)
                diff_to_save = np.clip(self.difference_map, 0, 255).astype(np.uint8)
            
            cv2.imwrite(output_path, diff_to_save)
            print(f"Difference map saved to: {output_path}")
            return True
            
        except Exception as e:
            print(f"Error saving difference map: {str(e)}")
            return False
    
    def visualize_region(self, coords: List[Tuple[int, int]], output_path: Optional[str] = None) -> bool:
        """
        Create a visualization showing the selected region on the difference map.
        
        Args:
            coords: List of 4 coordinate tuples (x, y) defining the rectangle
            output_path: Optional path to save the visualization
            
        Returns:
            bool: True if visualization created successfully, False otherwise
        """
        if self.difference_map is None:
            print("Error: No difference map available")
            return False
        
        if not self.validate_coordinates(coords):
            return False
        
        try:
            # Normalize difference map for visualization
            diff_normalized = cv2.normalize(self.difference_map, None, 0, 255, cv2.NORM_MINMAX)
            diff_vis = diff_normalized.astype(np.uint8)
            
            # Convert to BGR for colored rectangle
            diff_bgr = cv2.cvtColor(diff_vis, cv2.COLOR_GRAY2BGR)
            
            # Get rectangle bounds
            min_x, min_y, max_x, max_y = self.get_rectangle_bounds(coords)
            
            # Draw rectangle
            cv2.rectangle(diff_bgr, (min_x, min_y), (max_x, max_y), (0, 255, 0), 2)
            
            # Add coordinate labels
            for i, (x, y) in enumerate(coords):
                cv2.circle(diff_bgr, (x, y), 3, (0, 0, 255), -1)
                cv2.putText(diff_bgr, f"{i+1}", (x+5, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            if output_path:
                cv2.imwrite(output_path, diff_bgr)
                print(f"Visualization saved to: {output_path}")
            
            return True
            
        except Exception as e:
            print(f"Error creating visualization: {str(e)}")
            return False


def parse_coordinates(coord_string: str) -> List[Tuple[int, int]]:
    """
    Parse coordinate string into list of coordinate tuples.
    
    Args:
        coord_string: String in format "x1,y1 x2,y2 x3,y3 x4,y4"
        
    Returns:
        List of coordinate tuples
    """
    try:
        coord_pairs = coord_string.strip().split()
        if len(coord_pairs) != 4:
            raise ValueError(f"Expected 4 coordinate pairs, got {len(coord_pairs)}")
        
        coordinates = []
        for pair in coord_pairs:
            x, y = map(int, pair.split(','))
            coordinates.append((x, y))
        
        return coordinates
        
    except Exception as e:
        raise ValueError(f"Error parsing coordinates: {str(e)}")


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Analyze differences between depth maps and compute regional integrals",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python depth_map_analyzer.py depth1.png depth2.png --coords "10,10 100,10 100,100 10,100"
  python depth_map_analyzer.py depth1.png depth2.png --coords "50,50 150,50 150,150 50,150" --save-diff diff.png --save-viz viz.png
        """
    )
    
    parser.add_argument('depth_map_1', help='Path to first depth map image')
    parser.add_argument('depth_map_2', help='Path to second depth map image')
    parser.add_argument('--coords', required=True,
                       help='4 pixel coordinates as "x1,y1 x2,y2 x3,y3 x4,y4"')
    parser.add_argument('--save-diff', 
                       help='Save difference map to specified path')
    parser.add_argument('--save-viz',
                       help='Save visualization with region overlay to specified path')
    parser.add_argument('--no-normalize', action='store_true',
                       help='Don\'t normalize difference map when saving')
    
    args = parser.parse_args()
    
    try:
        # Parse coordinates
        coordinates = parse_coordinates(args.coords)
        print(f"Parsed coordinates: {coordinates}")
        
        # Initialize analyzer
        analyzer = DepthMapAnalyzer()
        
        # Load depth maps
        if not analyzer.load_depth_maps(args.depth_map_1, args.depth_map_2):
            sys.exit(1)
        
        # Compute difference
        analyzer.compute_difference()
        
        # Compute regional integral
        results = analyzer.compute_regional_integral(coordinates)
        
        # Print results
        print("\n" + "="*60)
        print("REGIONAL INTEGRAL ANALYSIS RESULTS")
        print("="*60)
        print(f"Rectangle bounds: ({results['rectangle_bounds'][0]}, {results['rectangle_bounds'][1]}) to ({results['rectangle_bounds'][2]}, {results['rectangle_bounds'][3]})")
        print(f"Region dimensions: {results['region_dimensions'][0]} x {results['region_dimensions'][1]} pixels")
        print(f"Region area: {results['region_area']} pixels")
        print()
        print("INTEGRAL MEASURES:")
        print(f"  Sum integral: {results['integral_sum']:.4f}")
        print(f"  Mean integral: {results['integral_mean']:.4f}")
        print(f"  Absolute sum integral: {results['integral_abs_sum']:.4f}")
        print(f"  Squared sum integral: {results['integral_squared_sum']:.4f}")
        print()
        print("REGIONAL STATISTICS:")
        print(f"  Min value: {results['region_min']:.4f}")
        print(f"  Max value: {results['region_max']:.4f}")
        print(f"  Standard deviation: {results['region_std']:.4f}")
        print("="*60)
        
        # Save difference map if requested
        if args.save_diff:
            analyzer.save_difference_map(args.save_diff, normalize=not args.no_normalize)
        
        # Save visualization if requested
        if args.save_viz:
            analyzer.visualize_region(coordinates, args.save_viz)
        
        print(f"\nAnalysis completed successfully!")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 