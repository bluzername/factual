#!/usr/bin/env python3
"""
Example usage of the Depth Map Analyzer tool.

This script demonstrates how to use the DepthMapAnalyzer class programmatically.
"""

import numpy as np
import cv2
from depth_map_analyzer import DepthMapAnalyzer


def create_sample_depth_maps():
    """Create sample depth maps for demonstration."""
    # Create two 400x300 sample depth maps with different patterns
    height, width = 300, 400
    
    # Depth map 1: Gradient pattern
    depth_map_1 = np.zeros((height, width), dtype=np.uint8)
    for i in range(height):
        for j in range(width):
            depth_map_1[i, j] = int((i + j) * 255 / (height + width))
    
    # Depth map 2: Circular pattern
    depth_map_2 = np.zeros((height, width), dtype=np.uint8)
    center_x, center_y = width // 2, height // 2
    max_dist = np.sqrt(center_x**2 + center_y**2)
    
    for i in range(height):
        for j in range(width):
            dist = np.sqrt((j - center_x)**2 + (i - center_y)**2)
            depth_map_2[i, j] = int((1 - dist / max_dist) * 255)
    
    # Save sample depth maps
    cv2.imwrite('sample_depth_map_1.png', depth_map_1)
    cv2.imwrite('sample_depth_map_2.png', depth_map_2)
    
    print("Created sample depth maps:")
    print("  - sample_depth_map_1.png (gradient pattern)")
    print("  - sample_depth_map_2.png (circular pattern)")
    
    return 'sample_depth_map_1.png', 'sample_depth_map_2.png'


def main():
    """Main demonstration function."""
    print("Depth Map Analyzer - Example Usage")
    print("=" * 50)
    
    # Create sample depth maps
    map1_path, map2_path = create_sample_depth_maps()
    
    # Initialize the analyzer
    analyzer = DepthMapAnalyzer()
    
    # Load depth maps
    print(f"\nLoading depth maps...")
    if not analyzer.load_depth_maps(map1_path, map2_path):
        print("Failed to load depth maps!")
        return
    
    # Compute difference
    print(f"\nComputing difference between depth maps...")
    difference = analyzer.compute_difference()
    
    # Define a rectangular region for analysis
    # Format: [(x1, y1), (x2, y2), (x3, y3), (x4, y4)]
    # Let's analyze the central region of the image
    coordinates = [(100, 50), (300, 50), (300, 250), (100, 250)]
    print(f"\nAnalyzing rectangular region with coordinates: {coordinates}")
    
    # Compute regional integral
    results = analyzer.compute_regional_integral(coordinates)
    
    # Display results
    print("\n" + "="*60)
    print("ANALYSIS RESULTS")
    print("="*60)
    print(f"Rectangle bounds: {results['rectangle_bounds']}")
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
    
    # Save outputs
    print(f"\nSaving analysis outputs...")
    
    # Save difference map
    analyzer.save_difference_map('example_difference_map.png')
    
    # Save visualization
    analyzer.visualize_region(coordinates, 'example_visualization.png')
    
    print("Created output files:")
    print("  - example_difference_map.png (difference between the two depth maps)")
    print("  - example_visualization.png (visualization with region overlay)")
    
    print(f"\nExample completed successfully!")


if __name__ == "__main__":
    main() 