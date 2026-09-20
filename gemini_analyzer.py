# gemini_analyzer.py
import requests
import json
import time
import pandas as pd
from typing import Dict, Any, Tuple, List # Added List type hint
import os # Added os import

# Gemini API configuration using the specified model
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
# The API key is an empty string; it will be provided by the execution environment.
API_KEY = "AIzaSyB0m8383hDy-ow7cnhK833OzuJRejoW4_g" # Ensure API_KEY is empty by default


def prepare_prompt(symbol: str, df: pd.DataFrame, summary: Dict[str, Any]) -> Tuple[str, str]:
    """
    Prepares the system and user prompts for the Gemini API for SINGLE STOCK analysis.

    Args:
        symbol: The stock ticker symbol.
        df: A pandas DataFrame with the historical price data ('close', 'high', 'low', 'volume').
        summary: A dictionary containing pre-calculated technical indicators.

    Returns:
        A tuple containing the system prompt and the user prompt.
    """
    system_prompt = """
    You are a professional stock market technical analyst for the Colombo Stock Exchange (CSE). Your role is to provide an unbiased, data-driven analysis based exclusively on the historical price and volume data provided.

    You must adhere to the following rules:
    1.  **Data-Bound:** Base your entire analysis ONLY on the data given in the user prompt (technical summary and recent data). Do not use any external knowledge, news, or real-time market information. Mention you are analyzing CSE data.
    2.  **No Financial Advice:** Do not give any recommendations to "buy," "sell," or "hold." Do not predict future prices. Instead, describe the technical situation objectively.
    3.  **Neutral Tone:** Use neutral and objective language (e.g., "The RSI suggests potential oversold conditions," instead of "This is a great buying opportunity.").
    4.  **Structured Output:** Structure your response using Markdown with the following five sections exactly as named:
        * `### Potential Bullish Indicators`
        * `### Potential Bearish Indicators & Risks`
        * `### Key Price Levels` (Mention support/resistance based on MA's, 52wk levels)
        * `### Potential Accumulation Zones`
        * `### Hypothetical DCA Strategy Example`
    5.  **Be Concise:** Keep your analysis clear and to the point. Focus on interpreting the provided summary metrics.
    6.  **For "Potential Accumulation Zones":** Identify price ranges near significant, historically-tested support levels derived from the provided data (e.g., near the 200-day SMA, or the 52-week low). Frame these as areas where the stock has previously found buying interest, not as buy recommendations.
    7.  **For "Hypothetical DCA Strategy Example":** Based on the identified accumulation zones, create a sample Dollar-Cost Averaging plan (e.g., 3 tiers). This must be presented as an educational example (e.g., "A hypothetical 3-tiered DCA strategy *could* involve allocating capital at...") and not as direct advice. Emphasize it's hypothetical.
    """

    # Prepare a snippet of recent data to include in the prompt
    recent_data = df.tail(20)[['close', 'high', 'low', 'volume']].to_string() # Select specific columns

    user_prompt = f"""
    Analyze the historical stock data for the CSE symbol: **{symbol}**.

    **Technical Summary (calculated from historical data):**
    ```json
    {json.dumps(summary, indent=2)}
    ```

    **Recent Data (Last 20 Days):**
    ```
    {recent_data}
    ```

    Based *only* on the data provided above, provide a technical analysis in the required Markdown format, including Potential Accumulation Zones and a Hypothetical DCA Strategy Example specifically for symbol {symbol}. Do not mention external factors.
    """
    return system_prompt, user_prompt

