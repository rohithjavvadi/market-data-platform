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
