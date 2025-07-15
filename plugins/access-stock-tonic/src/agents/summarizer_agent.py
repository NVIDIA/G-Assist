"""
Summarizer Agent for generating enhanced summaries using LangChain chat clients.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

try:
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
    from langchain.prompts import ChatPromptTemplate
    from langchain.schema import HumanMessage, SystemMessage
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("Warning: LangChain not available. Summarizer agent will use fallback methods.")

from ..prompts.summarizer_prompts import (
    STOCK_SUMMARY_PROMPT,
    PORTFOLIO_SUMMARY_PROMPT,
    EXECUTIVE_SUMMARY_PROMPT,
    RISK_SUMMARY_PROMPT,
    RECOMMENDATION_SUMMARY_PROMPT
)

class SummarizerAgent:
    """
    Summarizer Agent that uses LangChain chat clients to generate enhanced summaries
    from analyzer assessments and product bundle data.
    """
    
    def __init__(self, 
                 openai_api_key: Optional[str] = None,
                 anthropic_api_key: Optional[str] = None,
                 use_llm: bool = True,
                 llm_provider: str = "openai",
                 openai_model: str = "gpt-4",
                 anthropic_model: str = "claude-3-opus-20240229",
                 temperature: float = 0.3):
        """
        Initialize the Summarizer Agent.
        
        Args:
            openai_api_key: OpenAI API key
            anthropic_api_key: Anthropic API key
            use_llm: Whether to use LLM for summarization
            llm_provider: LLM provider ("openai" or "anthropic")
            openai_model: OpenAI model name
            anthropic_model: Anthropic model name
            temperature: Temperature for LLM generation
        """
        self.logger = logging.getLogger(__name__)
        self.use_llm = use_llm and LLM_AVAILABLE and (openai_api_key or anthropic_api_key)
        self.llm_provider = llm_provider
        self.temperature = temperature
        
        # Initialize LLM client
        self.llm_client = None
        if self.use_llm:
            self._initialize_llm_client(
                openai_api_key, anthropic_api_key, 
                openai_model, anthropic_model
            )
        
        self.logger.info(f"SummarizerAgent initialized with LLM: {self.use_llm}")
    
    def _initialize_llm_client(self, openai_api_key: str, anthropic_api_key: str,
                              openai_model: str, anthropic_model: str):
        """Initialize the LLM client based on provider."""
        try:
            if self.llm_provider == "openai" and openai_api_key:
                self.llm_client = ChatOpenAI(
                    openai_api_key=openai_api_key,
                    model_name=openai_model,
                    temperature=self.temperature
                )
                self.logger.info(f"Initialized OpenAI client with model: {openai_model}")
            
            elif self.llm_provider == "anthropic" and anthropic_api_key:
                try:
                    self.llm_client = ChatAnthropic(
                        anthropic_api_key=anthropic_api_key,
                        model=anthropic_model,
                        temperature=self.temperature
                    )
                    self.logger.info(f"Initialized Anthropic client with model: {anthropic_model}")
                except AttributeError as e:
                    if "count_tokens" in str(e):
                        self.logger.warning("Anthropic client version issue detected, falling back to template-based summarization")
                        self.use_llm = False
                        return
                    else:
                        raise e
            
            else:
                self.logger.warning("No valid API key provided, falling back to template-based summarization")
                self.use_llm = False
                
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM client: {e}")
            self.use_llm = False
    
    def generate_stock_summary(self, stock_data: Dict[str, Any]) -> str:
        """
        Generate an enhanced summary for a single stock.
        
        Args:
            stock_data: Stock analysis and assessment data
            
        Returns:
            Enhanced stock summary
        """
        try:
            print(f"[SUMMARIZER DEBUG] Starting generate_stock_summary")
            print(f"[SUMMARIZER DEBUG] Stock data keys: {list(stock_data.keys())}")
            print(f"[SUMMARIZER DEBUG] Stock data has 'symbol': {'symbol' in stock_data}")
            print(f"[SUMMARIZER DEBUG] Stock data has 'assessment': {'assessment' in stock_data}")
            print(f"[SUMMARIZER DEBUG] Stock data has 'analysis': {'analysis' in stock_data}")
            print(f"[SUMMARIZER DEBUG] Stock data has 'price_data': {'price_data' in stock_data}")
            
            symbol = stock_data.get('symbol', 'Unknown')
            print(f"[SUMMARIZER DEBUG] Processing symbol: {symbol}")
            
            assessment = stock_data.get('assessment', {})
            analysis = stock_data.get('analysis', {})
            price_data = stock_data.get('price_data', {})
            
            print(f"[SUMMARIZER DEBUG] Assessment keys: {list(assessment.keys()) if assessment else 'None'}")
            print(f"[SUMMARIZER DEBUG] Analysis keys: {list(analysis.keys()) if analysis else 'None'}")
            print(f"[SUMMARIZER DEBUG] Price data keys: {list(price_data.keys()) if price_data else 'None'}")
            
            # Extract key information
            recommendation = assessment.get('investment_recommendation', {})
            risk = assessment.get('risk_assessment', {})
            confidence = assessment.get('confidence_score', {})
            suitability = assessment.get('suitability_score', {})
            insights = assessment.get('insights', {})
            text_assessment = assessment.get('text_assessment', '')
            
            print(f"[SUMMARIZER DEBUG] Recommendation: {recommendation}")
            print(f"[SUMMARIZER DEBUG] Risk: {risk}")
            print(f"[SUMMARIZER DEBUG] Confidence: {confidence}")
            print(f"[SUMMARIZER DEBUG] Suitability: {suitability}")
            print(f"[SUMMARIZER DEBUG] Text assessment length: {len(text_assessment) if text_assessment else 0}")
            
            # Extract price information and handle None values
            current_price = price_data.get('current_price')
            predicted_price = price_data.get('predicted_price')
            current_date = price_data.get('current_date')
            predicted_date = price_data.get('predicted_date')
            price_change = price_data.get('price_change')
            price_change_pct = price_data.get('price_change_pct')
            
            print(f"[SUMMARIZER DEBUG] Price data extracted:")
            print(f"[SUMMARIZER DEBUG]   current_price: {current_price}")
            print(f"[SUMMARIZER DEBUG]   predicted_price: {predicted_price}")
            print(f"[SUMMARIZER DEBUG]   current_date: {current_date}")
            print(f"[SUMMARIZER DEBUG]   predicted_date: {predicted_date}")
            print(f"[SUMMARIZER DEBUG]   price_change: {price_change}")
            print(f"[SUMMARIZER DEBUG]   price_change_pct: {price_change_pct}")
            
            # Prepare context for LLM with safe formatting
            context = {
                'symbol': symbol,
                'recommendation': recommendation.get('recommendation', 'HOLD'),
                'recommendation_strength': recommendation.get('strength', 'MEDIUM'),
                'recommendation_score': recommendation.get('score', 0.5),
                'risk_level': risk.get('risk_level', 'MODERATE'),
                'risk_score': risk.get('risk_score', 0.5),
                'confidence_level': confidence.get('confidence_level', 'MEDIUM'),
                'confidence_score': confidence.get('confidence_score', 0.5),
                'suitability_level': suitability.get('suitability_level', 'GOOD'),
                'suitability_score': suitability.get('suitability_score', 0.5),
                'text_assessment': text_assessment,
                'insights': insights,
                # Handle None values for price formatting
                'current_price': current_price if current_price is not None else 0.0,
                'predicted_price': predicted_price if predicted_price is not None else 0.0,
                'current_date': current_date if current_date is not None else 'Unknown',
                'predicted_date': predicted_date if predicted_date is not None else 'Unknown',
                'price_change': price_change if price_change is not None else 0.0,
                'price_change_pct': price_change_pct if price_change_pct is not None else 0.0
            }
            
            print(f"[SUMMARIZER DEBUG] Context prepared with keys: {list(context.keys())}")
            
            # Generate dynamic price analysis section
            if current_price and current_price > 0 and predicted_price and predicted_price > 0:
                price_analysis = f"""
