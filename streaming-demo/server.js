import express from 'express';
import cors from 'cors';
import OpenAI from 'openai';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
const port = 3001;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Initialize OpenAI client
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY || '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'
});

// Transform OpenAI stream chunks to our protocol
function transformOpenAIStream(chunk) {
  try {
    const choice = chunk.choices[0];
    
    if (!choice) {
      if (chunk.usage) {
        return { data: chunk.usage, id: chunk.id, type: 'usage' };
      }
      return null;
    }

    // Handle tool calls
    if (choice.delta?.tool_calls) {
      return {
        data: choice.delta.tool_calls,
        id: chunk.id,
        type: 'tool_calls'
      };
    }

    // Handle finish reason
    if (choice.finish_reason) {
      if (choice.delta?.content) {
        return { data: choice.delta.content, id: chunk.id, type: 'text' };
      }
      if (chunk.usage) {
        return { data: chunk.usage, id: chunk.id, type: 'usage' };
      }
      return { data: choice.finish_reason, id: chunk.id, type: 'stop' };
    }

    // Handle text content
    if (choice.delta?.content) {
      return { data: choice.delta.content, id: chunk.id, type: 'text' };
    }

    return null;
  } catch (error) {
    console.error('Stream transform error:', error);
    return {
      data: { message: 'Stream parsing error', error: error.message },
      id: chunk.id || 'error',
      type: 'error'
    };
  }
}

// Chat streaming endpoint
app.post('/api/chat', async (req, res) => {
  try {
    const { messages, model = 'gpt-4o-mini', stream: enableStreaming = true } = req.body;

    if (!messages || !Array.isArray(messages)) {
      return res.status(400).json({ error: 'Messages array is required' });
    }

    // Set headers for Server-Sent Events
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('Access-Control-Allow-Origin', '*');

    if (!enableStreaming) {
      // Non-streaming response
      const completion = await openai.chat.completions.create({
        model,
        messages,
        stream: false
      });

      const content = completion.choices[0]?.message?.content || '';
      res.write(`event: text\ndata: ${JSON.stringify(content)}\n\n`);
      res.write(`event: stop\ndata: ${JSON.stringify('stop')}\n\n`);
      res.end();
      return;
    }

    // Create streaming completion
    const stream = await openai.chat.completions.create({
      model,
      messages,
      stream: true,
      stream_options: { include_usage: true }
    });

    // Process stream
    for await (const chunk of stream) {
      const transformed = transformOpenAIStream(chunk);
      
      if (transformed) {
        console.log('Sending SSE:', transformed.type, transformed.data);
        // Send as Server-Sent Event
        res.write(`event: ${transformed.type}\ndata: ${JSON.stringify(transformed.data)}\n\n`);
      }
    }

    res.end();

  } catch (error) {
    console.error('Chat API error:', error);
    
    // Send error as SSE
    res.write(`event: error\ndata: ${JSON.stringify({
      message: error.message,
      type: 'ChatAPIError'
    })}\n\n`);
    res.end();
  }
});

// Serve the HTML page
app.get('/', (req, res) => {
  res.sendFile(join(__dirname, 'public', 'index.html'));
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
  console.log('Make sure to set your OPENAI_API_KEY environment variable');
}); 