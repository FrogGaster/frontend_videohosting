import type { Channel, Comment, ContinueWatchingItem, User, Video, VideoAnalytics, VideoListResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
const ANALYTICS_BATCH_FLUSH_MS = 1200;
const ANALYTICS_BATCH_MAX = 30;

type BatchedImpression = { video_id: number; source: string };
type BatchedWatchProgress = {
  video_id: number;
  seconds_watched: number;
  duration_seconds: number;
  progress_pct: number;
};

let queuedImpressions: BatchedImpression[] = [];
let queuedWatchProgress: BatchedWatchProgress[] = [];
let analyticsToken: string | null = null;
let analyticsFlushTimer: number | null = null;

function authHeaders(token?: string | null): HeadersInit {
  if (!token) {
    return {};
  }
  return { Authorization: `Bearer ${token}` };
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    let message = "Request failed";
    try {
      const body = await response.json();
      message = body.detail ?? message;
    } catch (_err) {
      message = response.statusText || message;
    }
    throw new Error(message);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function flushAnalyticsBatch(forceToken?: string | null): Promise<void> {
  if (queuedImpressions.length === 0 && queuedWatchProgress.length === 0) {
    return;
  }
  const token = forceToken !== undefined ? forceToken : analyticsToken;
  const payload = {
    impressions: queuedImpressions,
    watch_progress: queuedWatchProgress
  };
  queuedImpressions = [];
  queuedWatchProgress = [];
  await request<void>("/analytics/batch", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify(payload)
  }).catch(() => undefined);
}

function scheduleAnalyticsFlush(token?: string | null) {
  const nextToken = token ?? null;
  if (analyticsToken !== null && analyticsToken !== nextToken) {
    void flushAnalyticsBatch(analyticsToken);
  }
  analyticsToken = nextToken;
  if (queuedImpressions.length + queuedWatchProgress.length >= ANALYTICS_BATCH_MAX) {
    void flushAnalyticsBatch(nextToken);
    return;
  }
  if (analyticsFlushTimer !== null) {
    return;
  }
  analyticsFlushTimer = window.setTimeout(() => {
    analyticsFlushTimer = null;
    void flushAnalyticsBatch(nextToken);
  }, ANALYTICS_BATCH_FLUSH_MS);
}

export const api = {
  base: API_BASE,
  register: (payload: { username: string; email: string; password: string }) =>
    request<User>("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }),
  login: (payload: { email: string; password: string }) =>
    request<{ access_token: string; token_type: string }>("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }),
  me: (token: string) => request<User>("/auth/me", { headers: authHeaders(token) }),
  getChannel: (channelId: number) => request<Channel>(`/channels/${channelId}`),
  listVideos: (cursor?: number | null, genre?: string, ownerId?: number, query?: string, surface = "home", token?: string | null) => {
    const params = new URLSearchParams();
    if (cursor) {
      params.set("cursor", String(cursor));
    }
    if (genre) {
      params.set("genre", genre);
    }
    if (ownerId) {
      params.set("owner_id", String(ownerId));
    }
    if (query && query.trim()) {
      params.set("q", query.trim());
    }
    params.set("surface", surface);
    return request<VideoListResponse>(`/videos?${params.toString()}`, { headers: authHeaders(token) });
  },
  getVideo: (id: string | number, token?: string | null) => request<Video>(`/videos/${id}`, { headers: authHeaders(token) }),
  getVideoQualities: (videoId: number, token?: string | null) =>
    request<{ items: string[] }>(`/videos/${videoId}/qualities`, { headers: authHeaders(token) }),
  getSuggestions: (query: string) => request<{ items: string[] }>(`/search/suggestions?q=${encodeURIComponent(query)}`),
  getContinueWatching: (token: string) => request<ContinueWatchingItem[]>("/me/continue-watching", { headers: authHeaders(token) }),
  getWatchLater: (token: string) => request<Video[]>("/me/watch-later", { headers: authHeaders(token) }),
  addWatchLater: (videoId: number, token: string) =>
    request<void>(`/videos/${videoId}/watch-later`, { method: "POST", headers: authHeaders(token) }),
  removeWatchLater: (videoId: number, token: string) =>
    request<void>(`/videos/${videoId}/watch-later`, { method: "DELETE", headers: authHeaders(token) }),
  deleteVideo: (videoId: number, token: string) =>
    request<void>(`/videos/${videoId}`, { method: "DELETE", headers: authHeaders(token) }),
  getComments: (videoId: number, token?: string | null) => request<Comment[]>(`/videos/${videoId}/comments`, { headers: authHeaders(token) }),
  postComment: (videoId: number, token: string, text: string) =>
    request<Comment>(`/videos/${videoId}/comments`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify({ text })
    }),
  likeVideo: (videoId: number, token: string) =>
    request<void>(`/videos/${videoId}/like`, { method: "POST", headers: authHeaders(token) }),
  unlikeVideo: (videoId: number, token: string) =>
    request<void>(`/videos/${videoId}/like`, { method: "DELETE", headers: authHeaders(token) }),
  getLikeStatus: (videoId: number, token?: string | null) =>
    request<{ is_liked: boolean; likes_count: number }>(`/videos/${videoId}/like-status`, { headers: authHeaders(token) }),
  subscribe: (channelId: number, token: string) =>
    request<void>(`/channels/${channelId}/subscribe`, { method: "POST", headers: authHeaders(token) }),
  unsubscribe: (channelId: number, token: string) =>
    request<void>(`/channels/${channelId}/subscribe`, { method: "DELETE", headers: authHeaders(token) }),
  getSubscriptionStatus: (channelId: number, token?: string | null) =>
    request<{ is_subscribed: boolean }>(`/channels/${channelId}/subscription-status`, { headers: authHeaders(token) }),
  uploadVideo: (token: string, formData: FormData, onProgress?: (percent: number) => void) =>
    new Promise<Video>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_BASE}/videos/upload`);
      if (token) {
        xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      }
      xhr.upload.onprogress = (event) => {
        if (!event.lengthComputable || !onProgress) {
          return;
        }
        const percent = Math.round((event.loaded / event.total) * 100);
        onProgress(percent);
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText) as Video);
          } catch (_error) {
            reject(new Error("Invalid upload response"));
          }
          return;
        }
        try {
          const parsed = JSON.parse(xhr.responseText) as { detail?: string };
          reject(new Error(parsed.detail ?? "Upload failed"));
        } catch (_error) {
          reject(new Error("Upload failed"));
        }
      };
      xhr.onerror = () => reject(new Error("Network upload error"));
      xhr.send(formData);
    }),
  setUploadAccess: (token: string, userId: number, canUpload: boolean) =>
    request<User>(`/admin/users/${userId}/upload-access`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify({ can_upload: canUpload })
    }),
  trackImpression: (videoId: number, token?: string | null, source = "feed") => {
    queuedImpressions.push({ video_id: videoId, source });
    scheduleAnalyticsFlush(token);
    return Promise.resolve();
  },
  trackWatchProgress: (
    payload: { videoId: number; secondsWatched: number; durationSeconds: number; progressPct: number },
    token?: string | null
  ) => {
    queuedWatchProgress.push({
      video_id: payload.videoId,
      seconds_watched: payload.secondsWatched,
      duration_seconds: payload.durationSeconds,
      progress_pct: payload.progressPct
    });
    scheduleAnalyticsFlush(token);
    return Promise.resolve();
  },
  getVideoAnalytics: (videoId: number, token: string) =>
    request<VideoAnalytics>(`/studio/videos/${videoId}/analytics`, { headers: authHeaders(token) }),
  getProcessingStatus: (videoId: number, token?: string | null) =>
    request<{ video_id: number; status: string; error_message: string; output: Record<string, unknown> }>(
      `/videos/${videoId}/processing-status`,
      { headers: authHeaders(token) }
    ),
  getHls: (videoId: number, token?: string | null) => request<{ hls_url: string }>(`/videos/${videoId}/hls`, { headers: authHeaders(token) }),
  reportVideo: (videoId: number, token: string, reason: string) =>
    request<{ status: string }>(`/reports/video/${videoId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify({ reason })
    }),
  reportComment: (commentId: number, token: string, reason: string) =>
    request<{ status: string }>(`/reports/comment/${commentId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify({ reason })
    }),
  moderationReports: (token: string, statusFilter = "open") =>
    request<
      Array<{
        kind: "video" | "comment";
        report_id: number;
        target_id: number;
        reason: string;
        status: string;
        created_at: string;
      }>
    >(`/moderation/reports?status_filter=${encodeURIComponent(statusFilter)}`, { headers: authHeaders(token) }),
  moderationPendingVideos: (token: string) =>
    request<Video[]>("/moderation/videos/pending", { headers: authHeaders(token) }),
  moderationVideoAction: (token: string, videoId: number, action: "approve" | "reject") =>
    request<Video>(`/moderation/videos/${videoId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify({ action })
    }),
  moderationAction: (token: string, kind: "video" | "comment", reportId: number, action: string) =>
    request<{ status: string }>(`/moderation/reports/${kind}/${reportId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify({ action })
    }),
  myNotifications: (token: string, unreadOnly = false) =>
    request<Array<{ id: number; type: string; message: string; is_read: boolean; created_at: string; payload: Record<string, unknown> }>>(
      `/me/notifications?unread_only=${String(unreadOnly)}`,
      { headers: authHeaders(token) }
    ),
  markNotificationRead: (token: string, id: number) =>
    request<void>(`/me/notifications/${id}/read`, { method: "POST", headers: authHeaders(token) }),
  studioDashboard: (token: string, days = 14) =>
    request<{
      daily_views: Array<{ day: string; value: number }>;
      daily_watch_time_minutes: Array<{ day: string; value: number }>;
      traffic_sources: Array<{ source: string; impressions: number }>;
      watch_time_curve: Array<{ day: string; value: number }>;
      top_videos: Array<{ video_id: number; title: string; views: number; avg_watch_percent: number }>;
    }>(`/studio/dashboard?days=${days}`, { headers: authHeaders(token) })
};