- **Current Price**: ${current_price:.2f} (as of {current_date})
- **Predicted Price**: ${predicted_price:.2f} (target date: {predicted_date})
- **Expected Change**: ${price_change:.2f} ({price_change_pct:+.1f}%)
- **Price Trend**: {'Bullish' if price_change > 0 else 'Bearish' if price_change < 0 else 'Neutral'} movement expected
"""
                print(f"[SUMMARIZER DEBUG] Generated price analysis with actual prices")
            else:
                price_analysis = "- **Price Data**: Historical and predicted price data not available"
                print(f"[SUMMARIZER DEBUG] No valid price data available")
            
            context['price_analysis_section'] = price_analysis
            
            if self.use_llm and self.llm_client:
                print(f"[SUMMARIZER DEBUG] Using LLM for summary generation")
                return self._generate_llm_summary(STOCK_SUMMARY_PROMPT, context)
            else:
                print(f"[SUMMARIZER DEBUG] Using template for summary generation")
                return self._generate_template_summary(context)
                
        except Exception as e:
            print(f"[SUMMARIZER DEBUG] Error in generate_stock_summary: {e}")
            import traceback
            print(f"[SUMMARIZER DEBUG] Error traceback: {traceback.format_exc()}")
            self.logger.error(f"Error generating stock summary for {stock_data.get('symbol', 'Unknown')}: {e}")
            return f"Summary generation failed for {stock_data.get('symbol', 'Unknown')}: {str(e)}"
    
    def generate_portfolio_summary(self, portfolio_data: Dict[str, Any]) -> str:
        """
        Generate an enhanced portfolio-level summary.
        
        Args:
            portfolio_data: Portfolio analysis and assessment data
            
        Returns:
            Enhanced portfolio summary
        """
        try:
            print(f"[SUMMARIZER DEBUG] Starting generate_portfolio_summary")
            print(f"[SUMMARIZER DEBUG] Portfolio data keys: {list(portfolio_data.keys())}")
            
            # Extract portfolio information
            assessment_summary = portfolio_data.get('assessment_summary', {})
            product_summary = portfolio_data.get('product_summary', '')
            individual_assessments = portfolio_data.get('individual_assessments', [])
            user_preferences = portfolio_data.get('user_preferences', {})
            product = portfolio_data.get('product', {})
            
            print(f"[SUMMARIZER DEBUG] Assessment summary keys: {list(assessment_summary.keys()) if assessment_summary else 'None'}")
            print(f"[SUMMARIZER DEBUG] Individual assessments count: {len(individual_assessments)}")
            print(f"[SUMMARIZER DEBUG] User preferences keys: {list(user_preferences.keys()) if user_preferences else 'None'}")
            print(f"[SUMMARIZER DEBUG] Product keys: {list(product.keys()) if product else 'None'}")
            
            # Get the correct total stocks count from product components
            components = product.get('components', [])
            total_stocks = len(components)
            
            print(f"[SUMMARIZER DEBUG] Total stocks from components: {total_stocks}")
            
            # Prepare context for LLM
            context = {
                'total_stocks': total_stocks,
                'avg_confidence': assessment_summary.get('avg_confidence_score', 0.5),
                'avg_suitability': assessment_summary.get('avg_suitability_score', 0.5),
                'avg_recommendation': assessment_summary.get('avg_recommendation_score', 0.5),
                'risk_distribution': assessment_summary.get('risk_distribution', {}),
                'recommendation_distribution': assessment_summary.get('recommendation_distribution', {}),
                'product_summary': product_summary,
                'individual_assessments': individual_assessments,
                'user_preferences': user_preferences,
                'product_type': product.get('product_type', 'UNKNOWN'),
                'notional_amount': product.get('notional_amount', 100000.0)
            }
            
            print(f"[SUMMARIZER DEBUG] Context prepared with keys: {list(context.keys())}")
            print(f"[SUMMARIZER DEBUG] Risk distribution: {context['risk_distribution']}")
            print(f"[SUMMARIZER DEBUG] Recommendation distribution: {context['recommendation_distribution']}")
            
            if self.use_llm and self.llm_client:
                print(f"[SUMMARIZER DEBUG] Using LLM for portfolio summary generation")
                return self._generate_llm_summary(PORTFOLIO_SUMMARY_PROMPT, context)
            else:
                print(f"[SUMMARIZER DEBUG] Using template for portfolio summary generation")
                return self._generate_template_portfolio_summary(context)
                
        except Exception as e:
            print(f"[SUMMARIZER DEBUG] Error in generate_portfolio_summary: {e}")
            import traceback
            print(f"[SUMMARIZER DEBUG] Error traceback: {traceback.format_exc()}")
            self.logger.error(f"Error generating portfolio summary: {e}")
            return f"Portfolio summary generation failed: {str(e)}"
    
    def generate_executive_summary(self, portfolio_data: Dict[str, Any]) -> str:
        """
        Generate an executive summary for the portfolio.
        
        Args:
            portfolio_data: Portfolio analysis and assessment data
            
        Returns:
            Executive summary
        """
        try:
            print(f"[SUMMARIZER DEBUG] Starting generate_executive_summary")
            print(f"[SUMMARIZER DEBUG] Portfolio data keys: {list(portfolio_data.keys())}")
            
            # Extract key metrics
            assessment_summary = portfolio_data.get('assessment_summary', {})
            user_preferences = portfolio_data.get('user_preferences', {})
            product = portfolio_data.get('product', {})
            
            print(f"[SUMMARIZER DEBUG] Assessment summary keys: {list(assessment_summary.keys()) if assessment_summary else 'None'}")
            print(f"[SUMMARIZER DEBUG] User preferences keys: {list(user_preferences.keys()) if user_preferences else 'None'}")
            print(f"[SUMMARIZER DEBUG] Product keys: {list(product.keys()) if product else 'None'}")
            
            context = {
                'avg_confidence': assessment_summary.get('avg_confidence_score', 0.5),
                'avg_suitability': assessment_summary.get('avg_suitability_score', 0.5),
                'avg_recommendation': assessment_summary.get('avg_recommendation_score', 0.5),
                'risk_distribution': assessment_summary.get('risk_distribution', {}),
                'recommendation_distribution': assessment_summary.get('recommendation_distribution', {}),
                'risk_tolerance': user_preferences.get('risk_tolerance', 'moderate'),
                'investment_horizon': user_preferences.get('investment_horizon', 'long'),
                'capital_amount': product.get('notional_amount', 100000.0),
                'product_type': product.get('product_type', 'UNKNOWN'),
                'total_components': len(product.get('components', []))
            }
            
            print(f"[SUMMARIZER DEBUG] Context prepared with keys: {list(context.keys())}")
            print(f"[SUMMARIZER DEBUG] Risk distribution: {context['risk_distribution']}")
            print(f"[SUMMARIZER DEBUG] Recommendation distribution: {context['recommendation_distribution']}")
            
            if self.use_llm and self.llm_client:
                print(f"[SUMMARIZER DEBUG] Using LLM for executive summary generation")
                return self._generate_llm_summary(EXECUTIVE_SUMMARY_PROMPT, context)
            else:
                print(f"[SUMMARIZER DEBUG] Using template for executive summary generation")
                return self._generate_template_executive_summary(context)
                
        except Exception as e:
            print(f"[SUMMARIZER DEBUG] Error in generate_executive_summary: {e}")
            import traceback
            print(f"[SUMMARIZER DEBUG] Error traceback: {traceback.format_exc()}")
            self.logger.error(f"Error generating executive summary: {e}")
            return f"Executive summary generation failed: {str(e)}"
    
    def generate_risk_summary(self, portfolio_data: Dict[str, Any]) -> str:
        """
        Generate a detailed risk summary for the portfolio.
        
        Args:
            portfolio_data: Portfolio analysis and assessment data
            
        Returns:
            Risk summary
        """
        try:
            print(f"[SUMMARIZER DEBUG] Starting generate_risk_summary")
            print(f"[SUMMARIZER DEBUG] Portfolio data keys: {list(portfolio_data.keys())}")
            
            assessment_summary = portfolio_data.get('assessment_summary', {})
            individual_assessments = portfolio_data.get('individual_assessments', [])
            user_preferences = portfolio_data.get('user_preferences', {})
            product = portfolio_data.get('product', {})
            
            print(f"[SUMMARIZER DEBUG] Assessment summary keys: {list(assessment_summary.keys()) if assessment_summary else 'None'}")
            print(f"[SUMMARIZER DEBUG] Individual assessments count: {len(individual_assessments)}")
            print(f"[SUMMARIZER DEBUG] User preferences keys: {list(user_preferences.keys()) if user_preferences else 'None'}")
            print(f"[SUMMARIZER DEBUG] Product keys: {list(product.keys()) if product else 'None'}")
            
            # Get the correct total stocks count from product components
            components = product.get('components', [])
            total_stocks = len(components)
            
            print(f"[SUMMARIZER DEBUG] Total stocks from components: {total_stocks}")
            
            context = {
                'risk_distribution': assessment_summary.get('risk_distribution', {}),
                'individual_assessments': individual_assessments,
                'risk_tolerance': user_preferences.get('risk_tolerance', 'moderate'),
                'total_stocks': total_stocks
            }
            
            print(f"[SUMMARIZER DEBUG] Context prepared with keys: {list(context.keys())}")
            print(f"[SUMMARIZER DEBUG] Risk distribution: {context['risk_distribution']}")
            
            if self.use_llm and self.llm_client:
                print(f"[SUMMARIZER DEBUG] Using LLM for risk summary generation")
                return self._generate_llm_summary(RISK_SUMMARY_PROMPT, context)
            else:
                print(f"[SUMMARIZER DEBUG] Using template for risk summary generation")
                return self._generate_template_risk_summary(context)
                
        except Exception as e:
            print(f"[SUMMARIZER DEBUG] Error in generate_risk_summary: {e}")
            import traceback
            print(f"[SUMMARIZER DEBUG] Error traceback: {traceback.format_exc()}")
            self.logger.error(f"Error generating risk summary: {e}")
            return f"Risk summary generation failed: {str(e)}"
    
    def generate_recommendation_summary(self, portfolio_data: Dict[str, Any]) -> str:
        """
        Generate a recommendation summary for the portfolio.
        
        Args:
            portfolio_data: Portfolio analysis and assessment data
            
        Returns:
            Recommendation summary
        """
        try:
            print(f"[SUMMARIZER DEBUG] Starting generate_recommendation_summary")
            print(f"[SUMMARIZER DEBUG] Portfolio data keys: {list(portfolio_data.keys())}")
            
            assessment_summary = portfolio_data.get('assessment_summary', {})
            individual_assessments = portfolio_data.get('individual_assessments', [])
            user_preferences = portfolio_data.get('user_preferences', {})
            product = portfolio_data.get('product', {})
            
            print(f"[SUMMARIZER DEBUG] Assessment summary keys: {list(assessment_summary.keys()) if assessment_summary else 'None'}")
            print(f"[SUMMARIZER DEBUG] Individual assessments count: {len(individual_assessments)}")
            print(f"[SUMMARIZER DEBUG] User preferences keys: {list(user_preferences.keys()) if user_preferences else 'None'}")
            print(f"[SUMMARIZER DEBUG] Product keys: {list(product.keys()) if product else 'None'}")
            
            # Get the correct total stocks count from product components
            components = product.get('components', [])
            total_stocks = len(components)
            
            print(f"[SUMMARIZER DEBUG] Total stocks from components: {total_stocks}")
            
            context = {
                'recommendation_distribution': assessment_summary.get('recommendation_distribution', {}),
                'avg_recommendation': assessment_summary.get('avg_recommendation_score', 0.5),
                'individual_assessments': individual_assessments,
                'risk_tolerance': user_preferences.get('risk_tolerance', 'moderate'),
                'investment_horizon': user_preferences.get('investment_horizon', 'long'),
                'total_stocks': total_stocks
            }
            
            print(f"[SUMMARIZER DEBUG] Context prepared with keys: {list(context.keys())}")
            print(f"[SUMMARIZER DEBUG] Recommendation distribution: {context['recommendation_distribution']}")
            
            if self.use_llm and self.llm_client:
                print(f"[SUMMARIZER DEBUG] Using LLM for recommendation summary generation")
                return self._generate_llm_summary(RECOMMENDATION_SUMMARY_PROMPT, context)
            else:
                print(f"[SUMMARIZER DEBUG] Using template for recommendation summary generation")
                return self._generate_template_recommendation_summary(context)
                
        except Exception as e:
            print(f"[SUMMARIZER DEBUG] Error in generate_recommendation_summary: {e}")
            import traceback
            print(f"[SUMMARIZER DEBUG] Error traceback: {traceback.format_exc()}")
            self.logger.error(f"Error generating recommendation summary: {e}")
            return f"Recommendation summary generation failed: {str(e)}"
    
    def _generate_llm_summary(self, prompt_template: str, context: Dict[str, Any]) -> str:
        """Generate summary using LLM."""
        try:
            # Format the prompt with context
            formatted_prompt = prompt_template.format(**context)
            
            # Create messages
            messages = [
                SystemMessage(content="You are a professional financial analyst and investment advisor. Provide clear, concise, and accurate summaries based on the provided data."),
                HumanMessage(content=formatted_prompt)
            ]
            
            # Generate response
            response = self.llm_client.invoke(messages)
            return response.content.strip()
            
        except Exception as e:
            self.logger.error(f"LLM summary generation failed: {e}")
            return self._generate_fallback_summary(context)
    
    def _generate_template_summary(self, context: Dict[str, Any]) -> str:
        """Generate template-based stock summary."""
        symbol = context['symbol']
        recommendation = context['recommendation']
        risk_level = context['risk_level']
        confidence = context['confidence_score']
        
        # Extract price data
        current_price = context.get('current_price')
        predicted_price = context.get('predicted_price')
        current_date = context.get('current_date')
        predicted_date = context.get('predicted_date')
        price_change = context.get('price_change')
        price_change_pct = context.get('price_change_pct')
        
        summary = f"""
