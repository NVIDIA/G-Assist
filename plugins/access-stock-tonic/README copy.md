# Structured Equity Product System

A comprehensive LangChain-based system for creating structured equity products using FINOS CDM (Common Domain Model) standards. This system combines natural language processing, stock discovery, financial analysis, and product structuring to create compliant financial products.

## 🏗️ System Architecture

The system consists of four specialized agents working in sequence, orchestrated by a **LangGraph state machine**:

### 1. Query Processor Agent
- **Purpose**: Converts natural language user queries into structured investment criteria
- **Input**: Natural language investment requests
- **Output**: Structured criteria (sectors, risk tolerance, investment horizon, etc.)
- **Example**: "I want conservative tech stocks for retirement" → Structured criteria

### 2. Stock Picker Agent
- **Purpose**: Discovers stocks based on criteria using yfinance screening
- **Input**: Structured investment criteria
- **Output**: List of relevant stock tickers and company information
- **Features**: Dynamic discovery, multiple screening criteria, ESG filtering

### 3. Analyzer Agent
- **Purpose**: Performs deep financial analysis on selected stocks
- **Input**: Stock tickers
- **Output**: Comprehensive analysis including signals, risk metrics, and predictions
- **Integration**: Uses MCP server for advanced analysis capabilities
- **Individual Summaries**: Generates detailed summaries for each analyzed stock

### 4. Summarizer Agent
- **Purpose**: Generates enhanced summaries using LangChain chat clients
- **Input**: Stock analysis and assessment data
- **Output**: Professional-grade summaries for individual stocks and portfolios
- **Features**: 
  - Individual stock summaries after each analysis
  - Portfolio-level summaries
  - Executive summaries
  - Risk analysis summaries
  - Investment recommendation summaries
  - LLM-powered summarization with fallback templates

### 5. Product Bundler Agent
- **Purpose**: Creates FINOS CDM-compliant structured equity products
- **Input**: Analysis results from Analyzer Agent
- **Output**: Structured financial products with CDM compliance
- **Standards**: Follows FINOS CDM 6.0.0 specifications

### 🎯 LangGraph State Machine
- **Purpose**: Orchestrates the complete workflow with state management
- **Features**: 
  - Prevents infinite loops with iteration limits
  - Ensures more stocks discovered than retained in final product
  - Supports user feedback and product modification
  - Configurable workflow parameters
  - Persistent state across iterations

## 🚀 Quick Start

### Prerequisites

- **Python 3.8 or higher**
- **Git** (for cloning the repository)
- **API Keys** (OpenAI, Anthropic, or HuggingFace)

### Installation

#### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/stock_picker.git
cd stock_picker
```

#### 2. Create Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

#### 3. Install Dependencies
```bash
# Upgrade pip
pip install --upgrade pip

# Install required packages
pip install -r requirements.txt
```

#### 4. Set Up Environment Variables
Create a `.env` file in the project root:

**Option A: Use the configuration setup script (Recommended)**
```bash
# Create a configuration template
python scripts/setup_config.py create

# Check your current configuration
python scripts/setup_config.py check
```

**Option B: Manual configuration**
```bash
# API Keys (get from respective providers)
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
HF_API_KEY=your_huggingface_api_key_here

# LLM Configuration
LLM_PROVIDER=anthropic  # Options: openai, anthropic, huggingface
OPENAI_MODEL=gpt-4
ANTHROPIC_MODEL=claude-3-opus-20240229
HF_MODEL=HuggingFaceH4/zephyr-7b-beta

# MCP Server Configuration (for stock analysis)
MCP_PROVIDER=huggingface
MCP_SERVER_URL=https://tonic-stock-predictions.hf.space/mcp/sse
```

**Configuration Examples:**

1. **Anthropic LLM + HuggingFace MCP** (Recommended)
   ```bash
   LLM_PROVIDER=anthropic
   ANTHROPIC_API_KEY=your_anthropic_key
   HF_API_KEY=your_hf_key_for_mcp
   ```

2. **OpenAI LLM + HuggingFace MCP**
   ```bash
   LLM_PROVIDER=openai
   OPENAI_API_KEY=your_openai_key
   HF_API_KEY=your_hf_key_for_mcp
   ```

3. **HuggingFace LLM + HuggingFace MCP**
   ```bash
   LLM_PROVIDER=huggingface
   HF_API_KEY=your_hf_key_for_both
   ```

#### 5. Verify Installation
```bash
# Test that all packages are installed correctly
python -c "import langchain; import yfinance; import gradio; print('✅ All packages installed successfully!')"
```

### Basic Usage

#### Individual Agents
```python
from src.agents import QueryProcessorAgent, StockPickerAgent, AnalyzerAgent, ProductBundlerAgent

