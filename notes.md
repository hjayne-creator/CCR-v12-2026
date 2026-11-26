# Notes

This will be a POC used internally for testing. Expected PDP volume, 1 run at a time, and bulk (<100) at a later point. 
Available API keys: OpenAI, Anthropic, Google
FireCrawl API: Bot blocking is a problem. Use PDP content extraction (JS enabled, body content, markdown); use Search and Scrape endpoints.
Search APIs: Serper, DataforSEO
Platform: whatever you recommend. In th past have used: FastAPI + SQLModel backend, React + Vite frontend
Servers: local, and avaialble StreamLit or Railway for production
DB: Neon (optional) 
Multi-client: yes, to support multiple clients, for example: sgs-engineering.com and designpublic.com
Some PDPs will be brand only (sgs engineering); others will be available on other retailer websites. 
LLMs: ability to choose from miltiple providers and models and pricing for each run. 

Example PDP app (owned)
Pull from anything here as useful. 
https://pdp-optimizer-dynecom.streamlit.app/
See Streamlit folder

Example URLs:
https://www.sgs-engineering.com/sgs-3-ton-low-profile-trolley-jack
https://www.designpublic.com/products/norm-architects-ridge-sofa-modules-wendelbo?variant=45136433447097