# {symbol} Investment Summary

## Key Metrics
- **Recommendation**: {recommendation} (Score: {context['recommendation_score']:.1%})
- **Risk Level**: {risk_level} (Score: {context['risk_score']:.1%})
- **Confidence**: {context['confidence_level']} ({confidence:.1%})
- **Suitability**: {context['suitability_level']} ({context['suitability_score']:.1%})
"""
        
        # Add price analysis if available
        if current_price and current_price > 0 and predicted_price and predicted_price > 0:
            summary += f"""
## Price Analysis
- **Current Price**: ${current_price:.2f} (as of {current_date})
- **Predicted Price**: ${predicted_price:.2f} (target: {predicted_date})
- **Expected Change**: ${price_change:.2f} ({price_change_pct:+.1f}%)
- **Price Trend**: {'Bullish' if price_change > 0 else 'Bearish' if price_change < 0 else 'Neutral'} movement expected

"""
        else:
            summary += f"""
## Price Analysis
- **Price Data**: Historical and predicted price data not available

"""
        
        summary += f"""
## Assessment
Based on the analysis, {symbol} presents a {recommendation.lower().replace('_', ' ')} opportunity with {context['recommendation_strength'].lower()} conviction. 
The stock shows a {risk_level.lower()} risk profile and is {context['suitability_level'].lower()} suitable for the target investor profile.

