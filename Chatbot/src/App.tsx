import React, { useState, useRef, useEffect, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Sparkles,
  Square,
  Plus,
  Trash2,
  Copy,
  Check,
  RotateCcw,
  ThumbsUp,
  ThumbsDown,
  Menu,
  X,
  PanelLeftClose,
  PanelLeft,
  Search,
  MessageSquare,
  Code2,
  Lightbulb,
  PenTool,
  Compass,
  User,
  ArrowUp,
  ArrowUpRight,
} from "lucide-react";
import "./App.css";

interface Message {
  id?: string;
  role: "user" | "bot";
  content: string;
}

interface Conversation {
  thread_id: string;
  title: string;
  message_count: number;
  preview: string;
}

interface ElicitationItem {
  label: string;
  query: string;
}

interface ElicitationGroup {
  message: string;
  items: ElicitationItem[];
}

function parseMessageContent(content: string): {
  cleanText: string;
  elicitationGroup: ElicitationGroup | null;
} {
  let cleanText = content || "";
  let elicitationGroup: ElicitationGroup | null = null;

  // 1. Extract ElicitationsGroup if present (even across multiple lines)
  const groupRegex = /<ElicitationsGroup(?:\s+message=["']([^"']*)["'])?[^>]*>([\s\S]*?)<\/ElicitationsGroup>/i;
  const match = content.match(groupRegex);
  if (match) {
    const message = match[1] || "Where would you like to go next?";
    const inner = match[2];
    const items: ElicitationItem[] = [];
    const itemRegex = /<Elicitation\s+label=["']([^"']*)["']\s+query=["']([^"']*)["'][^>]*\/?>/gi;
    let itemMatch: RegExpExecArray | null;
    while ((itemMatch = itemRegex.exec(inner)) !== null) {
      items.push({ label: itemMatch[1], query: itemMatch[2] });
    }
    // Also support reversed query/label order
    if (items.length === 0) {
      const itemRegexRev = /<Elicitation\s+query=["']([^"']*)["']\s+label=["']([^"']*)["'][^>]*\/?>/gi;
      while ((itemMatch = itemRegexRev.exec(inner)) !== null) {
        items.push({ label: itemMatch[2], query: itemMatch[1] });
      }
    }
    if (items.length > 0) {
      elicitationGroup = { message, items };
    }
  }

  // 2. Remove full ElicitationsGroup block
  cleanText = cleanText.replace(/<ElicitationsGroup[\s\S]*?<\/ElicitationsGroup>/gi, "");

  // 3. Remove in-flight / partial ElicitationsGroup block during streaming
  cleanText = cleanText.replace(/<ElicitationsGroup[\s\S]*$/gi, "");

  // 4. Remove Steps / Step / thought blocks
  cleanText = cleanText.replace(/<(?:Steps|thought)[\s\S]*?<\/(?:Steps|thought)>/gi, "");
  cleanText = cleanText.replace(/<(?:Steps|thought)[\s\S]*$/gi, "");

  // 5. Remove any remaining XML tags like <Elicitation .../>, <Step .../>
  cleanText = cleanText.replace(/<\/?[a-zA-Z]+(?::[a-zA-Z]+)?(?:\s+[^>]*?)?\/?>/g, "");

  // 6. Clean any trailing unclosed tag during streaming
  cleanText = cleanText.replace(/<[a-zA-Z\/][^>]*$/g, "");

  return { cleanText: cleanText.trim(), elicitationGroup };
}

const STARTER_PROMPTS = [
  {
    icon: Lightbulb,
    title: "Explain a concept",
    description: "Explain quantum computing in simple terms with an analogy",
    prompt:
      "Explain quantum computing in simple terms using everyday analogies.",
  },
  {
    icon: Code2,
    title: "Code assistance",
    description: "Write a Python script for asynchronous data fetching",
    prompt:
      "Write a clean Python script to fetch data asynchronously from an API and save to a JSON file.",
  },
  {
    icon: PenTool,
    title: "Draft a message",
    description: "Compose a professional project proposal email",
    prompt:
      "Draft a concise, professional email proposing a new AI automation project to my team lead.",
  },
  {
    icon: Compass,
    title: "Compare & Analyze",
    description: "Compare LangGraph with AutoGen & CrewAI",
    prompt:
      "Compare LangGraph with AutoGen and CrewAI: what are their key strengths and recommended use cases?",
  },
];

