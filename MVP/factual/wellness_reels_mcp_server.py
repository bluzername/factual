#!/usr/bin/env python3
"""
wellness_reels_mcp_server.py

MCP-style server that provides the trending wellness reels finder as a callable tool.
This server implements a simplified MCP interface for the wellness content discovery tool.

Usage:
  python3 wellness_reels_mcp_server.py --port 8080
"""

import asyncio
import json
import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from aiohttp import web
from aiohttp.web import Request, Response, json_response
import subprocess

# Add the current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

# ─── CONFIG ───────────────────────────────────────────────────────────────────

SERVER_NAME = "wellness-reels-finder"
SERVER_VERSION = "1.0.0"
SCRIPT_DIR = Path(__file__).parent
WELLNESS_FINDER_SCRIPT = SCRIPT_DIR / "trending_wellness_reels_finder.py"

# ─── LOGGING ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ─── MCP SERVER IMPLEMENTATION ────────────────────────────────────────────────

class WellnessReelsMCPServer:
    """MCP-style server for the wellness reels finder tool."""
    
    def __init__(self):
        self.app = web.Application()
        self.setup_routes()
    
    def setup_routes(self):
        """Setup HTTP routes for the MCP server."""
        # Core MCP endpoints
        self.app.router.add_get('/', self.get_server_info)
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/capabilities', self.get_capabilities)
        
        # Tool endpoints
        self.app.router.add_get('/tools', self.list_tools)
        self.app.router.add_post('/tools/find_trending_wellness_reels', self.find_trending_wellness_reels)
        
        # Resource endpoints
        self.app.router.add_get('/resources', self.list_resources)
        
        # Enable CORS
        self.app.router.add_options('/{path:.*}', self.handle_options)
    
    async def handle_options(self, request: Request) -> Response:
        """Handle CORS preflight requests."""
        return Response(
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            }
        )
    
    def add_cors_headers(self, response: Response) -> Response:
        """Add CORS headers to response."""
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response
    
    async def get_server_info(self, request: Request) -> Response:
        """Get basic server information."""
        info = {
            "name": SERVER_NAME,
            "version": SERVER_VERSION,
            "description": "MCP server for finding trending factual wellness reels on Instagram",
            "author": "Factual Team",
            "capabilities": [
                "tools",
                "resources"
            ],
            "endpoints": {
                "health": "/health",
                "capabilities": "/capabilities",
                "tools": "/tools",
                "resources": "/resources"
            }
        }
        return self.add_cors_headers(json_response(info))
    
    async def health_check(self, request: Request) -> Response:
        """Health check endpoint."""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": SERVER_VERSION,
            "checks": {
                "wellness_finder_script": WELLNESS_FINDER_SCRIPT.exists(),
                "environment_variables": {
                    "IG_ACCESS_TOKEN": bool(os.getenv("IG_ACCESS_TOKEN")),
                    "IG_BUSINESS_USER_ID": bool(os.getenv("IG_BUSINESS_USER_ID")),
                    "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY"))
                }
            }
        }
        
        # Overall health based on critical components
        if not WELLNESS_FINDER_SCRIPT.exists():
            health_status["status"] = "unhealthy"
            health_status["error"] = "Wellness finder script not found"
        elif not (os.getenv("IG_ACCESS_TOKEN") and os.getenv("IG_BUSINESS_USER_ID")):
            health_status["status"] = "degraded"
            health_status["warning"] = "Instagram API credentials not configured"
        
        status_code = 200 if health_status["status"] == "healthy" else 503
        return self.add_cors_headers(json_response(health_status, status=status_code))
    
    async def get_capabilities(self, request: Request) -> Response:
        """Get server capabilities."""
        capabilities = {
            "tools": {
                "find_trending_wellness_reels": {
                    "description": "Find trending factual wellness reels on Instagram",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "max_reels": {
                                "type": "integer",
                                "description": "Maximum number of reels to find",
                                "default": 20,
                                "minimum": 1,
                                "maximum": 100
                            },
                            "format": {
                                "type": "string",
                                "description": "Output format",
                                "enum": ["links", "csv", "json"],
                                "default": "links"
                            },
                            "min_views": {
                                "type": "integer",
                                "description": "Minimum view count threshold",
                                "default": 10000,
                                "minimum": 0
                            },
                            "min_likes": {
                                "type": "integer",
                                "description": "Minimum like count threshold",
                                "default": 500,
                                "minimum": 0
                            },
                            "min_comments": {
                                "type": "integer",
                                "description": "Minimum comment count threshold",
                                "default": 50,
                                "minimum": 0
                            }
                        }
                    }
                }
            },
            "resources": {
                "latest_results": {
                    "description": "Access to the latest trending wellness reels results"
                }
            }
        }
        return self.add_cors_headers(json_response(capabilities))
    
    async def list_tools(self, request: Request) -> Response:
        """List available tools."""
        tools = [
            {
                "name": "find_trending_wellness_reels",
                "description": "Find trending factual wellness reels on Instagram",
                "parameters": {
                    "max_reels": "Maximum number of reels to find (default: 20)",
                    "format": "Output format: links, csv, json (default: links)",
                    "min_views": "Minimum view count threshold (default: 10000)",
                    "min_likes": "Minimum like count threshold (default: 500)",
                    "min_comments": "Minimum comment count threshold (default: 50)"
                }
            }
        ]
        return self.add_cors_headers(json_response({"tools": tools}))
    
    async def find_trending_wellness_reels(self, request: Request) -> Response:
        """Execute the trending wellness reels finder tool."""
        try:
            # Parse request body
            if request.content_type == 'application/json':
                params = await request.json()
            else:
                params = {}
            
            # Extract parameters with defaults
            max_reels = params.get("max_reels", 20)
            output_format = params.get("format", "links")
            min_views = params.get("min_views", 10000)
            min_likes = params.get("min_likes", 500)
            min_comments = params.get("min_comments", 50)
            
            # Validate parameters
            if not isinstance(max_reels, int) or max_reels < 1 or max_reels > 100:
                return self.add_cors_headers(json_response(
                    {"error": "max_reels must be an integer between 1 and 100"},
                    status=400
                ))
            
            if output_format not in ["links", "csv", "json"]:
                return self.add_cors_headers(json_response(
                    {"error": "format must be one of: links, csv, json"},
                    status=400
                ))
            
            # Generate unique output filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"wellness_reels_mcp_{timestamp}.txt"
            
            # Build command
            cmd = [
                "python3", str(WELLNESS_FINDER_SCRIPT),
                "--max-reels", str(max_reels),
                "--output", output_file,
                "--format", output_format,
                "--min-views", str(min_views),
                "--min-likes", str(min_likes),
                "--min-comments", str(min_comments)
            ]
            
            logger.info(f"Executing: {' '.join(cmd)}")
            
            # Execute the wellness finder
            result = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=SCRIPT_DIR,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                # Read the output file
                output_path = SCRIPT_DIR / output_file
                results = []
                
                if output_path.exists():
                    if output_format == "links":
                        with open(output_path, 'r') as f:
                            results = [line.strip() for line in f if line.strip()]
                    elif output_format == "json":
                        json_file = SCRIPT_DIR / output_file.replace('.txt', '.json')
                        if json_file.exists():
                            with open(json_file, 'r') as f:
                                results = json.load(f)
                    elif output_format == "csv":
                        csv_file = SCRIPT_DIR / output_file.replace('.txt', '.csv')
                        if csv_file.exists():
                            import csv
                            with open(csv_file, 'r') as f:
                                reader = csv.DictReader(f)
                                results = list(reader)
                    
                    # Clean up temporary files
                    try:
                        output_path.unlink(missing_ok=True)
                        (SCRIPT_DIR / output_file.replace('.txt', '.csv')).unlink(missing_ok=True)
                        (SCRIPT_DIR / output_file.replace('.txt', '.json')).unlink(missing_ok=True)
                    except Exception:
                        pass
                
                response_data = {
                    "success": True,
                    "timestamp": timestamp,
                    "parameters": {
                        "max_reels": max_reels,
                        "format": output_format,
                        "min_views": min_views,
                        "min_likes": min_likes,
                        "min_comments": min_comments
                    },
                    "results": results,
                    "count": len(results) if isinstance(results, list) else (results.get("total_found", 0) if isinstance(results, dict) else 0),
                    "stdout": stdout.decode('utf-8') if stdout else "",
                }
                
                return self.add_cors_headers(json_response(response_data))
            
            else:
                error_message = stderr.decode('utf-8') if stderr else "Unknown error"
                logger.error(f"Wellness finder failed: {error_message}")
                
                return self.add_cors_headers(json_response({
                    "success": False,
                    "error": "Wellness finder execution failed",
                    "details": error_message,
                    "stdout": stdout.decode('utf-8') if stdout else "",
                }, status=500))
        
        except Exception as e:
            logger.exception("Error in find_trending_wellness_reels")
            return self.add_cors_headers(json_response({
                "success": False,
                "error": f"Internal server error: {str(e)}"
            }, status=500))
    
    async def list_resources(self, request: Request) -> Response:
        """List available resources."""
        resources = []
        
        # Check for latest results symlink
        latest_link = SCRIPT_DIR / "latest_trending_wellness_reels.txt"
        if latest_link.exists():
            resources.append({
                "name": "latest_results",
                "description": "Latest trending wellness reels results",
                "type": "file",
                "path": str(latest_link)
            })
        
        # Check for archive directory
        archive_dir = SCRIPT_DIR / "wellness_reels_archive"
        if archive_dir.exists():
            resources.append({
                "name": "archive",
                "description": "Historical trending wellness reels archive",
                "type": "directory",
                "path": str(archive_dir)
            })
        
        return self.add_cors_headers(json_response({"resources": resources}))
    
    async def start_server(self, host: str = "localhost", port: int = 8080):
        """Start the MCP server."""
        logger.info(f"Starting Wellness Reels MCP Server on {host}:{port}")
        
        # Check requirements
        if not WELLNESS_FINDER_SCRIPT.exists():
            logger.error(f"Wellness finder script not found: {WELLNESS_FINDER_SCRIPT}")
            sys.exit(1)
        
        if not (os.getenv("IG_ACCESS_TOKEN") and os.getenv("IG_BUSINESS_USER_ID")):
            logger.warning("Instagram API credentials not configured - server will start but tools may fail")
        
        # Start server
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        logger.info(f"Server started at http://{host}:{port}")
        logger.info("Available endpoints:")
        logger.info(f"  GET  http://{host}:{port}/         - Server info")
        logger.info(f"  GET  http://{host}:{port}/health   - Health check")
        logger.info(f"  GET  http://{host}:{port}/tools    - List tools")
        logger.info(f"  POST http://{host}:{port}/tools/find_trending_wellness_reels - Execute finder")
        
        try:
            # Keep server running
            while True:
                await asyncio.sleep(3600)  # Sleep for 1 hour
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        finally:
            await runner.cleanup()

async def main():
    parser = argparse.ArgumentParser(
        description="Wellness Reels MCP Server"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host to bind to (default: localhost)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080)"
    )
    parser.add_argument(
        "--log-level",
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help="Log level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Start server
    server = WellnessReelsMCPServer()
    await server.start_server(args.host, args.port)

if __name__ == "__main__":
    asyncio.run(main())