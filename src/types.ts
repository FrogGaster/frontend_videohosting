export type User = {
  id: number;
  username: string;
  email: string;
  is_admin: boolean;
  can_upload: boolean;
};

export type Channel = {
  id: number;
  owner_id: number;
  name: string;
  description: string;
  avatar_url: string;
  subscribers_count: number;
};

export type Video = {
  id: number;
  owner_id: number;
  channel_id: number;
  channel_name: string;
  title: string;
  description: string;
  genre: string;
  views_count: number;
  likes_count: number;
  comments_count: number;
  thumbnail_url: string;
  moderation_status: "pending" | "approved" | "rejected";
  created_at: string;
};

export type VideoListResponse = {
  items: Video[];
  next_cursor: number | null;
};

export type Comment = {
  id: number;
  user_id: number;
  username: string;
  video_id: number;
  text: string;
  created_at: string;
};

export type RetentionPoint = {
  bucket: string;
  viewers: number;
};

export type VideoAnalytics = {
  video_id: number;
  impressions: number;
  unique_views: number;
  ctr_percent: number;
  avg_watch_percent: number;
  retention: RetentionPoint[];
};

export type ContinueWatchingItem = {
  video: Video;
  progress_pct: number;
  seconds_watched: number;
};