## Key Insights
{self._format_insights(context['insights'])}

## Conclusion
{symbol} represents a {recommendation.lower().replace('_', ' ')} opportunity with {context['confidence_level'].lower()} confidence 
and {context['suitability_level'].lower()} suitability for the specified investment criteria.
"""
        return summary.strip()
    
    def _generate_template_portfolio_summary(self, context: Dict[str, Any]) -> str:
        """Generate template-based portfolio summary."""
        total_stocks = context['total_stocks']
        avg_confidence = context['avg_confidence']
        avg_suitability = context['avg_suitability']
        avg_recommendation = context['avg_recommendation']
        
        summary = f"""
# Portfolio Investment Summary

## Portfolio Overview
- **Total Components**: {total_stocks} stocks
- **Product Type**: {context['product_type']}
- **Investment Amount**: ${context['notional_amount']:,.2f}
- **Target Investor**: {context['user_preferences'].get('risk_tolerance', 'moderate').title()} risk tolerance

## Assessment Summary
- **Overall Confidence**: {avg_confidence:.1%}
- **Overall Suitability**: {avg_suitability:.1%}
- **Average Recommendation Score**: {avg_recommendation:.1%}

## Risk Profile
{self._format_risk_distribution(context['risk_distribution'])}

## Recommendation Distribution
{self._format_recommendation_distribution(context['recommendation_distribution'])}

