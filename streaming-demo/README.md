# Lobe Chat Streaming Demo

A minimal implementation demonstrating the core streaming functionality from Lobe Chat. This demo shows how to implement real-time AI chat streaming using Server-Sent Events (SSE) and the OpenAI API.

Now available in both **Node.js** and **Python** implementations!

## Features

- ✅ Real-time streaming responses
- ✅ Server-Sent Events (SSE) implementation
- ✅ OpenAI API integration
- ✅ Conversation history
- ✅ Error handling
- ✅ Token usage tracking
- ✅ Clean, responsive UI
- ✅ Typing indicators
- ✅ Request cancellation
- ✅ Both Node.js and Python backends

## Architecture

This demo replicates the key components of Lobe Chat's streaming architecture:

### Backend Options

#### Node.js Backend (`server.js`)
- **Express server** with CORS and JSON middleware
- **OpenAI client** for API communication
- **Stream transformation** - converts OpenAI chunks to standardized format
- **SSE endpoint** - `/api/chat` that streams responses
- **Error handling** for network and API errors

#### Python Backend (`server.py`)
- **FastAPI server** with uvicorn ASGI server
- **Async OpenAI client** for non-blocking operations
- **SSE-Starlette** for Server-Sent Events
- **Pydantic models** for request validation
- **Same API interface** as Node.js version

### Frontend (`public/index.html`)
- **Chat interface** with message history
- **SSE consumption** using Fetch API and ReadableStream
- **Real-time updates** as chunks arrive
- **State management** for streaming status
- **Conversation context** maintenance

## Setup

### Option 1: Node.js Server

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Set your OpenAI API key:**
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

3. **Start the server:**
   ```bash
   npm run dev
   ```

### Option 2: Python Server

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   # or
   npm run install:python
   ```

2. **Set your OpenAI API key:**
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```
   
   Or create a `.env` file:
   ```
   OPENAI_API_KEY=your-api-key-here
   ```

3. **Start the Python server:**
   ```bash
   python server.py
   # or
   npm run dev:python
   # or with uvicorn directly
   uvicorn server:app --reload --port 3001
   ```

### Access the Application

4. **Open your browser:**
   ```
   http://localhost:3001
   ```

## How It Works

### 1. Frontend Request
```javascript
const response = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    messages: conversationHistory,
    model: 'gpt-4o-mini',
    stream: true
  })
});
```

### 2. Backend Processing

#### Node.js Implementation
```javascript
// Create OpenAI streaming completion
const stream = await openai.chat.completions.create({
  model,
  messages,
  stream: true,
  stream_options: { include_usage: true }
});

// Transform and send as SSE
for await (const chunk of stream) {
  const transformed = transformOpenAIStream(chunk);
  if (transformed) {
    res.write(`event: ${transformed.type}\ndata: ${JSON.stringify(transformed.data)}\n\n`);
  }
}
```

#### Python Implementation
```python
# Create OpenAI streaming completion
stream = await client.chat.completions.create(
    model=model,
    messages=messages,
    stream=True,
    stream_options={"include_usage": True}
)

# Transform and send as SSE
async for chunk in stream:
    transformed = transform_openai_stream(chunk)
    if transformed:
        yield f"event: {transformed['type']}\n"
        yield f"data: {json.dumps(transformed['data'])}\n\n"
```

### 3. Frontend Stream Consumption
```javascript
const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  // Parse SSE format and handle events
  const lines = decoder.decode(value).split('\n');
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.substring(6));
      handleStreamEvent(event, data);
    }
  }
}
```

## Stream Events

The demo handles these event types (matching Lobe Chat's protocol):

- **`text`** - Text content chunks
- **`usage`** - Token usage information
- **`stop`** - Stream completion
- **`error`** - Error messages
- **`tool_calls`** - Function calling (placeholder)

## Key Differences from Lobe Chat

This is a simplified version focusing on core streaming concepts:

- **Single provider** (OpenAI only)
- **No authentication** system
- **No database** persistence
- **No plugin system**
- **No advanced features** (reasoning, images, etc.)
- **Simplified error handling**

## Python vs Node.js Implementations

Both implementations provide identical functionality with these differences:

| Feature | Node.js | Python |
|---------|---------|---------|
| Framework | Express | FastAPI |
| Async Model | Promises/async-await | asyncio/async-await |
| OpenAI Client | Official SDK | Official Async SDK |
| SSE Implementation | Manual response writing | sse-starlette |
| Type Safety | JavaScript (dynamic) | Pydantic models |
| Performance | Good | Excellent (with uvicorn) |

## Extending the Demo

To add more features:

1. **Multiple providers** - Add Anthropic, Google, etc.
2. **Authentication** - Add user management
3. **Persistence** - Save conversations to database
4. **Tool calling** - Implement function calling
5. **File uploads** - Add image/document support
6. **Advanced UI** - Add markdown rendering, syntax highlighting

## Code Structure

```
streaming-demo/
├── package.json          # Dependencies and scripts
├── server.js             # Node.js Express server
├── server.py             # Python FastAPI server
├── requirements.txt      # Python dependencies
├── public/
│   └── index.html        # Frontend chat interface
└── README.md            # This file
```

## Learning Points

This demo illustrates:

1. **Server-Sent Events** for real-time communication
2. **Stream processing** and transformation
3. **Async iteration** with OpenAI streams
4. **Frontend state management** during streaming
5. **Error handling** in streaming contexts
6. **Conversation context** management
7. **Cross-platform implementation** (Node.js and Python)

## Troubleshooting

**No API key error:**
- Make sure `OPENAI_API_KEY` environment variable is set
- For Python, you can also use a `.env` file

**CORS errors:**
- Both servers include CORS middleware for local development

**Stream parsing errors:**
- Check browser console for detailed error messages
- Check server logs for backend errors

**Connection issues:**
- Ensure the server is running on port 3001
- For Python, make sure all dependencies are installed

**Python-specific issues:**
- Ensure Python 3.8+ is installed
- Use a virtual environment to avoid dependency conflicts
- If uvicorn doesn't start, try: `python -m uvicorn server:app --reload --port 3001`

## License

MIT License - feel free to use this code for learning and development! 