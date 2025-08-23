# Merged Company Research Project

This project combines:
- **Frontend**: original Streamlit interface
- **Backend**: The sophisticated agentic AI system from "company-research-agent"

## What Changed

- **Frontend**: Kept exactly the same - same UI, same style, same user experience
- **Backend**: Replaced simple LLM approach with the advanced agentic AI system that:
  - Uses multiple research nodes (company, financial, industry, news analysis)
  - Implements a sophisticated workflow with grounding, collection, curation, and enrichment
  - Provides more comprehensive and accurate company research

## How to Run

### 1. Install Dependencies
```bash
cd merged
pip install -r requirements.txt
```

### 2. Set up Environment Variables
Make sure your `.env` file contains:
```
TAVILY_API_KEY=your_tavily_key
AZURE_OPENAI_API_KEY=your_azure_key
AZURE_OPENAI_ENDPOINT=your_azure_endpoint
AZURE_OPENAI_EMBED_DEPLOYMENT=gpt-5-mini
```

### 3. Start the Backend Server
```bash
python backend_server.py
```
This will start the FastAPI server on http://localhost:8000

### 4. Start the Frontend
In a new terminal:
```bash
streamlit run app.py
```
This will start the Streamlit frontend on http://localhost:8501

## How It Works

1. **User Input**: Enter company name (and optionally URL, industry, location) in your familiar Streamlit interface
2. **Backend Processing**: The agentic AI system:
   - Grounds the research with initial context
   - Runs multiple specialized researchers (company, financial, industry, news)
   - Collects and curates information
   - Enriches the data
   - Generates comprehensive briefings
   - Compiles a final report
3. **Frontend Display**: Shows the results in your original UI format with the enhanced content

## Benefits

- **Same User Experience**: Your frontend looks and feels exactly the same
- **Better Research**: Much more comprehensive and accurate company information
- **Advanced AI**: Uses the sophisticated agentic workflow instead of simple LLM calls
- **Real-time Updates**: WebSocket support for live progress updates (can be enhanced further)

## File Structure

```
merged/
├── app.py                 # Your Streamlit frontend (modified to use agentic backend)
├── backend_server.py      # FastAPI backend server
├── backend/               # Agentic AI backend system
├── ui.py                  # Your original UI components
├── data.py                # Your original data models
├── config.py              # Your original configuration
├── requirements.txt       # Combined dependencies
├── .env                   # Environment variables
└── README.md             # This file
```

## Notes

- The frontend polling approach can be enhanced with WebSocket integration for real-time updates
- The agentic system provides much richer research but may take longer to complete
- All your original UI styling and user experience is preserved
