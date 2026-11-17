"""Labelled eval questions. items = acceptable section keys (10-K or 10-Q)."""

SEARCH_CASES = [
    {
        "id": "aapl_china_mfg",
        "ticker": "AAPL",
        "items": ["1A", "II-1A"],
        "question": "Apple risks from manufacturing concentration in China and Asia",
    },
    {
        "id": "aapl_dma",
        "ticker": "AAPL",
        "items": ["3", "II-1", "1A", "II-1A"],
        "question": "Apple legal proceedings under the EU Digital Markets Act",
    },
    {
        "id": "aapl_cyber",
        "ticker": "AAPL",
        "items": ["1C"],
        "question": "Apple cybersecurity risk management and board oversight",
    },
    {"id": "aapl_people", "ticker": "AAPL", "items": ["1"], "question": "Apple human capital and number of employees"},
    {
        "id": "msft_azure",
        "ticker": "MSFT",
        "items": ["7", "I-2"],
        "question": "Microsoft Azure and cloud revenue growth drivers",
    },
    {
        "id": "msft_cyber",
        "ticker": "MSFT",
        "items": ["1A", "II-1A", "1C"],
        "question": "Microsoft cyberattacks by nation-state actors",
    },
    {
        "id": "msft_buyback",
        "ticker": "MSFT",
        "items": ["5", "7", "8", "II-2", "I-1", "I-2"],
        "question": "Microsoft share repurchases and dividends",
    },
    {
        "id": "nvda_export",
        "ticker": "NVDA",
        "items": ["1A", "II-1A"],
        "question": "NVIDIA export controls restricting data center GPU sales to China",
    },
    {
        "id": "nvda_foundry",
        "ticker": "NVDA",
        "items": ["1A", "II-1A", "1"],
        "question": "NVIDIA dependence on third-party foundries to manufacture chips",
    },
    {"id": "nvda_dc_rev", "ticker": "NVDA", "items": ["7", "I-2"], "question": "NVIDIA data center revenue growth"},
    {
        "id": "amzn_aws",
        "ticker": "AMZN",
        "items": ["7", "I-2", "8", "I-1"],
        "question": "Amazon AWS segment sales and operating income",
    },
    {
        "id": "amzn_fulfillment",
        "ticker": "AMZN",
        "items": ["1A", "II-1A", "7", "I-2", "1"],
        "question": "Amazon fulfillment network capacity and costs",
    },
    {
        "id": "googl_ads",
        "ticker": "GOOGL",
        "items": ["7", "I-2", "1"],
        "question": "Alphabet Google advertising revenue from Search and YouTube",
    },
    {
        "id": "googl_capex",
        "ticker": "GOOGL",
        "items": ["7", "I-2"],
        "question": "Alphabet capital expenditures on AI and technical infrastructure",
    },
]

# No company names: the question only names products/segments.
HARD_CASES = [
    {
        "id": "h_iphone_geo",
        "ticker": "AAPL",
        "items": ["7", "I-2"],
        "question": "iPhone net sales by geographic segment",
    },
    {
        "id": "h_wearables",
        "ticker": "AAPL",
        "items": ["7", "I-2"],
        "question": "Wearables, Home and Accessories net sales change",
    },
    {
        "id": "h_app_store",
        "ticker": "AAPL",
        "items": ["1A", "II-1A", "3", "II-1"],
        "question": "App Store commission changes required by regulators",
    },
    {"id": "h_xbox", "ticker": "MSFT", "items": ["7", "I-2"], "question": "Xbox content and services revenue"},
    {"id": "h_linkedin", "ticker": "MSFT", "items": ["7", "I-2"], "question": "LinkedIn revenue growth"},
    {"id": "h_cuda", "ticker": "NVDA", "items": ["1"], "question": "CUDA software platform and developer ecosystem"},
    {
        "id": "h_ai_export",
        "ticker": "NVDA",
        "items": ["1A", "II-1A"],
        "question": "Licensing requirements for shipping AI accelerators to China",
    },
    {
        "id": "h_prime",
        "ticker": "AMZN",
        "items": ["1", "7", "I-2"],
        "question": "Prime membership benefits and subscription services",
    },
    {"id": "h_3p_seller", "ticker": "AMZN", "items": ["7", "I-2"], "question": "Third-party seller services revenue"},
    {"id": "h_youtube", "ticker": "GOOGL", "items": ["7", "I-2"], "question": "YouTube ads revenue"},
    {
        "id": "h_other_bets",
        "ticker": "GOOGL",
        "items": ["7", "I-2", "8", "I-1"],
        "question": "Other Bets operating loss",
    },
]

PRICE_CASES = [
    {
        "id": "p_amzn_1y",
        "ticker": "AMZN",
        "period": "1y",
        "question": "How has Amazon stock performed over the past year?",
    },
    {"id": "p_nvda_ytd", "ticker": "NVDA", "period": "ytd", "question": "What is NVIDIA's year-to-date stock return?"},
    {
        "id": "p_msft_6m",
        "ticker": "MSFT",
        "period": "6m",
        "question": "How volatile has Microsoft stock been over the last six months?",
    },
    {
        "id": "p_googl_3y",
        "ticker": "GOOGL",
        "period": "3y",
        "question": "What was Alphabet's maximum drawdown over the last three years?",
    },
    {"id": "p_aapl_1m", "ticker": "AAPL", "period": "1m", "question": "How did Apple shares do over the past month?"},
]
