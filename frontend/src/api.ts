import type {
  Assignment,
  Call,
  ChatMessage,
  ChatThread,
  Property,
  Slot,
  StaffTraining,
  User,
  AdminDashboard,
} from "./types";

import oktaAuth from './oktaAuth';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

export async function apiFetch<T>(
  path: string,
  userId?: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (userId) headers.set("X-User-Id", userId);
  // Attach access token if present
  try {
    const token = await oktaAuth.tokenManager.get('accessToken') as unknown;
    const maybeToken = token as { accessToken?: string; access_token?: string } | string | null | undefined;
    const access =
      (typeof maybeToken === 'object' && maybeToken !== null
        ? maybeToken.accessToken ?? maybeToken.access_token
        : typeof maybeToken === 'string'
          ? maybeToken
          : undefined);
    if (access) {
      headers.set('Authorization', `Bearer ${access}`);
    }
  } catch (e) {
    // ignore if no token
  }
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  users: () => apiFetch<User[]>("/debug/seed-users"),
  properties: (userId: string) => apiFetch<Property[]>("/properties", userId),
  training: (userId: string, propertyId: string) =>
    apiFetch<StaffTraining[]>(`/properties/${propertyId}/training`, userId),
  calls: (userId: string) => apiFetch<Call[]>("/scheduling/calls", userId),
  slots: (userId: string, propertyId: string, start: string, end: string) =>
    apiFetch<Slot[]>(
      `/scheduling/slots?property_id=${propertyId}&start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}&timezone=Asia/Kolkata&duration_minutes=30`,
      userId,
    ),
  book: (userId: string, payload: Record<string, unknown>) =>
    apiFetch<Call>("/scheduling/book", userId, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  acceptCall: (userId: string, callId: string) =>
    apiFetch<Call>(`/scheduling/${callId}/accept`, userId, { method: "POST" }),
  rescheduleCall: (
    userId: string,
    callId: string,
    payload: Record<string, unknown>,
  ) =>
    apiFetch<Call>(`/scheduling/${callId}/reschedule`, userId, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  markMissed: (userId: string, callId: string) =>
    apiFetch<Call>(`/scheduling/${callId}/missed`, userId, { method: "POST" }),
  deleteCall: (userId: string, callId: string) =>
    apiFetch<{ status: string }>(`/scheduling/${callId}`, userId, {
      method: "DELETE",
    }),
  chatThreads: (userId: string) =>
    apiFetch<ChatThread[]>("/chat/threads", userId),
  createChatThread: (userId: string, propertyId: string) =>
    apiFetch<ChatThread>("/chat/threads", userId, {
      method: "POST",
      body: JSON.stringify({ property_id: propertyId }),
    }),
  chatMessages: (userId: string, threadId: string) =>
    apiFetch<ChatMessage[]>(`/chat/threads/${threadId}/messages`, userId),
  sendChatMessage: (
    userId: string,
    threadId: string,
    payload: Record<string, unknown>,
  ) =>
    apiFetch<ChatMessage>(`/chat/threads/${threadId}/messages`, userId, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  markChatThreadRead: (userId: string, threadId: string) =>
    apiFetch<{ status: string }>(`/chat/threads/${threadId}/read`, userId, {
      method: "POST",
    }),
  cmcAssignments: (userId: string) =>
    apiFetch<Assignment[]>("/cmc/assignments", userId),
  adminDashboard: (userId: string) =>
    apiFetch<AdminDashboard>("/admin/dashboard", userId),
  reassign: (userId: string, propertyId: string, newCmcUserId: string) =>
    apiFetch<{ status: string; future_calls_transferred: number }>(
      "/admin/reassign-cmc",
      userId,
      {
        method: "POST",
        body: JSON.stringify({
          property_id: propertyId,
          new_cmc_user_id: newCmcUserId,
          transfer_future_calls: true,
        }),
      },
    ),
};
