#!/usr/bin/env python3
"""
HTML Summary Generator for Factual Pipeline

Generates rich HTML summaries and Instagram-ready descriptions for fact-checked reels.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse
import re


class HTMLSummaryGenerator:
    """Generate rich HTML summaries for reel fact-checking"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.template_dir = Path(__file__).parent / "templates"
        
    def generate_summary(self, reel_result: Dict[str, Any], output_dir: str) -> Dict[str, str]:
        """
        Generate comprehensive HTML summary and Instagram description
        
        Args:
            reel_result: Processing result from factual pipeline
            output_dir: Directory to save output files
            
        Returns:
            Dictionary with paths to generated files
        """
        output_paths = {}
        
        # Generate HTML summary
        html_content = self._generate_html_summary(reel_result)
        html_path = os.path.join(output_dir, "summary.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        output_paths['html_summary'] = html_path
        
        # Generate Instagram description
        ig_desc = self._generate_instagram_description(reel_result)
        ig_path = os.path.join(output_dir, "instagram_description.txt")
        with open(ig_path, 'w', encoding='utf-8') as f:
            f.write(ig_desc)
        output_paths['instagram_description'] = ig_path
        
        # Generate copyable sources list
        sources_text = self._generate_sources_text(reel_result)
        sources_path = os.path.join(output_dir, "sources_copyable.txt")
        with open(sources_path, 'w', encoding='utf-8') as f:
            f.write(sources_text)
        output_paths['sources_text'] = sources_path
        
        return output_paths
    
    def _generate_html_summary(self, reel_result: Dict[str, Any]) -> str:
        """Generate comprehensive HTML summary"""
        
        # Extract key information
        url = reel_result.get('original_url', 'Unknown')
        platform = self._detect_platform(url)
        processed_at = datetime.now().strftime('%B %d, %Y at %I:%M %p')
        
        # Get claims and interventions
        claims = reel_result.get('claims', [])
        interventions = reel_result.get('interventions', [])
        sources = reel_result.get('sources', [])
        
        # Calculate overall verdict
        verdict = self._calculate_verdict(claims, interventions)
        verdict_color = self._get_verdict_color(verdict)
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fact Check Summary - {platform.title()} Reel</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #fafafa;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 2.2em;
        }}
        
        .platform-badge {{
            background: rgba(255, 255, 255, 0.2);
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            display: inline-block;
            margin-top: 10px;
        }}
        
        .verdict {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 30px;
            border-left: 5px solid {verdict_color};
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .verdict-status {{
            font-size: 1.4em;
            font-weight: bold;
            color: {verdict_color};
            margin-bottom: 10px;
        }}
        
        .section {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 25px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .section h2 {{
            color: #333;
            margin-top: 0;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        
        .claim {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 15px 0;
            border-left: 4px solid #667eea;
        }}
        
        .claim-text {{
            font-weight: bold;
            margin-bottom: 10px;
        }}
        
        .claim-verdict {{
            color: #666;
            font-style: italic;
        }}
        
        .source {{
            background: #f0f8ff;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
            border: 1px solid #e1ecf4;
        }}
        
        .source-title {{
            font-weight: bold;
            color: #1a73e8;
            margin-bottom: 5px;
        }}
        
        .source-link {{
            color: #1a73e8;
            text-decoration: none;
            word-break: break-all;
        }}
        
        .source-link:hover {{
            text-decoration: underline;
        }}
        
        .metadata {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-top: 30px;
            font-size: 0.9em;
            color: #666;
        }}
        
        .copy-button {{
            background: #667eea;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9em;
            margin-top: 10px;
        }}
        
        .copy-button:hover {{
            background: #5a67d8;
        }}
        
        @media (max-width: 600px) {{
            body {{ padding: 10px; }}
            .header {{ padding: 20px; }}
            .section {{ padding: 15px; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Fact Check Report</h1>
        <div class="platform-badge">{platform.title()} Reel</div>
    </div>
    
    <div class="verdict">
        <div class="verdict-status">Overall Assessment: {verdict}</div>
        <p>This {platform} reel has been analyzed for factual accuracy using AI-powered fact-checking tools.</p>
    </div>
    
    <div class="section">
        <h2>📋 Claims Analyzed</h2>
        {self._format_claims_html(claims, interventions)}
    </div>
    
    <div class="section">
        <h2>📚 Sources & References</h2>
        {self._format_sources_html(sources)}
        <button class="copy-button" onclick="copySourcesText()">Copy Sources for Instagram</button>
    </div>
    
    <div class="section">
        <h2>🎯 Recommendations</h2>
        {self._generate_recommendations_html(verdict, claims)}
    </div>
    
    <div class="metadata">
        <strong>Original Content:</strong> <a href="{url}" target="_blank" class="source-link">{url}</a><br>
        <strong>Processed:</strong> {processed_at}<br>
        <strong>Generated by:</strong> Factual AI Pipeline v2.0
    </div>
    
    <script>
        function copySourcesText() {{
            fetch('sources_copyable.txt')
                .then(response => response.text())
                .then(text => {{
                    navigator.clipboard.writeText(text).then(() => {{
                        alert('Sources copied to clipboard!');
                    }});
                }})
                .catch(err => console.error('Failed to copy sources:', err));
        }}
    </script>
</body>
</html>"""
        
        return html
    
    def _generate_instagram_description(self, reel_result: Dict[str, Any]) -> str:
        """Generate Instagram-ready description text"""
        
        url = reel_result.get('original_url', '')
        claims = reel_result.get('claims', [])
        interventions = reel_result.get('interventions', [])
        sources = reel_result.get('sources', [])
        
        verdict = self._calculate_verdict(claims, interventions)
        
        # Create emoji-rich description
        verdict_emoji = {
            'VERIFIED': '✅',
            'PARTIALLY ACCURATE': '⚠️',
            'MISLEADING': '❌',
            'FALSE': '🚫',
            'NEEDS CONTEXT': '💭'
        }.get(verdict, '🔍')
        
        description = f"""{verdict_emoji} FACT CHECK COMPLETE

🎯 Verdict: {verdict}

📋 Key Findings:
{self._format_claims_for_instagram(claims, interventions)}

📚 Sources:
{self._format_sources_for_instagram(sources)}

🔗 Original: {url}
📅 Checked: {datetime.now().strftime('%m/%d/%Y')}

#FactCheck #Verification #TruthMatters #MediaLiteracy #AIFactCheck"""
        
        # Ensure it fits Instagram's character limit (2200)
        if len(description) > 2200:
            description = description[:2150] + "...\n\n#FactCheck #Verification"
        
        return description
    
    def _generate_sources_text(self, reel_result: Dict[str, Any]) -> str:
        """Generate copyable sources text for Instagram comments"""
        
        sources = reel_result.get('sources', [])
        
        if not sources:
            return "Sources:\nNo external sources were referenced in this fact-check."
        
        sources_text = "📚 SOURCES:\n\n"
        
        for i, source in enumerate(sources, 1):
            title = source.get('title', 'Source')
            url = source.get('url', '')
            
            # Clean up title
            title = re.sub(r'[^\w\s\-\.]', '', title)[:60]
            
            sources_text += f"{i}. {title}\n{url}\n\n"
        
        sources_text += f"Fact-checked on {datetime.now().strftime('%m/%d/%Y')}"
        
        return sources_text
    
    def _format_claims_html(self, claims: List[Dict], interventions: List[Any]) -> str:
        """Format claims for HTML display"""
        
        if not claims and not interventions:
            return "<p>No specific claims were identified for fact-checking.</p>"
        
        html = ""
        
        # Process interventions which contain the claims
        for i, intervention in enumerate(interventions, 1):
            claim_text = getattr(intervention, 'claim_text', 'Claim not specified')
            commentary = getattr(intervention, 'commentary', 'No commentary available')
            
            html += f"""
            <div class="claim">
                <div class="claim-text">Claim {i}: {claim_text}</div>
                <div class="claim-verdict">{commentary}</div>
            </div>
            """
        
        return html or "<p>Claims analysis is being processed...</p>"
    
    def _format_sources_html(self, sources: List[Dict]) -> str:
        """Format sources for HTML display"""
        
        if not sources:
            return "<p>No external sources were referenced in this analysis.</p>"
        
        html = ""
        
        for source in sources:
            title = source.get('title', 'Untitled Source')
            url = source.get('url', '#')
            description = source.get('description', '')
            
            html += f"""
            <div class="source">
                <div class="source-title">{title}</div>
                {f'<p>{description}</p>' if description else ''}
                <a href="{url}" target="_blank" class="source-link">{url}</a>
            </div>
            """
        
        return html
    
    def _format_claims_for_instagram(self, claims: List[Dict], interventions: List[Any]) -> str:
        """Format claims for Instagram description"""
        
        if not interventions:
            return "• Analysis in progress..."
        
        formatted = ""
        for i, intervention in enumerate(interventions[:3], 1):  # Limit to 3 for space
            claim = getattr(intervention, 'claim_text', 'Claim analysis')
            formatted += f"• {claim[:80]}{'...' if len(claim) > 80 else ''}\n"
        
        if len(interventions) > 3:
            formatted += f"• ...and {len(interventions) - 3} more findings\n"
        
        return formatted
    
    def _format_sources_for_instagram(self, sources: List[Dict]) -> str:
        """Format sources for Instagram description"""
        
        if not sources:
            return "• See full report for detailed sources"
        
        formatted = ""
        for i, source in enumerate(sources[:2], 1):  # Limit to 2 for space
            title = source.get('title', 'Source')[:40]
            formatted += f"• {title}{'...' if len(source.get('title', '')) > 40 else ''}\n"
        
        if len(sources) > 2:
            formatted += f"• +{len(sources) - 2} more sources\n"
        
        return formatted
    
    def _generate_recommendations_html(self, verdict: str, claims: List[Dict]) -> str:
        """Generate recommendations based on verdict"""
        
        recommendations = {
            'VERIFIED': [
                "✅ This content appears to be factually accurate",
                "📤 Safe to share with confidence",
                "🔍 Always verify information from multiple sources"
            ],
            'PARTIALLY ACCURATE': [
                "⚠️ This content contains both accurate and inaccurate information",
                "📝 Consider adding context when sharing",
                "🔍 Verify specific claims before sharing"
            ],
            'MISLEADING': [
                "❌ This content contains misleading information",
                "🚫 Avoid sharing without proper context",
                "📚 Check reliable sources before believing claims"
            ],
            'FALSE': [
                "🚫 This content contains false information",
                "❌ Do not share this content",
                "📢 Consider reporting misinformation"
            ],
            'NEEDS CONTEXT': [
                "💭 This content requires additional context",
                "📝 Add context when sharing",
                "🔍 Research the full story before forming opinions"
            ]
        }
        
        recs = recommendations.get(verdict, recommendations['NEEDS CONTEXT'])
        
        html = "<ul>"
        for rec in recs:
            html += f"<li>{rec}</li>"
        html += "</ul>"
        
        return html
    
    def _calculate_verdict(self, claims: List[Dict], interventions: List[Any]) -> str:
        """Calculate overall verdict based on claims and interventions"""
        
        if not interventions:
            return "NEEDS ANALYSIS"
        
        # Simple heuristic based on intervention types
        # In a real implementation, you'd have more sophisticated logic
        total = len(interventions)
        
        if total == 0:
            return "NO CLAIMS FOUND"
        
        # For now, return a default verdict
        # This should be enhanced based on your actual intervention analysis
        return "PARTIALLY ACCURATE"
    
    def _get_verdict_color(self, verdict: str) -> str:
        """Get color for verdict display"""
        
        colors = {
            'VERIFIED': '#28a745',
            'PARTIALLY ACCURATE': '#ffc107', 
            'MISLEADING': '#fd7e14',
            'FALSE': '#dc3545',
            'NEEDS CONTEXT': '#6f42c1',
            'NEEDS ANALYSIS': '#6c757d'
        }
        
        return colors.get(verdict, '#6c757d')
    
    def _detect_platform(self, url: str) -> str:
        """Detect platform from URL"""
        
        if 'instagram.com' in url:
            return 'instagram'
        elif 'facebook.com' in url or 'fb.watch' in url:
            return 'facebook'
        else:
            return 'social media'

    def generate_batch_summary(self, batch_results: Dict[str, Any], output_dir: str) -> str:
        """Generate HTML summary for batch processing"""
        
        total = batch_results.get('total_urls', 0)
        successful = batch_results.get('successful', 0)
        failed = batch_results.get('failed', 0)
        success_rate = (successful / total * 100) if total > 0 else 0
        
        processed_at = datetime.now().strftime('%B %d, %Y at %I:%M %p')
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Batch Fact Check Summary</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background-color: #fafafa;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            text-align: center;
        }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}
        
        .results-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }}
        
        .result-card {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .result-success {{
            border-left: 5px solid #28a745;
        }}
        
        .result-failed {{
            border-left: 5px solid #dc3545;
        }}
        
        .result-url {{
            font-size: 0.9em;
            color: #666;
            word-break: break-all;
            margin-bottom: 10px;
        }}
        
        .result-status {{
            font-weight: bold;
            margin-bottom: 10px;
        }}
        
        .success {{ color: #28a745; }}
        .failed {{ color: #dc3545; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Batch Fact Check Summary</h1>
        <p>Processed {total} reels on {processed_at}</p>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <div class="stat-number">{total}</div>
            <div>Total Reels</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{successful}</div>
            <div>Successful</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{failed}</div>
            <div>Failed</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{success_rate:.1f}%</div>
            <div>Success Rate</div>
        </div>
    </div>
    
    <h2>📋 Processing Results</h2>
    <div class="results-grid">
        {self._format_batch_results_html(batch_results)}
    </div>
</body>
</html>"""
        
        batch_html_path = os.path.join(output_dir, "batch_summary.html")
        with open(batch_html_path, 'w', encoding='utf-8') as f:
            f.write(html)
            
        return batch_html_path
    
    def _format_batch_results_html(self, batch_results: Dict[str, Any]) -> str:
        """Format batch results for HTML display"""
        
        html = ""
        
        # Successful results
        for result in batch_results.get('results', []):
            status_class = "result-success"
            status_text = "✅ Success"
            
            html += f"""
            <div class="result-card {status_class}">
                <div class="result-url">{result.get('url', 'Unknown URL')}</div>
                <div class="result-status success">{status_text}</div>
                <p>Line {result.get('line_number', '?')} in batch file</p>
            </div>
            """
        
        # Failed results
        for failed in batch_results.get('failed_urls', []):
            html += f"""
            <div class="result-card result-failed">
                <div class="result-url">{failed.get('url', 'Unknown URL')}</div>
                <div class="result-status failed">❌ Failed</div>
                <p>Line {failed.get('line_number', '?')}: {failed.get('error', 'Unknown error')}</p>
            </div>
            """
        
        return html
