import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api';
import type { ChatMessage, ChatThread, Property, User } from '../types';

const WS_BASE = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}${import.meta.env.VITE_API_BASE_URL ?? '/api'}`;

export default function ChatPage({ user }: { user: User }) {
  const [properties, setProperties] = useState<Property[]>([]);
  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [selectedThread, setSelectedThread] = useState<ChatThread | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [error, setError] = useState('');
  const [typingUsers, setTypingUsers] = useState<Record<string, boolean>>({});
  const [connecting, setConnecting] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const selectedThreadRef = useRef<ChatThread | null>(null);
  const typingTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const typingTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const messagesRef = useRef<HTMLDivElement | null>(null);

  async function loadThreads() {
    try {
      const threadRows = await api.chatThreads(user.id);
      setThreads(threadRows);
      if (!selectedThread && threadRows.length > 0) {
        setSelectedThread(threadRows[0]);
        selectedThreadRef.current = threadRows[0];
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load chat threads');
    }
  }

  async function loadProperties() {
    try {
      const props = await api.properties(user.id);
      setProperties(props);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load properties');
    }
  }

  async function loadMessages(thread: ChatThread) {
    try {
      const loadedMessages = await api.chatMessages(user.id, thread.id);
      setMessages(loadedMessages);
      setSelectedThread(thread);
      selectedThreadRef.current = thread;
      await api.markChatThreadRead(user.id, thread.id);
      await loadThreads();
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load messages');
    }
  }

  async function createConversation(propertyId: string) {
    try {
      const thread = await api.createChatThread(user.id, propertyId);
      await loadThreads();
      setSelectedThread(thread);
      selectedThreadRef.current = thread;
      await loadMessages(thread);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : 'Unable to start conversation');
    }
  }

  async function handleSendMessage() {
    if (!selectedThread || !newMessage.trim()) return;
    try {
      const sentMessage = await api.sendChatMessage(user.id, selectedThread.id, {
        content: newMessage.trim(),
      });
      setMessages((prev) => [...prev, sentMessage]);
      setNewMessage('');
      setError('');
      loadThreads();
    } catch (sendError) {
      setError(sendError instanceof Error ? sendError.message : 'Unable to send message');
    }
  }

  function handleTyping(isTyping: boolean) {
    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) return;
    socketRef.current.send(JSON.stringify({ type: 'typing', is_typing: isTyping }));
    if (typingTimeout.current) {
      clearTimeout(typingTimeout.current);
    }
    if (isTyping) {
      typingTimeout.current = setTimeout(() => {
        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
          socketRef.current.send(JSON.stringify({ type: 'typing', is_typing: false }));
        }
      }, 1200);
    }
  }

  useEffect(() => {
    loadThreads();
    loadProperties();
    return () => {
      if (typingTimeout.current) {
        clearTimeout(typingTimeout.current);
      }
      // clear any outstanding typing timers
      Object.values(typingTimers.current).forEach((t) => clearTimeout(t));
    };
  }, [user.id]);

  useEffect(() => {
    if (!selectedThread) return;
    const websocket = new WebSocket(`${WS_BASE}/chat/ws?thread_id=${selectedThread.id}&user_id=${user.id}`);
    socketRef.current = websocket;
    setConnecting(true);

    websocket.onopen = () => {
      setConnecting(false);
    };

    websocket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as {
          type: string;
          message?: ChatMessage;
          user_id?: string;
          is_typing?: boolean;
          status?: string;
        };
        const currentThread = selectedThreadRef.current;
        if (payload.type === 'message' && payload.message) {
          if (payload.message.thread_id === currentThread?.id) {
            setMessages((prev) => [...prev, payload.message!]);
          }
          loadThreads();
        }
        if (payload.type === 'typing' && payload.user_id) {
          if (payload.status === 'connected') {
            return;
          }
          const uid = payload.user_id as string;
          if (typingTimers.current[uid]) {
            clearTimeout(typingTimers.current[uid]);
            delete typingTimers.current[uid];
          }
          setTypingUsers((prev) => ({ ...prev, [uid]: Boolean(payload.is_typing) }));
          typingTimers.current[uid] = setTimeout(() => {
            setTypingUsers((prev) => ({ ...prev, [uid]: false }));
            delete typingTimers.current[uid];
          }, 1500) as unknown as ReturnType<typeof setTimeout>;
        }
        if (payload.type === 'read' && payload.user_id) {
          loadThreads();
        }
      } catch {
        // ignore invalid websocket data
      }
    };

    websocket.onclose = () => {
      setConnecting(false);
    };

    websocket.onerror = () => {
      setConnecting(false);
    };

    return () => {
      websocket.close();
      socketRef.current = null;
    };
  }, [selectedThread?.id]);

  const currentTypingUsers = useMemo(() => {
    return Object.entries(typingUsers)
      .filter(([userId, typing]) => typing && userId !== user.id)
      .map(([userId]) => userId);
  }, [typingUsers, user.id]);

  const zoomChatLink = useMemo(() => {
    if (!selectedThread) return null;
    const cmc = selectedThread.cmc_user;
    const jid = cmc.zoom_user_id || cmc.email;
    return `zoommtg://zoom.us/chat?jid=${encodeURIComponent(jid)}`;
  }, [selectedThread]);

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <main className="chat-layout">
      <aside className="chat-sidebar">
        <section className="card">
          <h3>Conversations</h3>
          <div className="chat-thread-list">
            {threads.map((thread) => (
              <button
                key={thread.id}
                type="button"
                className={thread.id === selectedThread?.id ? 'thread-item active' : 'thread-item'}
                onClick={() => loadMessages(thread)}
              >
                <div>
                  <strong>{thread.property.name}</strong>
                  <p className="muted">CMC: {thread.cmc_user.full_name}</p>
                </div>
                <div className="thread-count">
                  {thread.unread_count > 0 ? <span>{thread.unread_count}</span> : null}
                </div>
              </button>
            ))}
            {threads.length === 0 && <p className="muted">No conversations yet.</p>}
          </div>
        </section>

        <section className="card">
          <h3>Start a new conversation</h3>
          <select onChange={(e) => createConversation(e.target.value)} value="">
            <option value="">Select property</option>
            {properties.map((property) => (
              <option key={property.id} value={property.id}>{property.name}</option>
            ))}
          </select>
          <p className="muted">Select an assigned property to open the CMC thread.</p>
        </section>
      </aside>

      <section className="chat-panel card">
        {error && <p className="error">{error}</p>}
        <div className="chat-panel-header">
          <div>
            <h3>{selectedThread ? `${selectedThread.property.name} conversation` : 'Select a thread'}</h3>
            <p className="muted">{selectedThread ? `CMC: ${selectedThread.cmc_user.full_name}` : 'Pick a conversation from the left pane.'}</p>
          </div>
          <div className="chat-actions">
            {zoomChatLink ? (
              <a className="secondary-button" href={zoomChatLink} target="_blank" rel="noreferrer">
                Open Zoom Chat
              </a>
            ) : null}
            <div className="status-pill">{connecting ? 'Connecting…' : 'Live chat'}</div>
          </div>
        </div>

        <div className="chat-messages" ref={messagesRef}>
          {!selectedThread && <p className="muted">Choose a conversation to see messages.</p>}
          {selectedThread && messages.length === 0 && <p className="muted">No messages yet. Say hello.</p>}
          {selectedThread && messages.map((message) => (
            <div key={message.id} className={message.sender.id === user.id ? 'chat-message outgoing' : 'chat-message incoming'}>
              <div className="message-meta">
                <strong>{message.sender.full_name}</strong>
                <span>{new Date(message.created_at).toLocaleString()}</span>
              </div>
              <div className="message-content">{message.content}</div>
              <div className="message-status">
                {message.sender.id === user.id ? (
                  <span>{message.read_by.includes(selectedThread?.cmc_user.id ?? '') ? 'Read' : 'Sent'}</span>
                ) : null}
              </div>
            </div>
          ))}
        </div>

        {selectedThread && currentTypingUsers.length > 0 && (
          <p className="muted">{currentTypingUsers.length === 1 ? 'CMC is typing…' : 'Typing…'}</p>
        )}

        {selectedThread && (
          <div className="chat-input-row">
            <textarea
              rows={2}
              value={newMessage}
              onChange={(event) => {
                setNewMessage(event.target.value);
                handleTyping(event.target.value.length > 0);
              }}
              placeholder="Type your message..."
            />
            <button type="button" onClick={handleSendMessage} disabled={!newMessage.trim()}>Send</button>
          </div>
        )}
      </section>
    </main>
  );
}
