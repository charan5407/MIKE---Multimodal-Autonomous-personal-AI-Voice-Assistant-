"""
Financial Analytics Package for MIKE.
Exports Stock Analyst, Candidate Shortlist, and Technical Indicator tools.
"""

from core.tools.finance.stock_tool import StockAnalystTool, StockShortlistTool
from core.tools.registry import tool_registry


def register_finance_tools():
    """Registers financial intelligence and stock analysis tools into central registry."""
    tools = [
        StockAnalystTool(),
        StockShortlistTool(),
    ]
    for tool in tools:
        tool_registry.register(tool)