## Investment Thesis
This portfolio is designed for {context['user_preferences'].get('risk_tolerance', 'moderate')} investors 
seeking {context['user_preferences'].get('investment_horizon', 'long')}-term growth. 
The portfolio demonstrates balanced characteristics with appropriate risk-reward profiles.
"""
        return summary.strip()
    
    def _generate_template_executive_summary(self, context: Dict[str, Any]) -> str:
        """Generate template-based executive summary."""
        return f"""
# Executive Summary

## Investment Opportunity
This {context['product_type'].lower().replace('_', ' ')} offers a balanced investment opportunity 
for {context['risk_tolerance']} investors with a {context['investment_horizon']}-term horizon.

## Key Metrics
- **Portfolio Confidence**: {context['avg_confidence']:.1%}
- **Investor Suitability**: {context['avg_suitability']:.1%}
- **Investment Recommendation**: {context['avg_recommendation']:.1%}
- **Total Components**: {context['total_components']} stocks
- **Investment Amount**: ${context['capital_amount']:,.2f}

## Risk-Reward Profile
The portfolio demonstrates appropriate risk management with {self._get_risk_summary(context['risk_distribution'])} 
risk distribution and {self._get_recommendation_summary(context['recommendation_distribution'])} 
investment recommendations.

## Recommendation
This portfolio represents a compelling investment opportunity with strong alignment 
to the target investor profile and appropriate risk management.
"""
    
    def _generate_template_risk_summary(self, context: Dict[str, Any]) -> str:
        """Generate template-based risk summary."""
        risk_dist = context['risk_distribution']
        total = sum(risk_dist.values())
        
        low_pct = (risk_dist.get('low', 0)/total*100) if total > 0 else 0
        moderate_pct = (risk_dist.get('moderate', 0)/total*100) if total > 0 else 0
        high_pct = (risk_dist.get('high', 0)/total*100) if total > 0 else 0
        
        return f"""