// Helper to copy text to clipboard
async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();
      const successful = document.execCommand("copy");
      document.body.removeChild(textarea);
      return successful;
    }
  } catch {
    return false;
  }
}

// Custom Markdown Code Block component with Copy button
const CodeBlock: React.FC<{
  inline?: boolean;
  className?: string;
  children?: React.ReactNode;
}> = ({ inline, className, children, ...props }) => {
  const [copied, setCopied] = useState(false);
  const match = /language-(\w+)/.exec(className || "");
  const language = match ? match[1] : "";
  const codeContent = String(children).replace(/\n$/, "");

  const handleCopy = async () => {
    const ok = await copyToClipboard(codeContent);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (inline) {
    return (
      <code className="inline-code" {...props}>
        {children}
      </code>
    );
  }

  return (
    <div className="code-block-wrapper">
      <div className="code-block-header">
        <span className="code-block-lang">{language || "code"}</span>
        <button
          className="copy-code-btn"
          onClick={handleCopy}
          aria-label="Copy code"
          type="button"
        >
          {copied ? (
            <>
              <Check size={14} className="copy-icon-success" />
              <span>Copied!</span>
            </>
          ) : (
            <>
              <Copy size={14} />
              <span>Copy code</span>
            </>
          )}
        </button>
      </div>
      <pre className="code-block-pre">
        <code className={className} {...props}>
          {children}
        </code>
      </pre>
    </div>
  );
};

const API_BASE = ((import.meta as any).env?.VITE_API_BASE || "").replace(/\/+$/, "");

function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [threadId, setThreadId] = useState<string>(() => {
    return window.location.hash.slice(1) || Date.now().toString();
  });
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false); // mobile drawer
  const [desktopSidebarOpen, setDesktopSidebarOpen] = useState(true); // desktop toggle
  const [searchQuery, setSearchQuery] = useState("");
  const [feedback, setFeedback] = useState<Record<number, "up" | "down">>({});

  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Auto scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Dismiss mobile keyboard
  const handleDismissKeyboard = () => {
    if (document.activeElement === textareaRef.current) {
      textareaRef.current?.blur();
    }
  };

  // Dismiss keyboard on mobile back button (popstate) or Escape key
  useEffect(() => {
    const handleDismiss = () => {
      textareaRef.current?.blur();
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        textareaRef.current?.blur();
      }
    };
    window.addEventListener("popstate", handleDismiss);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("popstate", handleDismiss);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  // Load chat history and restore selected thread on mount
  useEffect(() => {
    const init = async () => {
      await loadConversations();
      const hash = window.location.hash.slice(1);
      if (hash) {
        try {
          const res = await fetch(`${API_BASE}/conversation/${hash}`);
          if (res.ok) {
            const data = await res.json();
            setMessages(
              (data.messages || []).map((m: { role: string; content: string }) => ({
                role: m.role === "user" ? "user" : "bot",
                content: m.content,
              }))
            );
          }
        } catch {}
      }
    };
    init();
  }, []);

  const loadConversations = async () => {
    try {
      const res = await fetch(`${API_BASE}/conversation`);
      const data = await res.json();
      setConversations(data.conversations || []);
    } catch (err) {
      console.error("Failed to load conversations", err);
    }
  };

  const switchConversation = async (id: string) => {
    if (id === threadId) {
      setSidebarOpen(false);
      return;
    }
    setThreadId(id);
    window.location.hash = id;
    setSidebarOpen(false);
    try {
      const res = await fetch(`${API_BASE}/conversation/${id}`);
      const data = await res.json();
      setMessages(
        (data.messages || []).map((m: { role: string; content: string }) => ({
          role: m.role === "user" ? "user" : "bot",
          content: m.content,
        })),
      );
    } catch (err) {
      console.error("Failed to switch conversation", err);
    }
  };

  const newChat = () => {
    const id = Date.now().toString();
    setThreadId(id);
    window.location.hash = id;
    setMessages([]);
    setInput("");
    setSidebarOpen(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const deleteConversation = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try {
      await fetch(`${API_BASE}/conversation/${id}`, { method: "DELETE" });
      setConversations((prev) => prev.filter((c) => c.thread_id !== id));
      if (threadId === id) {
        const newId = Date.now().toString();
        setThreadId(newId);
        window.location.hash = newId;
        setMessages([]);
      }
    } catch (err) {
      console.error("Failed to delete conversation", err);
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 180) + "px";
  };

  const stop = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setIsLoading(false);
  };

  const executeSend = async (textToSend: string) => {
    const text = textToSend.trim();
    if (!text) return;

    if (isLoading) {
      stop();
      return;
    }

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      if (window.innerWidth <= 768 || "ontouchstart" in window) {
        textareaRef.current.blur();
      }
    }
    setIsLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, thread_id: threadId }),
        signal: controller.signal,
      });

      if (!res.body) {
        throw new Error("No response stream");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      const botId = `bot-${Date.now()}`;
      let botCreated = false;
      let streamFinished = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.done) {
              streamFinished = true;
              break;
            }

            if (data.token) {
              if (!botCreated) {
                botCreated = true;
                setMessages((prev) => [
                  ...prev,
                  { id: botId, role: "bot", content: data.token },
                ]);
              } else {
                setMessages((prev) =>
                  prev.map((m) =>
                    (m as any).id === botId
                      ? { ...m, content: m.content + data.token }
                      : m,
                  ),
                );
              }
            }
          } catch (err) {
            console.error("Stream parse error:", err);
          }
        }

        if (streamFinished) {
          try {
            await reader.cancel();
          } catch {}
          break;
        }
      }

      setIsLoading(false);
      abortRef.current = null;
      loadConversations();
    } catch (e: any) {
      if (e?.name !== "AbortError") {
        setMessages((prev) => [
          ...prev,
          {
            role: "bot",
            content:
              "⚠️ Unable to connect to server. Please verify the backend is running.",
          },
        ]);
      }
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }
  };

  const handleSend = () => executeSend(input);

  const handleRegenerate = (index: number) => {
    // Find the preceding user message
    for (let i = index - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        executeSend(messages[i].content);
        break;
      }
    }
  };

  const toggleFeedback = (index: number, type: "up" | "down") => {
    setFeedback((prev) => ({
      ...prev,
      [index]: prev[index] === type ? (null as any) : type,
    }));
  };

  // Filter conversations
  const filteredConversations = useMemo(() => {
    const sorted = [...conversations].sort((a, b) =>
      b.thread_id.localeCompare(a.thread_id, undefined, { numeric: true })
    );
    if (!searchQuery.trim()) return sorted;
    const q = searchQuery.toLowerCase();
    return sorted.filter(
      (c) =>
        (c.title && c.title.toLowerCase().includes(q)) ||
        (c.preview && c.preview.toLowerCase().includes(q)),
    );
  }, [conversations, searchQuery]);

  // Greeting
  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  }, []);

  return (
    <div
      className={`app ${desktopSidebarOpen ? "desktop-sidebar-expanded" : "desktop-sidebar-collapsed"}`}
    >
      {/* Sidebar overlay for mobile */}
      <div
        className={`sidebar-overlay ${sidebarOpen ? "active" : ""}`}
        onClick={() => setSidebarOpen(false)}
        aria-hidden="true"
      />

      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-header">
          <div className="brand-row">
            <div className="brand-logo">
              <Sparkles className="sparkle-icon" size={20} />
              <span className="brand-title">AI Assistant</span>
            </div>
            <button
              className="icon-btn mobile-close-btn"
              onClick={() => setSidebarOpen(false)}
              aria-label="Close sidebar"
            >
              <X size={18} />
            </button>
          </div>

          <button className="new-chat-btn" onClick={newChat}>
            <Plus size={18} />
            <span>New chat</span>
          </button>

          {conversations.length > 0 && (
            <div className="search-bar">
              <Search size={14} className="search-icon" />
              <input
                type="text"
                placeholder="Search chats..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button
                  className="clear-search"
                  onClick={() => setSearchQuery("")}
                >
                  <X size={12} />
                </button>
              )}
            </div>
          )}
        </div>

        <div className="sidebar-content">
          {conversations.length === 0 ? (
            <div className="sidebar-empty">
              <MessageSquare size={24} className="empty-icon" />
              <p>No chat history yet</p>
              <span>Your conversations will appear here</span>
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="sidebar-empty">
              <p>No matching chats found</p>
            </div>
          ) : (
            <ul className="conversation-list">
              {filteredConversations.map((c) => {
                const isActive = threadId === c.thread_id;
                return (
                  <li
                    key={c.thread_id}
                    className={`conversation-item ${isActive ? "active" : ""}`}
                  >
                    <button
                      className="conversation-link"
                      onClick={() => switchConversation(c.thread_id)}
                      title={c.title || "Chat"}
                    >
                      <MessageSquare size={16} className="item-icon" />
                      <div className="conversation-meta">
                        <span className="conversation-title">
                          {c.title || "New chat"}
                        </span>
                        {c.preview && (
                          <span className="conversation-preview">
                            {c.preview}
                          </span>
                        )}
                      </div>
                    </button>
                    <button
                      className="delete-btn"
                      onClick={(e) => deleteConversation(e, c.thread_id)}
                      title="Delete chat"
                      aria-label="Delete chat"
                    >
                      <Trash2 size={14} />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="sidebar-footer">
          <div className="user-profile">
            <div className="user-avatar-mini">
              <User size={14} />
            </div>
            <div className="user-info">
              <span className="user-name">Local User</span>
              <span className="user-status">Ready</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main chat view */}
      <div className="main-content">
        {/* Top App Bar */}
        <header className="header">
          <div className="header-left">
            {/* Mobile menu toggle */}
            <button
              className="icon-btn mobile-menu-btn"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open menu"
            >
              <Menu size={20} />
            </button>

            {/* Desktop collapse toggle */}
            <button
              className="icon-btn desktop-collapse-btn"
              onClick={() => setDesktopSidebarOpen(!desktopSidebarOpen)}
              title={desktopSidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
              aria-label="Toggle sidebar"
            >
              {desktopSidebarOpen ? (
                <PanelLeftClose size={20} />
              ) : (
                <PanelLeft size={20} />
              )}
            </button>

            <div className="model-selector">
              <span className="model-name">Assistant</span>
              <span className="model-badge">Active</span>
            </div>
          </div>

          <div className="header-right">
            <button
              className="new-chat-top-btn"
              onClick={newChat}
              title="New chat"
            >
              <Plus size={16} />
              <span className="btn-label">New chat</span>
            </button>
          </div>
        </header>

        {/* Messages scroll area */}
        <main
          className="messages-container"
          onClick={handleDismissKeyboard}
          onTouchStart={handleDismissKeyboard}
        >
          <div className="messages-inner">
            {messages.length === 0 && !isLoading && (
              <div className="welcome-section">
                <div className="welcome-glow-icon">
                  <Sparkles size={36} />
                </div>
                <h1 className="welcome-title">
                  {greeting},{" "}
                  <span className="gradient-text">how can I help?</span>
                </h1>
                <p className="welcome-subtitle">
                  Ask questions, debug code, brainstorm ideas, or summarize
                  text.
                </p>

                {/* Starters Grid */}
                <div className="starters-grid">
                  {STARTER_PROMPTS.map((item, idx) => {
                    const Icon = item.icon;
                    return (
                      <button
                        key={idx}
                        className="starter-card"
                        onClick={() => executeSend(item.prompt)}
                      >
                        <div className="starter-icon-wrap">
                          <Icon size={18} />
                        </div>
                        <div className="starter-content">
                          <span className="starter-title">{item.title}</span>
                          <span className="starter-desc">
                            {item.description}
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Message feed */}
            {messages.map((m, i) => {
              const isUser = m.role === "user";
              const isStreamingCurrent =
                isLoading && !isUser && i === messages.length - 1;

              const { cleanText, elicitationGroup } = !isUser
                ? parseMessageContent(m.content)
                : { cleanText: m.content, elicitationGroup: null };

              return (
                <div
                  key={i}
                  className={`message-row ${isUser ? "user" : "bot"}`}
                >
                  <div className="message-body">
                    <div className="bubble">
                      {isUser ? (
                        <div className="user-message-text">{m.content}</div>
                      ) : (
                        <div className="markdown-content">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              code: CodeBlock as any,
                            }}
                          >
                            {cleanText}
                          </ReactMarkdown>
                          {isStreamingCurrent && (
                            <span className="streaming-cursor" />
                          )}
                        </div>
                      )}
                    </div>

                    {/* Interactive Follow-up Suggestions (Gemini/ChatGPT style) */}
                    {elicitationGroup && elicitationGroup.items.length > 0 && (
                      <div className="followup-container">
                        <div className="followup-header">
                          <Sparkles size={13} className="followup-icon" />
                          <span>{elicitationGroup.message}</span>
                        </div>
                        <div className="followup-chips">
                          {elicitationGroup.items.map((item, idx) => (
                            <button
                              key={idx}
                              className="followup-chip"
                              onClick={() => executeSend(item.query)}
                              type="button"
                              title={item.query}
                            >
                              <span className="followup-chip-label">
                                {item.label}
                              </span>
                              <ArrowUpRight
                                size={13}
                                className="followup-chip-arrow"
                              />
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Action Bar for bot only */}
                    {!isUser && (
                      <div className="message-actions">
                        <button
                          className={`action-btn ${
                            feedback[i] === "up" ? "active-feedback" : ""
                          }`}
                          onClick={() => toggleFeedback(i, "up")}
                          title="Good response"
                          aria-label="Thumbs up"
                        >
                          <ThumbsUp size={15} />
                        </button>
                        <button
                          className={`action-btn ${
                            feedback[i] === "down" ? "active-feedback" : ""
                          }`}
                          onClick={() => toggleFeedback(i, "down")}
                          title="Bad response"
                          aria-label="Thumbs down"
                        >
                          <ThumbsDown size={15} />
                        </button>
                        <button
                          className="action-btn"
                          onClick={() => handleRegenerate(i)}
                          title="Regenerate response"
                          aria-label="Regenerate response"
                        >
                          <RotateCcw size={15} />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Typing indicator placeholder before first token */}
            {isLoading &&
              (messages.length === 0 ||
                messages[messages.length - 1]?.role !== "bot") && (
                <div className="message-row bot">
                  <div className="message-body">
                    <div className="bubble">
                      <div className="typing-indicator">
                        <span className="dot" />
                        <span className="dot" />
                        <span className="dot" />
                      </div>
                    </div>
                  </div>
                </div>
              )}

            <div ref={bottomRef} />
          </div>
        </main>

        {/* Input Bar */}
        <footer className="composer-footer">
          <div className="composer-container">
            <div className="composer-box">
              <textarea
                ref={textareaRef}
                id="userInput"
                className="composer-textarea"
                placeholder="Ask anything or request help..."
                rows={1}
                value={input}
                onChange={handleInput}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
              />

              <div className="composer-controls">
                {isLoading ? (
                  <button
                    type="button"
                    className="composer-action-btn stop-btn"
                    onClick={stop}
                    title="Stop generating"
                    aria-label="Stop generation"
                  >
                    <Square size={14} fill="currentColor" />
                  </button>
                ) : (
                  <button
                    type="button"
                    className="composer-action-btn send-btn"
                    onClick={handleSend}
                    disabled={!input.trim()}
                    title="Send message"
                    aria-label="Send message"
                  >
                    <ArrowUp size={18} strokeWidth={2.5} />
                  </button>
                )}
              </div>
            </div>

            <div className="composer-footnote">
              AI can make mistakes. Verify important information.
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}

export default App;
