"""
Configuration for the LangGraph Structured Equity Workflow
"""

from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class WorkflowConfig:
    """Configuration for the structured equity workflow."""
    
    # Workflow settings
    max_iterations: int = 3
    max_stocks_per_iteration: int = 50
    min_stocks_for_product: int = 5
    max_stocks_for_product: int = 20
    
    # Stock discovery settings
    base_stock_limit: int = 30
    iteration_stock_increase: int = 10
    
    # Analysis settings
    analysis_timeout: int = 300  # seconds
    max_concurrent_analyses: int = 10
    
    # Product bundling settings
    default_notional_amount: float = 100000.0
    default_currency: str = "USD"
    default_maturity_days: int = 365
    
    # User feedback settings
    enable_interactive_feedback: bool = True
    auto_accept_after_iterations: int = 3
    
    # CDM compliance settings
    cdm_version: str = "6.0.0"
    compliance_level: str = "FULL"
    
    # Logging settings
    log_level: str = "INFO"
    enable_workflow_logging: bool = True
    
    # Performance settings
    enable_caching: bool = True
    cache_ttl: int = 3600  # seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "max_iterations": self.max_iterations,
            "max_stocks_per_iteration": self.max_stocks_per_iteration,
            "min_stocks_for_product": self.min_stocks_for_product,
            "max_stocks_for_product": self.max_stocks_for_product,
            "base_stock_limit": self.base_stock_limit,
            "iteration_stock_increase": self.iteration_stock_increase,
            "analysis_timeout": self.analysis_timeout,
            "max_concurrent_analyses": self.max_concurrent_analyses,
            "default_notional_amount": self.default_notional_amount,
            "default_currency": self.default_currency,
            "default_maturity_days": self.default_maturity_days,
            "enable_interactive_feedback": self.enable_interactive_feedback,
            "auto_accept_after_iterations": self.auto_accept_after_iterations,
            "cdm_version": self.cdm_version,
            "compliance_level": self.compliance_level,
            "log_level": self.log_level,
            "enable_workflow_logging": self.enable_workflow_logging,
            "enable_caching": self.enable_caching,
            "cache_ttl": self.cache_ttl
        }
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'WorkflowConfig':
        """Create config from dictionary."""
        return cls(**config_dict)
    
    @classmethod
    def get_default_config(cls) -> 'WorkflowConfig':
        """Get default configuration."""
        return cls()
    
    @classmethod
    def get_conservative_config(cls) -> 'WorkflowConfig':
        """Get conservative configuration for risk-averse users."""
        config = cls()
        config.max_iterations = 2
        config.max_stocks_per_iteration = 30
        config.min_stocks_for_product = 8
        config.max_stocks_for_product = 15
        config.base_stock_limit = 25
        config.auto_accept_after_iterations = 2
        return config
    
    @classmethod
    def get_aggressive_config(cls) -> 'WorkflowConfig':
        """Get aggressive configuration for growth-focused users."""
        config = cls()
        config.max_iterations = 4
        config.max_stocks_per_iteration = 60
        config.min_stocks_for_product = 3
        config.max_stocks_for_product = 25
        config.base_stock_limit = 40
        config.iteration_stock_increase = 15
        config.auto_accept_after_iterations = 4
        return config

# Predefined configurations
DEFAULT_CONFIG = WorkflowConfig.get_default_config()
CONSERVATIVE_CONFIG = WorkflowConfig.get_conservative_config()
AGGRESSIVE_CONFIG = WorkflowConfig.get_aggressive_config()

# Configuration presets
CONFIG_PRESETS = {
    "default": DEFAULT_CONFIG,
    "conservative": CONSERVATIVE_CONFIG,
    "aggressive": AGGRESSIVE_CONFIG
} 