# Risk Analysis Summary

## Risk Distribution
- **Low Risk**: {risk_dist.get('low', 0)} stocks ({low_pct:.1f}%)
- **Moderate Risk**: {risk_dist.get('moderate', 0)} stocks ({moderate_pct:.1f}%)
- **High Risk**: {risk_dist.get('high', 0)} stocks ({high_pct:.1f}%)

## Risk Assessment
This portfolio demonstrates {self._get_risk_profile(risk_dist)} risk characteristics, 
which is {self._get_risk_suitability(risk_dist, context['risk_tolerance'])} for {context['risk_tolerance']} investors.

## Risk Management
The portfolio includes appropriate diversification across {context['total_stocks']} stocks 
to mitigate concentration risk and provide balanced exposure.
"""
    
    def _generate_template_recommendation_summary(self, context: Dict[str, Any]) -> str:
        """Generate template-based recommendation summary."""
        rec_dist = context['recommendation_distribution']
        total = sum(rec_dist.values())
        
        strong_buy_pct = (rec_dist.get('strong_buy', 0)/total*100) if total > 0 else 0
        buy_pct = (rec_dist.get('buy', 0)/total*100) if total > 0 else 0
        hold_pct = (rec_dist.get('hold', 0)/total*100) if total > 0 else 0
        sell_pct = (rec_dist.get('sell', 0)/total*100) if total > 0 else 0
        strong_sell_pct = (rec_dist.get('strong_sell', 0)/total*100) if total > 0 else 0
        
        return f"""