# Initialize agents
query_processor = QueryProcessorAgent()
stock_picker = StockPickerAgent()
analyzer = AnalyzerAgent()
product_bundler = ProductBundlerAgent(openai_api_key="your-key")

# Process user query
user_query = "I want a conservative portfolio of large-cap technology stocks for retirement"
processed_query = query_processor.process_query(user_query)

# Discover stocks
stocks = stock_picker.pick_stocks(processed_query.to_stock_picker_query(), limit=10)

# Analyze stocks (requires MCP server)
analysis_results = analyzer.analyze_stocks([stock['symbol'] for stock in stocks])

# Create structured product
product_bundle = product_bundler.bundle_product(analysis_results)
```

#### LangGraph Workflow (Recommended)
```python
from src.workflow import StructuredEquityWorkflow, DEFAULT_CONFIG

# Initialize workflow
workflow = StructuredEquityWorkflow(openai_api_key="your-key", config=DEFAULT_CONFIG)

# Run complete workflow
result = workflow.run("I want a conservative portfolio of tech stocks for retirement")

if result["success"]:
    product_bundle = result["product_bundle"]
    print(f"Product created with {len(product_bundle['product']['components'])} components")
```

### Running the Application

#### Option 1: Gradio Web Interface (Recommended)
```bash
# Make sure virtual environment is activated
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run the Gradio web app
python gradio_app.py
```

The application will be available at:
- **Local**: http://localhost:7860
- **Network**: http://your-ip:7860

#### Option 2: Command Line Interface
```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run example script
python example_prompt_based_system.py
```

#### Option 3: Jupyter Notebook
```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Jupyter (if not already installed)
pip install jupyter

# Start Jupyter
jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser
```

Access at: http://localhost:8888

## 📋 Agent Details

### Query Processor Agent

Extracts structured criteria from natural language:

```python
# Supported criteria
- sectors: List of target sectors
- industries: List of target industries  
- markets: Target markets (US, international, etc.)
- countries: Specific countries
- market_cap_range: Market capitalization range
- risk_tolerance: low/moderate/high
- investment_horizon: short/medium/long
- capital_amount: Investment amount
- esg_focus: ESG requirements
- dividend_focus: Dividend preferences
- growth_focus: Growth vs value preference
- limit: Maximum number of stocks
```

### Stock Picker Agent

Uses yfinance for dynamic stock discovery:

```python
# Screening capabilities
- Geographic screening (US, international markets)
- Sector and industry filtering
- Market cap filtering
- ESG screening
- Dividend yield filtering
- Volatility and risk filtering
```

### Analyzer Agent

Performs comprehensive financial analysis:

```python
# Analysis components
- Technical signals (RSI, MACD, Bollinger Bands)
- Risk metrics (Sharpe ratio, VaR, volatility)
- Fundamental metrics (P/E, market cap, dividend yield)
- Sector analysis
- Ensemble predictions
- Confidence scoring
```

### Summarizer Agent

Generates enhanced summaries using LangChain chat clients:

```python
# Features
- Individual stock summaries after each analysis
- Portfolio-level summaries
- Executive summaries
- Risk analysis summaries
- Investment recommendation summaries
- LLM-powered summarization with fallback templates
```

### Product Bundler Agent

Creates CDM-compliant structured products:

```python
# CDM Product Types
- CONSERVATIVE_EQUITY_BASKET
- BALANCED_EQUITY_BASKET  
- AGGRESSIVE_EQUITY_BASKET

# CDM Compliance Features
- Product model compliance
- Event model integration
- Legal agreement standards
- Reference data model alignment
```

## 🎯 LangGraph Workflow Configuration

The system provides three pre-configured workflow settings:

### Default Configuration
```python
from src.workflow import DEFAULT_CONFIG

# Balanced approach
- Max iterations: 3
- Base stock limit: 30
- Max stocks per iteration: 50
- Min stocks for product: 5
- Max stocks for product: 20
```

### Conservative Configuration
```python
from src.workflow import CONSERVATIVE_CONFIG

# Risk-averse approach
- Max iterations: 2
- Base stock limit: 25
- Max stocks per iteration: 30
- Min stocks for product: 8
- Max stocks for product: 15
```

### Aggressive Configuration
```python
from src.workflow import AGGRESSIVE_CONFIG

