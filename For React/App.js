// src/App.js
import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [visibleCount, setVisibleCount] = useState(5);
  const messagesEndRef = useRef(null);
  const [isFocused, setIsFocused] = useState(false);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    const userMessage = { role: "user", content: query };
    setMessages((prev) => [...prev, userMessage]);
    setQuery("");
    setLoading(true);

    try {
      const response = await axios.post("http://localhost:5000/search", {
        query,
      });

      const docs = response.data.results || [];
      const systemMessage = {
        role: "system",
        content:
          docs.length > 0
            ? `Here's what I found:`
            : "No relevant documents found.",
        documents: docs,
      };

      setMessages((prev) => [...prev, systemMessage]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "system", content: "Something went wrong. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header>
        <a><img src="/logo.png" alt="NeuroSearch - logo" />NeuroSearch</a>
      </header>

      <div className="chatui">
        <div className="chatmessages">
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role} ${msg.role === "user" ? "right" : "left"}`}>
              <div className="bubble">
                <p className="content">{msg.content}</p>
                {msg.documents && (
                  <div className="documents">
                    {msg.documents.slice(0, visibleCount).map((doc, idx) => (
                      <div key={idx} className="doccard">
                        <p className="doctitle">{doc.title}</p>
                        <p className="doctype">Type: {doc.type}</p>
                        <a href={doc.url} target="_blank" rel="noreferrer">
                          Open
                        </a>
                      </div>
                    ))}
                    {msg.documents.length > visibleCount && (
                      <button className="show-more-btn" onClick={() => setVisibleCount((prev) => prev + 5)}>
                        Show more
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="message system left">
              
                <span className="typing-indicator">
                  <span></span><span></span><span></span>
                </span>
              
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className={`inputarea ${isFocused ? "focused" : ""}`}>
          <form onSubmit={handleSearch} className="chat-input">
            <input
              type="text"
              value={query}
              placeholder="Ask me something..."
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              disabled={loading}
            />
            <button type="submit" disabled={loading}>Send</button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default App;
