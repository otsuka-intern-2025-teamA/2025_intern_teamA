# Company Research Agent Setup

## Prerequisites

- Python 3.8+
- Azure OpenAI account with GPT-5-mini model deployed
- Tavily API key

## Installation

1. **Clone the repository and navigate to the project directory:**
   ```bash
   cd merged
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

1. **Create a `.env` file in the project root:**
   ```bash
   # Azure OpenAI Configuration
   AZURE_OPENAI_API_KEY=your_azure_openai_api_key_here
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   
   # Tavily API Configuration
   TAVILY_API_KEY=your_tavily_api_key_here
   
   # MongoDB Configuration (optional)
   MONGODB_URI=mongodb://localhost:27017/
   
   # Server Configuration
   HOST=0.0.0.0
   PORT=8000
   ```

2. **Replace the placeholder values with your actual API keys and endpoints.**

## Running the Application

### Option 1: Using the start script
```bash
./start.sh
```

### Option 2: Manual start
```bash
# Activate virtual environment
source .venv/bin/activate

# Start the backend server
python backend_server.py
```

The backend server will start on `http://localhost:8000`

## API Endpoints

- `POST /research` - Start a new research job
- `GET /research/{job_id}/report` - Get research results
- `GET /docs` - API documentation (Swagger UI)

## Troubleshooting

### Common Issues:

1. **"No active connections for job" errors:**
   - This is normal if no frontend is connected
   - The backend will continue processing without WebSocket updates

2. **Azure OpenAI errors:**
   - Verify your API key and endpoint are correct
   - Ensure GPT-5-mini model is deployed in your Azure OpenAI resource
   - Check API version compatibility

3. **Tavily API errors:**
   - Verify your Tavily API key is valid
   - Check your API usage limits

4. **Import errors:**
   - Ensure all dependencies are installed
   - Check Python version compatibility

### Debug Mode:

To enable debug logging, set the environment variable:
```bash
export LOG_LEVEL=DEBUG
```

## Project Structure

```
merged/
├── backend/                 # Backend application code
│   ├── classes/            # Data models and state classes
│   ├── nodes/              # Processing nodes for the research workflow
│   ├── services/           # External service integrations
│   └── utils/              # Utility functions
├── backend_server.py       # FastAPI server entry point
├── requirements.txt         # Python dependencies
├── start.sh                # Startup script
└── .env                    # Environment configuration (create this)
```

## Research Workflow

1. **Grounding** - Initial company information gathering
2. **Research** - Parallel research by different analysts:
   - Company Analyst
   - Financial Analyst
   - Industry Analyst
   - News Scanner
3. **Collection** - Gather all research data
4. **Curation** - Filter and rank documents by relevance
5. **Enrichment** - Extract raw content from URLs
6. **Briefing** - Generate summaries for each category
7. **Editing** - Compile final research report

## Contributing

When making changes to the code:
1. Test your changes thoroughly
2. Ensure all imports are correct
3. Check that WebSocket updates work properly
4. Verify the research workflow completes successfully