# Growth-focused approach
- Max iterations: 4
- Base stock limit: 40
- Max stocks per iteration: 60
- Min stocks for product: 3
- Max stocks for product: 25
```

## 🔧 Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `ANTHROPIC_API_KEY` | Anthropic API key | Optional |
| `HF_API_KEY` | HuggingFace API key | Optional |
| `LLM_PROVIDER` | LLM provider (openai/anthropic/huggingface) | `openai` |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4` |
| `ANTHROPIC_MODEL` | Anthropic model name | `claude-3-opus-20240229` |
| `HF_MODEL` | HuggingFace model name | `HuggingFaceH4/zephyr-7b-beta` |

### Model Selection

You can specify different models for each provider:

```bash
# Use GPT-4 Turbo
export OPENAI_MODEL=gpt-4-turbo

# Use Claude 3 Haiku (faster, cheaper)
export ANTHROPIC_MODEL=claude-3-haiku-20240307

# Use a different HuggingFace model
export HF_MODEL=meta-llama/Llama-2-7b-chat-hf
```

## 🧪 Testing

### Run Tests
```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run all tests
python -m pytest tests/

# Run specific test
python -m pytest tests/test_agents.py
```

### Test Individual Components
```bash
# Test query processor
python -c "
from src.agents.query_processor_agent import QueryProcessorAgent
agent = QueryProcessorAgent()
result = agent.process_query('I want 10 tech stocks for $50,000')
print(result)
"

# Test stock picker
python -c "
from src.agents.stock_picker_agent import StockPickerAgent
agent = StockPickerAgent()
stocks = agent.pick_stocks('technology large cap', limit=5)
print(stocks)
"
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Import Errors
```bash
# Make sure virtual environment is activated
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Reinstall packages
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

#### 2. API Key Issues
```bash
# Check if environment variables are set
echo $OPENAI_API_KEY  # On Windows: echo %OPENAI_API_KEY%

# Load from .env file
source .env  # On Windows PowerShell: Get-Content .env | ForEach-Object { if($_ -match "^([^#][^=]+)=(.*)$") { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process") } }
```

#### 3. Memory Issues
```bash
# Increase virtual environment memory
# On Windows: Increase VM memory in hypervisor settings
# On Linux: Add swap space
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

#### 4. Network Issues
```bash
# Check internet connection
ping google.com

# Check API access
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
```

### Performance Optimization

#### 1. Use Faster Models
```bash
# For development/testing
export OPENAI_MODEL=gpt-3.5-turbo
export ANTHROPIC_MODEL=claude-3-haiku-20240307
```

#### 2. Enable Caching
```python
# Enable result caching in your code
import os
os.environ["LANGCHAIN_CACHE"] = "true"
```

#### 3. Optimize VM Settings
- Increase CPU cores (4+ recommended)
- Increase RAM (8GB+ recommended)
- Use SSD storage
- Enable virtualization in BIOS

## 📚 API Documentation

### Query Processor Agent
```python
class QueryProcessorAgent:
    def process_query(self, user_query: str) -> ProcessedQuery:
        """Process natural language query into structured criteria."""
        
    def to_stock_picker_query(self, processed_query: ProcessedQuery) -> str:
        """Convert processed query to stock picker format."""
```

### Stock Picker Agent
```python
class StockPickerAgent:
    def pick_stocks(self, query: str, limit: int = 10) -> List[Dict]:
        """Discover stocks based on query criteria."""
```

### Analyzer Agent
```python
class AnalyzerAgent:
    def analyze_stocks(self, symbols: List[str]) -> List[Dict]:
        """Analyze stocks using MCP server."""
```

### Summarizer Agent
```python
class SummarizerAgent:
    def generate_summary(self, analysis_data: Dict) -> str:
        """Generate a professional-grade summary for a stock or portfolio."""
```

### Product Bundler Agent
```python
class ProductBundlerAgent:
    def bundle_product(self, analysis_results: List[Dict]) -> Dict:
        """Create CDM-compliant structured product."""
```

## 🤝 Contributing

### Development Setup
```bash
# Clone repository
git clone https://github.com/yourusername/stock_picker.git
cd stock_picker

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # If available

# Install pre-commit hooks
pre-commit install
```

### Code Style
```bash
# Format code
black src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_agents.py
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **LangChain** for the AI framework
- **LangGraph** for workflow orchestration
- **yfinance** for financial data
- **FINOS** for CDM standards
- **OpenAI/Anthropic/HuggingFace** for LLM capabilities

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/stock_picker/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/stock_picker/discussions)
- **Documentation**: [Wiki](https://github.com/yourusername/stock_picker/wiki)

---

**Note**: Always activate your virtual environment before running the application:
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
``` 