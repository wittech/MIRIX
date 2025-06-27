import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="Lobe Chat Streaming Demo")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI client
openai_client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "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")
)

# Pydantic models
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    model: str = "gpt-4o-mini"
    stream: bool = True

class StreamEvent(BaseModel):
    data: Any
    id: str
    type: str

def transform_openai_stream(chunk) -> Optional[StreamEvent]:
    """Transform OpenAI stream chunks to our protocol"""
    try:
        choice = chunk.choices[0] if chunk.choices else None
        
        if not choice:
            if hasattr(chunk, 'usage') and chunk.usage:
                return StreamEvent(
                    data=chunk.usage.model_dump(),
                    id=chunk.id,
                    type="usage"
                )
            return None

        # Handle tool calls
        if choice.delta and hasattr(choice.delta, 'tool_calls') and choice.delta.tool_calls:
            return StreamEvent(
                data=[tool_call.model_dump() for tool_call in choice.delta.tool_calls],
                id=chunk.id,
                type="tool_calls"
            )

        # Handle finish reason
        if choice.finish_reason:
            if choice.delta and choice.delta.content:
                return StreamEvent(
                    data=choice.delta.content,
                    id=chunk.id,
                    type="text"
                )
            if hasattr(chunk, 'usage') and chunk.usage:
                return StreamEvent(
                    data=chunk.usage.model_dump(),
                    id=chunk.id,
                    type="usage"
                )
            return StreamEvent(
                data=choice.finish_reason,
                id=chunk.id,
                type="stop"
            )

        # Handle text content
        if choice.delta and choice.delta.content:
            return StreamEvent(
                data=choice.delta.content,
                id=chunk.id,
                type="text"
            )

        return None
    except Exception as error:
        print(f"Stream transform error: {error}")
        return StreamEvent(
            data={"message": "Stream parsing error", "error": str(error)},
            id=getattr(chunk, 'id', 'error'),
            type="error"
        )

async def generate_chat_stream(messages: List[Message], model: str, enable_streaming: bool):
    """Generate chat completion stream"""
    try:
        # Convert messages to OpenAI format
        openai_messages = [{"role": msg.role, "content": msg.content} for msg in messages]
        
        if not enable_streaming:
            # Non-streaming response
            completion = openai_client.chat.completions.create(
                model=model,
                messages=openai_messages,
                stream=False
            )
            
            content = completion.choices[0].message.content if completion.choices else ""
            yield f"event: text\ndata: {json.dumps(content)}\n\n"
            yield f"event: stop\ndata: {json.dumps('stop')}\n\n"
            return

        # Create streaming completion
        stream = openai_client.chat.completions.create(
            model=model,
            messages=openai_messages,
            stream=True,
            stream_options={"include_usage": True}
        )

        # Process stream
        for chunk in stream:
            transformed = transform_openai_stream(chunk)
            
            if transformed:
                print(f"Sending SSE: {transformed.type} {transformed.data}")
                # Send as Server-Sent Event
                yield f"event: {transformed.type}\ndata: {json.dumps(transformed.data)}\n\n"

    except Exception as error:
        print(f"Chat API error: {error}")
        
        # Send error as SSE
        error_data = {
            "message": str(error),
            "type": "ChatAPIError"
        }
        yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """Chat streaming endpoint"""
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages array is required")

    return StreamingResponse(
        generate_chat_stream(request.messages, request.model, request.stream),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )

# Mount static files
app.mount("/static", StaticFiles(directory="public"), name="static")

@app.get("/")
async def serve_index():
    """Serve the HTML page"""
    return FileResponse("public/index.html")

if __name__ == "__main__":
    import uvicorn
    print("Server running at http://localhost:3001")
    print("Make sure to set your OPENAI_API_KEY environment variable")
    uvicorn.run(app, host="0.0.0.0", port=3001) 