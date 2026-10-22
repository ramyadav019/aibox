import { useState, useRef, useEffect } from "react";
import "./App.css";

interface Message {
  id: number;
  role: "user" | "bot";
  content: string;
}

interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [showWelcome, setShowWelcome] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const currentConversation = conversations.find(c => c.id === currentConversationId);
  const messages = currentConversation?.messages || [];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    const saved = localStorage.getItem("conversations");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setConversations(parsed);
        if (parsed.length > 0 && !currentConversationId) {
          setCurrentConversationId(parsed[0].id);
        }
      } catch {
        setConversations([]);
      }
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("conversations", JSON.stringify(conversations));
  }, [conversations]);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const createNewConversation = () => {
    const newConv: Conversation = {
      id: Date.now().toString(),
      title: "New chat",
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    setConversations(prev => [newConv, ...prev]);
    setCurrentConversationId(newConv.id);
    setMessages([]);
    setShowWelcome(true);
    setIsSidebarOpen(false);
  };

  const switchConversation = (id: string) => {
    setCurrentConversationId(id);
    setShowWelcome(messages.length === 0);
    setIsSidebarOpen(false);
  };

  const deleteConversation = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setConversations(prev => prev.filter(c => c.id !== id));
    if (currentConversationId === id) {
      const remaining = conversations.filter(c => c.id !== id);
      if (remaining.length > 0) {
        setCurrentConversationId(remaining[0].id);
      } else {
        setCurrentConversationId(null);
        setShowWelcome(true);
      }
    }
  };

  const updateConversationTitle = (id: string, title: string) => {
    setConversations(prev => prev.map(c => 
      c.id === id ? { ...c, title, updatedAt: Date.now() } : c
    ));
  };

  const getConversationTitle = (msgs: Message[]): string => {
    const firstUserMsg = msgs.find(m => m.role === "user");
    if (firstUserMsg) {
      return firstUserMsg.content.slice(0, 30) + (firstUserMsg.content.length > 30 ? "..." : "");
    }
    return "New chat";
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    let convId = currentConversationId;
    let isNewConversation = false;

    if (!convId) {
      isNewConversation = true;
      convId = Date.now().toString();
      const newConv: Conversation = {
        id: convId,
        title: getConversationTitle([{ id: Date.now(), role: "user", content: text }]),
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      setConversations(prev => [newConv, ...prev]);
      setCurrentConversationId(convId);
    }

    const userMessage: Message = {
      id: Date.now(),
      role: "user",
      content: text,
    };

    setConversations(prev => prev.map(c => 
      c.id === convId 
        ? { ...c, messages: [...c.messages, userMessage], updatedAt: Date.now(), title: isNewConversation ? getConversationTitle([userMessage]) : c.title }
        : c
    ));
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    setIsLoading(true);
    setShowWelcome(false);

    try {
      const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, thread_id: convId }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let botMessageId = Date.now() + 1;
      let botMessageContent = "";

      setConversations(prev => prev.map(c => 
        c.id === convId 
          ? { ...c, messages: [...c.messages, { id: botMessageId, role: "bot", content: "" }], updatedAt: Date.now() }
          : c
      ));

      const readStream = async () => {
        while (reader) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const data = JSON.parse(line.slice(6));
            if (data.done) continue;
            if (data.token) {
              botMessageContent += data.token;
              setConversations(prev => prev.map(c => 
                c.id === convId 
                  ? { ...c, messages: c.messages.map(msg => 
                      msg.id === botMessageId ? { ...msg, content: botMessageContent } : msg
                    ), updatedAt: Date.now() }
                  : c
              ));
            }
          }
        }
      };

      await readStream();
    } catch (error) {
      setConversations(prev => prev.map(c => 
        c.id === convId 
          ? { ...c, messages: [...c.messages, { id: Date.now(), role: "bot", content: "⚠️ Cannot reach server. Is the backend running?" }], updatedAt: Date.now() }
          : c
      ));
    } finally {
      setIsLoading(false);
      textareaRef.current?.focus();
    }
  };

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    if (days === 0) return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (days === 1) return "Yesterday";
    if (days < 7) return date.toLocaleDateString([], { weekday: 'short' });
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  return (
    <div className="app">
      <aside className={`sidebar ${isSidebarOpen ? "open" : ""}`}>
        <div className="sidebar-header">
          <h2>Chats</h2>
          <button className="new-chat-btn" onClick={createNewConversation} aria-label="New chat">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            New chat
          </button>
        </div>
        <div className="sidebar-content">
          {conversations.length === 0 ? (
            <div className="sidebar-empty">No conversations yet</div>
          ) : (
            <ul className="conversation-list">
              {conversations.map(conv => (
                <li key={conv.id} className={`conversation-item ${currentConversationId === conv.id ? "active" : ""}`}>
                  <button 
                    className="conversation-link"
                    onClick={() => switchConversation(conv.id)}
                    title={conv.title}
                  >
                    <span className="conversation-title">{conv.title || "New chat"}</span>
                    <span className="conversation-time">{formatTime(conv.updatedAt)}</span>
                  </button>
                  <button 
                    className="delete-btn"
                    onClick={(e) => deleteConversation(conv.id, e)}
                    aria-label="Delete conversation"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    </svg>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      {isSidebarOpen && (
        <div className="sidebar-overlay" onClick={() => setIsSidebarOpen(false)} />
      )}

      <div className="main-content">
        <header className="header">
          <button className="menu-btn" onClick={() => setIsSidebarOpen(true)} aria-label="Open menu">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
          <span>AI Assistant</span>
          <div className="status-pill">
            <div className="dot" />
            Online
          </div>
        </header>

        <main className="messages" id="messages">
          {showWelcome && messages.length === 0 && (
            <div className="welcome" id="welcome">
              <div className="welcome-icon">✦</div>
              <h1>How can I help you?</h1>
              <p>Ask me anything — I'm here to assist you.</p>
            </div>
          )}

          {messages.map((msg) => (
            <div key={msg.id} className={`message ${msg.role}`}>
              <div className="avatar">{msg.role === "bot" ? "✦" : "U"}</div>
              <div className="bubble">{msg.content.replace(/\n/g, "<br>")}</div>
            </div>
          ))}

          {isLoading && (
            <div className="message bot" id="typing">
              <div className="avatar">✦</div>
              <div className="bubble">
                <div className="typing">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </main>

        <footer className="input-wrap">
          <div style={{ width: "100%", maxWidth: 680 }}>
            <div className="input-box">
              <textarea
                ref={textareaRef}
                id="userInput"
                placeholder="Message AI Assistant..."
                rows={1}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
              />
              <button
                id="sendBtn"
                type="button"
                onClick={sendMessage}
                disabled={isLoading || !input.trim()}
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <line x1="12" y1="19" x2="12" y2="5" />
                  <polyline points="5 12 12 5 19 12" />
                </svg>
              </button>
            </div>
            <div className="hint">
              AI can make mistakes. Consider checking important info.
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}

export default App;