# Investment Recommendation Summary

## Recommendation Distribution
- **Strong Buy**: {rec_dist.get('strong_buy', 0)} stocks ({strong_buy_pct:.1f}%)
- **Buy**: {rec_dist.get('buy', 0)} stocks ({buy_pct:.1f}%)
- **Hold**: {rec_dist.get('hold', 0)} stocks ({hold_pct:.1f}%)
- **Sell**: {rec_dist.get('sell', 0)} stocks ({sell_pct:.1f}%)
- **Strong Sell**: {rec_dist.get('strong_sell', 0)} stocks ({strong_sell_pct:.1f}%)

## Overall Assessment
The portfolio shows an average recommendation score of {context['avg_recommendation']:.1%}, 
indicating {self._get_recommendation_strength(context['avg_recommendation'])} investment opportunities.

## Investment Thesis
This portfolio is well-suited for {context['risk_tolerance']} investors with a {context['investment_horizon']}-term horizon, 
offering {self._get_investment_characteristics(rec_dist)} investment characteristics.
"""
    
    def _generate_fallback_summary(self, context: Dict[str, Any]) -> str:
        """Generate fallback summary when LLM fails."""
        return f"Summary generation failed. Key metrics: {context.get('symbol', 'Unknown')} - {context.get('recommendation', 'HOLD')} recommendation with {context.get('confidence_score', 0.5):.1%} confidence."
    
    def _format_insights(self, insights: Dict[str, List[str]]) -> str:
        """Format insights for display."""
        if not insights:
            return "No specific insights available."
        
        formatted = []
        for category, insight_list in insights.items():
            if insight_list:
                category_name = category.replace('_', ' ').title()
                formatted.append(f"**{category_name}**:")
                for insight in insight_list[:3]:  # Limit to 3 insights per category
                    formatted.append(f"- {insight}")
        
        return '\n'.join(formatted) if formatted else "No specific insights available."
    
    def _format_risk_distribution(self, risk_dist: Dict[str, int]) -> str:
        """Format risk distribution for display."""
        total = sum(risk_dist.values())
        if total == 0:
            return "Risk distribution not available."
        
        return f"""