# *** ADDED function for Market Summary prompt ***
def prepare_market_summary_prompt(gainers_data: Dict[str, Any], losers_data: Dict[str, Any]) -> Tuple[str, str]:
    """
    Prepares the system and user prompts for the Gemini API for MARKET SUMMARY.

    Args:
        gainers_data: Raw JSON payload for top gainers from CSE API.
        losers_data: Raw JSON payload for top losers from CSE API.

    Returns:
        A tuple containing the system prompt and the user prompt.
    """
    system_prompt = """
    You are a market analyst summarizing daily activity on the Colombo Stock Exchange (CSE). Your task is to provide a brief, objective summary based *only* on the provided Top Gainers and Top Losers data.

    Rules:
    1.  **Data-Bound:** Base your summary *exclusively* on the list of top gainers and losers provided. Do not infer news, reasons, or external factors.
    2.  **Focus:** Briefly describe the general market sentiment (e.g., mixed, bullish bias, bearish bias) indicated by the number and magnitude of gainers vs. losers. Mention any standout performers (e.g., stocks with very high percentage changes) if present in the data. Mention which sectors (if identifiable from symbol names or data) are represented in the lists.
    3.  **No Predictions/Advice:** Do not predict future movements or offer any trading advice.
    4.  **Concise:** Keep the summary to 1-2 short paragraphs.
    5.  **Format:** Output as plain text, suitable for display in a modal popup. Start by stating the date (assume today).
    """

    # Helper to extract relevant info, handling potential structure variations
    def extract_top_list(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        items = []
        # Look for common keys where the list might be nested
        possible_keys = ['reqTradeSummery', 'data', 'records']
        data_list = data if isinstance(data, list) else None
        if not data_list:
            for key in possible_keys:
                if isinstance(data.get(key), list):
                    data_list = data[key]
                    break
        if not data_list:
            return [] # Return empty if structure unknown

        for item in data_list[:10]: # Limit to top 10
             symbol = item.get('symbol') or item.get('security')
             pct_change = item.get('percentageChange') or item.get('changePer')
             if symbol and pct_change is not None:
                 try:
                     items.append({'symbol': str(symbol), 'change': float(pct_change)})
                 except (ValueError, TypeError):
                     continue # Skip if data is invalid
        return items

    top_gainers = extract_top_list(gainers_data)
    top_losers = extract_top_list(losers_data)

    # Sort by magnitude for clarity in prompt
    top_gainers.sort(key=lambda x: x['change'], reverse=True)
    top_losers.sort(key=lambda x: abs(x['change']), reverse=True) # Sort losers by absolute change

    # Format data for the prompt
    gainers_str = "\n".join([f"- {g['symbol']}: +{g['change']:.2f}%" for g in top_gainers])
    losers_str = "\n".join([f"- {l['symbol']}: {l['change']:.2f}%" for l in top_losers])

    user_prompt = f"""
    Today's Top Movers data from the Colombo Stock Exchange (CSE) is provided below.

    **Top Gainers:**
    ```
    {gainers_str if gainers_str else "No gainers data provided."}
    ```

    **Top Losers:**
    ```
    {losers_str if losers_str else "No losers data provided."}
    ```

    Based *only* on this data, provide a brief (1-2 paragraph) objective summary of today's market activity and sentiment. Mention any standout percentage changes or visible sector trends. Do not speculate on reasons or give advice.
    """
    return system_prompt, user_prompt


def generate_analysis(system_prompt: str, user_prompt: str) -> str:
    """
    Calls the Gemini API to get text generation based on the prompts.

    Args:
        system_prompt: The system instruction for the model.
        user_prompt: The user query including the data.

    Returns:
        The generated text from Gemini, or an error message prefixed with "Error: ".
    """
    # Use environment variable for API Key if available, otherwise use empty string
    effective_api_key = os.getenv("GEMINI_API_KEY", API_KEY)
    url = f"{API_URL}?key={effective_api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "temperature": 0.5, # Slightly increased temperature
            "topK": 40,
            "topP": 0.95,
            # *** INCREASED maxOutputTokens ***
            "maxOutputTokens": 4096,
        }
    }

    retries = 3
    delay = 1.0
    for i in range(retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=90) # Increased timeout slightly
            response.raise_for_status() # Check for HTTP errors first

            result = response.json()

            # Check for explicit API errors in the response body
            if 'error' in result:
                error_detail = result['error'].get('message', json.dumps(result['error']))
                # Don't retry on explicit API errors usually
                return f"Error: Gemini API returned an error - {error_detail}"


            # Standard successful response parsing
            if 'candidates' in result and result['candidates']:
                candidate = result['candidates'][0]

                 # Check for safety ratings / blocked content
                if candidate.get('finishReason') == 'SAFETY':
                     return "Error: Gemini blocked the response due to safety concerns."
                if candidate.get('finishReason') == 'RECITATION':
                     return "Error: Gemini blocked the response due to potential recitation."
                # *** ADDED Check for MAX_TOKENS finish reason ***
                if candidate.get('finishReason') == 'MAX_TOKENS':
                     # Try to return the partial content received before cutoff
                     if 'content' in candidate and 'parts' in candidate['content']:
                         partial_text = candidate['content']['parts'][0]['text']
                         print(f"Warning: Gemini response truncated due to MAX_TOKENS. Returning partial analysis.")
                         return partial_text.strip() + "\n\n[Warning: Analysis truncated due to length limit]"
                     else:
                         return "Error: Gemini response exceeded maximum length and no partial content could be retrieved."

                if 'content' in candidate and 'parts' in candidate['content']:
                    text = candidate['content']['parts'][0]['text']
                    return text.strip() # Strip leading/trailing whitespace

            # Handle unexpected structure if no specific error and no candidates
            error_message = f"Unexpected API response structure: {json.dumps(result)}"
            print(f"Attempt {i+1} failed: {error_message}") # Log unexpected structure
            # Let it retry for unexpected structures, maybe temporary glitch
            if i == retries - 1:
                return f"Error: {error_message}"
            time.sleep(delay)
            delay *= 2 # Exponential backoff

        except requests.exceptions.Timeout as e:
            print(f"Attempt {i+1} timed out: {e}")
            if i < retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                return f"Error: Gemini API request timed out after {retries} attempts."
        except requests.exceptions.RequestException as e:
            # Includes connection errors, HTTP errors caught by raise_for_status
            print(f"Attempt {i+1} failed with RequestException: {e}")
            # Retry on network/server errors, but not on client errors (4xx) usually
            is_retryable = not (400 <= (e.response.status_code if e.response else 0) < 500)
            if is_retryable and i < retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                err_msg = f"Failed to connect to Gemini API after {retries} attempts."
                if e.response is not None:
                    err_msg += f" Status Code: {e.response.status_code}. Response: {e.response.text[:200]}" # Show start of error response
                else:
                     err_msg += f" Details: {e}"
                return f"Error: {err_msg}"
        except (ValueError, KeyError, json.JSONDecodeError) as e:
             # Errors during response processing
             print(f"Error parsing Gemini API response: {e}")
             raw_response = response.text if 'response' in locals() else "Response object not available"
             return f"Error: Could not parse Gemini API response. Details: {e}\nRaw Response Snippet: {raw_response[:200]}"

    return "Error: Gemini API call failed after all retries." # Should technically be unreachable

