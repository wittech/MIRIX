import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { tomorrow } from 'react-syntax-highlighter/dist/esm/styles/prism';
import './ChatBubble.css';

const ChatBubble = ({ message }) => {
  const { type, content, timestamp, images, isStreaming } = message;

  const formatTime = (date) => {
    // Handle both Date objects and ISO string timestamps
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    return dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const renderContent = () => {
    if (type === 'error') {
      return <div className="error-content">{content}</div>;
    }

    // Simple approach: just render the text with preserved whitespace
    // Split by newlines and render each line as a separate element
    const lines = (content || '').split('\n');
    
    return (
      <div className="content-text">
        {lines.map((line, index) => (
          <div key={index} className="content-line">
            {line || '\u00A0'} {/* Use non-breaking space for empty lines */}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className={`chat-bubble ${type}`}>
      <div className="bubble-header">
        <span className="sender">
          {type === 'user' ? '👤 You' : type === 'assistant' ? '🤖 MIRIX' : '❌ Error'}
        </span>
        <span className="timestamp">{formatTime(timestamp)}</span>
        {isStreaming && <span className="streaming-indicator">●</span>}
      </div>
      
      {images && images.length > 0 && (
        <div className="message-images">
          {images.map((image, index) => (
            <div key={index} className="image-preview">
              <img 
                src={image.url || (image.path ? `file://${image.path}` : image.name)} 
                alt={`Attachment ${index + 1}`}
                onError={(e) => {
                  // If file:// URL doesn't work, try without protocol for electron
                  if (image.path && e.target.src.startsWith('file://')) {
                    e.target.src = image.path;
                  }
                }}
                onLoad={(e) => {
                  // Revoke object URL after loading to prevent memory leaks
                  if (image.url && image.url.startsWith('blob:')) {
                    URL.revokeObjectURL(image.url);
                  }
                }}
              />
              <span className="image-name">{image.name}</span>
            </div>
          ))}
        </div>
      )}
      
      <div className="bubble-content">
        {renderContent()}
      </div>
    </div>
  );
};

export default ChatBubble; 