- **Low Risk**: {risk_dist.get('low', 0)} stocks ({risk_dist.get('low', 0)/total*100:.1f}%)
- **Moderate Risk**: {risk_dist.get('moderate', 0)} stocks ({risk_dist.get('moderate', 0)/total*100:.1f}%)
- **High Risk**: {risk_dist.get('high', 0)} stocks ({risk_dist.get('high', 0)/total*100:.1f}%)
"""
    
    def _format_recommendation_distribution(self, rec_dist: Dict[str, int]) -> str:
        """Format recommendation distribution for display."""
        total = sum(rec_dist.values())
        if total == 0:
            return "Recommendation distribution not available."
        
        return f"""
- **Strong Buy**: {rec_dist.get('strong_buy', 0)} stocks ({rec_dist.get('strong_buy', 0)/total*100:.1f}%)
- **Buy**: {rec_dist.get('buy', 0)} stocks ({rec_dist.get('buy', 0)/total*100:.1f}%)
- **Hold**: {rec_dist.get('hold', 0)} stocks ({rec_dist.get('hold', 0)/total*100:.1f}%)
- **Sell**: {rec_dist.get('sell', 0)} stocks ({rec_dist.get('sell', 0)/total*100:.1f}%)
- **Strong Sell**: {rec_dist.get('strong_sell', 0)} stocks ({rec_dist.get('strong_sell', 0)/total*100:.1f}%)
"""
    
    def _get_risk_summary(self, risk_dist: Dict[str, int]) -> str:
        """Get risk summary description."""
        low = risk_dist.get('low', 0)
        moderate = risk_dist.get('moderate', 0)
        high = risk_dist.get('high', 0)
        total = low + moderate + high
        
        if total == 0:
            return "balanced"
        
        if low > high and low > moderate:
            return "conservative"
        elif high > low and high > moderate:
            return "aggressive"
        else:
            return "balanced"
    
    def _get_recommendation_summary(self, rec_dist: Dict[str, int]) -> str:
        """Get recommendation summary description."""
        strong_buy = rec_dist.get('strong_buy', 0)
        buy = rec_dist.get('buy', 0)
        sell = rec_dist.get('sell', 0)
        strong_sell = rec_dist.get('strong_sell', 0)
        
        positive = strong_buy + buy
        negative = sell + strong_sell
        
        if positive > negative:
            return "positive"
        elif negative > positive:
            return "negative"
        else:
            return "neutral"
    
    def _get_risk_profile(self, risk_dist: Dict[str, int]) -> str:
        """Get risk profile description."""
        high = risk_dist.get('high', 0)
        total = sum(risk_dist.values())
        
        if total == 0:
            return "balanced"
        
        high_pct = high / total
        if high_pct > 0.4:
            return "higher"
        elif high_pct < 0.2:
            return "lower"
        else:
            return "moderate"
    
    def _get_risk_suitability(self, risk_dist: Dict[str, int], risk_tolerance: str) -> str:
        """Get risk suitability description."""
        high = risk_dist.get('high', 0)
        total = sum(risk_dist.values())
        
        if total == 0:
            return "appropriate"
        
        high_pct = high / total
        
        if risk_tolerance == 'conservative' and high_pct > 0.3:
            return "inappropriate"
        elif risk_tolerance == 'aggressive' and high_pct < 0.2:
            return "too conservative"
        else:
            return "appropriate"
    
    def _get_recommendation_strength(self, avg_score: float) -> str:
        """Get recommendation strength description."""
        if avg_score > 0.7:
            return "strong"
        elif avg_score > 0.5:
            return "moderate"
        else:
            return "weak"
    
    def _get_investment_characteristics(self, rec_dist: Dict[str, int]) -> str:
        """Get investment characteristics description."""
        strong_buy = rec_dist.get('strong_buy', 0)
        buy = rec_dist.get('buy', 0)
        total = sum(rec_dist.values())
        
        if total == 0:
            return "balanced"
        
        positive_pct = (strong_buy + buy) / total
        if positive_pct > 0.6:
            return "strong positive"
        elif positive_pct > 0.4:
            return "moderate positive"
        else:
            return "balanced" 