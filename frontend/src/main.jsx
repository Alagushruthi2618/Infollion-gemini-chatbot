import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  FileText,
  Image as ImageIcon,
  Loader2,
  MessageSquare,
  Plus,
  Send,
} from "lucide-react";
import "./styles.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function api(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

function App() {
  const [chats, setChats] = useState([]);
  const [activeChat, setActiveChat] = useState(null);
  const [message, setMessage] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [uploading, setUploading] = useState("");
  const [error, setError] = useState("");
  const documentInputRef = useRef(null);
  const imageInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    bootstrap();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeChat?.messages, isSending]);

  async function bootstrap() {
    try {
      const list = await api("/api/chats");
      if (list.chats.length > 0) {
        setChats(list.chats);
        await openChat(list.chats[0].id);
      } else {
        await newChat();
      }
    } catch (err) {
      setError(err.message);
    }
  }

  async function refreshChats(nextActiveChat = activeChat) {
    const list = await api("/api/chats");
    setChats(list.chats);
    if (nextActiveChat) {
      setActiveChat(nextActiveChat);
    }
  }

  async function newChat() {
    setError("");
    const data = await api("/api/chats", { method: "POST" });
    setActiveChat(data.chat);
    const list = await api("/api/chats");
    setChats(list.chats);
    setMessage("");
  }

  async function openChat(chatId) {
    setError("");
    const data = await api(`/api/chats/${chatId}`);
    setActiveChat(data.chat);
  }

  async function sendMessage(event) {
    event?.preventDefault();
    const text = message.trim();
    if (!text || !activeChat || isSending) return;

    setMessage("");
    setError("");
    setIsSending(true);
    const optimisticChat = {
      ...activeChat,
      messages: [
        ...activeChat.messages,
        {
          id: `local-${Date.now()}`,
          role: "user",
          content: text,
          createdAt: new Date().toISOString(),
        },
      ],
    };
    setActiveChat(optimisticChat);

    try {
      const data = await api(`/api/chats/${activeChat.id}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      await refreshChats(data.chat);
    } catch (err) {
      setActiveChat(activeChat);
      setMessage(text);
      setError(err.message);
    } finally {
      setIsSending(false);
    }
  }

  async function uploadFile(kind, file) {
    if (!file || !activeChat) return;
    setError("");
    setUploading(kind);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const data = await api(`/api/chats/${activeChat.id}/upload/${kind}`, {
        method: "POST",
        body: formData,
      });
      await refreshChats(data.chat);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading("");
      if (kind === "document" && documentInputRef.current) {
        documentInputRef.current.value = "";
      }
      if (kind === "image" && imageInputRef.current) {
        imageInputRef.current.value = "";
      }
    }
  }

  const messages = activeChat?.messages || [];

  return (
    <main className="appShell">
      <aside className="sidebar">
        <button className="newChatButton" onClick={newChat}>
          <Plus size={18} />
          New Chat
        </button>
        <div className="chatList">
          {chats.map((chat) => (
            <button
              key={chat.id}
              className={`chatListItem ${activeChat?.id === chat.id ? "active" : ""}`}
              onClick={() => openChat(chat.id)}
            >
              <MessageSquare size={17} />
              <span>{chat.title}</span>
            </button>
          ))}
        </div>
      </aside>

      <section className="chatPanel">
        <header className="topBar">
          <div>
            <h1>Gemini Chatbot</h1>
            <p>{activeChat ? activeChat.title : "Loading chat"}</p>
          </div>
          <div className="fileStatus">
            <span className={activeChat?.document ? "ready" : ""}>
              <FileText size={15} />
              {activeChat?.document ? activeChat.document.name : "No document"}
            </span>
            <span className={activeChat?.image ? "ready" : ""}>
              <ImageIcon size={15} />
              {activeChat?.image ? activeChat.image.name : "No image"}
            </span>
          </div>
        </header>

        {activeChat?.image?.preview && (
          <div className="imagePreview">
            <img src={activeChat.image.preview} alt={activeChat.image.name} />
          </div>
        )}

        <div className="messages">
          {messages.length === 0 && (
            <div className="emptyState">
              Upload a document or image, then ask Gemini about it.
            </div>
          )}
          {messages.map((item) => (
            <article key={item.id} className={`message ${item.role}`}>
              <div className="bubble">{item.content}</div>
            </article>
          ))}
          {isSending && (
            <article className="message bot">
              <div className="bubble loadingBubble">
                <Loader2 size={17} className="spin" />
                Thinking
              </div>
            </article>
          )}
          <div ref={messagesEndRef} />
        </div>

        {error && <div className="errorBanner">{error}</div>}

        <form className="composer" onSubmit={sendMessage}>
          <input
            ref={documentInputRef}
            type="file"
            accept=".pdf,.txt,application/pdf,text/plain"
            onChange={(event) => uploadFile("document", event.target.files[0])}
            hidden
          />
          <input
            ref={imageInputRef}
            type="file"
            accept=".png,.jpg,.jpeg,image/png,image/jpeg"
            onChange={(event) => uploadFile("image", event.target.files[0])}
            hidden
          />
          <button
            type="button"
            className="iconButton"
            title="Upload PDF or TXT document"
            onClick={() => documentInputRef.current?.click()}
            disabled={Boolean(uploading)}
          >
            {uploading === "document" ? <Loader2 className="spin" /> : <FileText />}
          </button>
          <button
            type="button"
            className="iconButton"
            title="Upload PNG or JPG image"
            onClick={() => imageInputRef.current?.click()}
            disabled={Boolean(uploading)}
          >
            {uploading === "image" ? <Loader2 className="spin" /> : <ImageIcon />}
          </button>
          <input
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Ask about the chat, document, or image..."
          />
          <button className="sendButton" type="submit" disabled={isSending || !message.trim()}>
            <Send size={18} />
            Send
          </button>
        </form>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
