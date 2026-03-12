import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, Navigate, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { api } from "./api";
import type { Channel, Comment, ContinueWatchingItem, User, Video, VideoAnalytics } from "./types";

const GENRES = ["hoi4_letsplay", "strategy", "war", "challenge"];

function useAuth() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("token"));
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    api.me(token)
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("token");
        setToken(null);
      })
      .finally(() => setLoading(false));
  }, [token]);

  const login = async (email: string, password: string) => {
    const data = await api.login({ email, password });
    localStorage.setItem("token", data.access_token);
    setToken(data.access_token);
  };

  const register = (username: string, email: string, password: string) => api.register({ username, email, password });

  const logout = () => {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
  };

  return { token, user, loading, login, register, logout, setUser };
}

function Layout({
  user,
  children,
  onLogout,
  searchQuery,
  onSearchQueryChange,
  suggestions,
  onSuggestionPick
}: {
  user: User | null;
  children: ReactNode;
  onLogout: () => void;
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  suggestions: string[];
  onSuggestionPick: (value: string) => void;
}) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-icon">▶</span>
          MoorLuck hosting
        </div>
        <nav>
          <Link to="/">Главная</Link>
          <Link to="/profile">Мой канал</Link>
          <Link to="/watch-later">Смотреть позже</Link>
          <Link to="/notifications">Уведомления</Link>
          <Link to="/moderation">Модерация</Link>
          <Link to="/upload">Загрузить видео</Link>
        </nav>
      </aside>
      <main className="content">
        <header className="topbar">
          <input
            placeholder="Поиск видео и каналов..."
            value={searchQuery}
            onChange={(e) => onSearchQueryChange(e.target.value)}
          />
          {suggestions.length > 0 ? (
            <div className="search-suggestions">
              {suggestions.map((item) => (
                <button key={item} type="button" className="suggestion-item" onClick={() => onSuggestionPick(item)}>
                  {item}
                </button>
              ))}
            </div>
          ) : null}
          {user ? (
            <button onClick={onLogout} className="ghost-btn">
              Выйти
            </button>
          ) : (
            <div className="auth-links">
              <Link to="/login">Вход</Link>
              <Link to="/register">Регистрация</Link>
            </div>
          )}
        </header>
        {children}
      </main>
    </div>
  );
}

function VideoCard({ video }: { video: Video }) {
  const navigate = useNavigate();
  return (
    <div
      className="video-card"
      role="button"
      tabIndex={0}
      onClick={() => navigate(`/videos/${video.id}`)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          navigate(`/videos/${video.id}`);
        }
      }}
    >
      {video.thumbnail_url ? (
        <img
          src={video.thumbnail_url.startsWith("http") ? video.thumbnail_url : `${api.base}${video.thumbnail_url}`}
          alt={video.title}
          loading="lazy"
          decoding="async"
        />
      ) : (
        <div className="thumb-placeholder">{video.title.slice(0, 1).toUpperCase()}</div>
      )}
      <div className="video-meta">
        <h4>{video.title}</h4>
        <p>
          <Link
            to={`/channels/${video.channel_id}`}
            onClick={(e) => {
              e.stopPropagation();
            }}
          >
            {video.channel_name}
          </Link>
        </p>
        <span>
          {video.views_count} просмотров · {new Date(video.created_at).toLocaleDateString("ru-RU")}
        </span>
      </div>
    </div>
  );
}

function HomePage({
  token,
  searchQuery,
  surface,
  onSurfaceChange
}: {
  token: string | null;
  searchQuery: string;
  surface: string;
  onSurfaceChange: (value: string) => void;
}) {
  const [genre, setGenre] = useState<string>("hoi4_letsplay");
  const [items, setItems] = useState<Video[]>([]);
  const [continueWatchingRows, setContinueWatchingRows] = useState<ContinueWatchingItem[]>([]);
  const [nextCursor, setNextCursor] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const trackedImpressionsRef = useRef<Set<number>>(new Set());

  const load = async (reset = false, forcedCursor?: number | null) => {
    if (loading) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const cursor = reset ? null : forcedCursor ?? nextCursor;
      const res = await api.listVideos(cursor, genre, undefined, searchQuery, surface, token);
      setItems((prev) => (reset ? res.items : [...prev, ...res.items]));
      setNextCursor(res.next_cursor);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    trackedImpressionsRef.current.clear();
    void load(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [genre, searchQuery, surface]);

  useEffect(() => {
    if (!token) {
      setContinueWatchingRows([]);
      return;
    }
    void api.getContinueWatching(token).then(setContinueWatchingRows).catch(() => setContinueWatchingRows([]));
  }, [token]);

  useEffect(() => {
    for (const item of items) {
      if (trackedImpressionsRef.current.has(item.id)) {
        continue;
      }
      trackedImpressionsRef.current.add(item.id);
      void api.trackImpression(item.id, token, "feed");
    }
  }, [items, token]);

  useEffect(() => {
    const node = sentinelRef.current;
    if (!node || !nextCursor || loading) {
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      const entry = entries[0];
      if (entry?.isIntersecting) {
        void load(false, nextCursor);
      }
    });
    observer.observe(node);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nextCursor, loading, genre, searchQuery, surface]);

  return (
    <section>
      <div className="genres">
        <select value={surface} onChange={(e) => onSurfaceChange(e.target.value)} className="surface-select">
          <option value="home">Home</option>
          <option value="watch_next">Watch next</option>
          <option value="trending">Trending</option>
          <option value="subscriptions">Subscriptions</option>
        </select>
        {GENRES.map((value) => (
          <button
            key={value}
            className={genre === value ? "genre active" : "genre"}
            onClick={() => setGenre(value)}
          >
            {value}
          </button>
        ))}
      </div>
      {continueWatchingRows.length > 0 ? (
        <section className="panel continue-panel">
          <h3>Продолжить просмотр</h3>
          <div className="video-grid">
            {continueWatchingRows.slice(0, 4).map((row) => (
              <div key={`continue-${row.video.id}`} className="continue-item">
                <VideoCard video={row.video} />
                <div className="continue-progress">
                  <div className="continue-progress-fill" style={{ width: `${row.progress_pct}%` }} />
                </div>
                <span className="continue-text">{row.progress_pct.toFixed(0)}% просмотрено</span>
              </div>
            ))}
          </div>
        </section>
      ) : null}
      {error && <p className="error">{error}</p>}
      <div className="video-grid">
        {items.map((video) => (
          <VideoCard key={video.id} video={video} />
        ))}
      </div>
      <div className="more-wrap">
        {nextCursor ? (
          <button onClick={() => void load(false)} disabled={loading}>
            {loading ? "Загрузка..." : "Показать еще"}
          </button>
        ) : (
          <span>Больше видео нет</span>
        )}
      </div>
      <div ref={sentinelRef} className="load-sentinel" />
    </section>
  );
}

function LoginPage({ onLogin }: { onLogin: (email: string, password: string) => Promise<void> }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  return (
    <form
      className="panel form"
      onSubmit={async (e) => {
        e.preventDefault();
        setError("");
        try {
          await onLogin(email, password);
          navigate("/");
        } catch (err) {
          setError((err as Error).message);
        }
      }}
    >
      <h2>Вход</h2>
      <input
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email или admin"
        type="text"
        required
      />
      <input
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Пароль"
        type="password"
        required
      />
      {error && <p className="error">{error}</p>}
      <button>Войти</button>
    </form>
  );
}

function RegisterPage({
  onRegister
}: {
  onRegister: (username: string, email: string, password: string) => Promise<unknown>;
}) {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  return (
    <form
      className="panel form"
      onSubmit={async (e) => {
        e.preventDefault();
        setError("");
        try {
          await onRegister(username, email, password);
          navigate("/login");
        } catch (err) {
          setError((err as Error).message);
        }
      }}
    >
      <h2>Регистрация</h2>
      <input
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        placeholder="Никнейм"
        required
        minLength={2}
      />
      <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" type="email" required />
      <input
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Пароль"
        type="password"
        required
        minLength={6}
      />
      {error && <p className="error">{error}</p>}
      <button>Создать аккаунт</button>
    </form>
  );
}

function VideoPage({ token }: { token: string | null }) {
  const params = useParams();
  const videoId = useMemo(() => Number(params.id), [params.id]);
  const playerRef = useRef<HTMLVideoElement | null>(null);
  const sentProgressRef = useRef(0);
  const [video, setVideo] = useState<Video | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [watchLaterSaved, setWatchLaterSaved] = useState(false);
  const [qualities, setQualities] = useState<string[]>(["source"]);
  const [selectedQuality, setSelectedQuality] = useState("source");
  const [hlsUrl, setHlsUrl] = useState<string | null>(null);
  const [isLiked, setIsLiked] = useState(false);
  const [isSubscribed, setIsSubscribed] = useState(false);

  useEffect(() => {
    if (!Number.isFinite(videoId) || videoId <= 0) {
      setError("Некорректный ID видео");
      return;
    }
    sentProgressRef.current = 0;
    setSelectedQuality("source");
    setQualities(["source"]);
    void api.getVideo(videoId, token).then(setVideo).catch((err) => setError((err as Error).message));
    void api.getComments(videoId, token).then(setComments).catch(() => setComments([]));
    void api
      .getVideoQualities(videoId, token)
      .then((res) => {
        setQualities(res.items.length ? res.items : ["source"]);
      })
      .catch(() => setQualities(["source"]));
    void api
      .getHls(videoId, token)
      .then((res) => setHlsUrl(res.hls_url.startsWith("http") ? res.hls_url : `${api.base}${res.hls_url}`))
      .catch(() => setHlsUrl(null));
    void api
      .getLikeStatus(videoId, token)
      .then((res) => {
        setIsLiked(res.is_liked);
        setVideo((prev) => (prev ? { ...prev, likes_count: res.likes_count } : prev));
      })
      .catch(() => setIsLiked(false));
  }, [videoId, token]);

  useEffect(() => {
    if (!video) {
      return;
    }
    void api
      .getSubscriptionStatus(video.channel_id, token)
      .then((res) => setIsSubscribed(res.is_subscribed))
      .catch(() => setIsSubscribed(false));
  }, [video, token]);

  useEffect(() => {
    if (!token || !Number.isFinite(videoId) || videoId <= 0) {
      setWatchLaterSaved(false);
      return;
    }
    void api
      .getWatchLater(token)
      .then((rows) => setWatchLaterSaved(rows.some((item) => item.id === videoId)))
      .catch(() => setWatchLaterSaved(false));
  }, [token, videoId]);

  useEffect(() => {
    const player = playerRef.current;
    if (!player || !video) {
      return;
    }
    const sendProgress = () => {
      const duration = Number.isFinite(player.duration) ? player.duration : 0;
      if (!duration || duration <= 0) {
        return;
      }
      const seconds = Math.max(0, player.currentTime);
      const progressPct = Math.min(100, (seconds / duration) * 100);
      if (progressPct < sentProgressRef.current + 5 && progressPct < 99.9) {
        return;
      }
      sentProgressRef.current = progressPct;
      void api.trackWatchProgress(
        {
          videoId: video.id,
          secondsWatched: seconds,
          durationSeconds: duration,
          progressPct
        },
        token
      );
    };

    player.addEventListener("timeupdate", sendProgress);
    player.addEventListener("ended", sendProgress);
    return () => {
      player.removeEventListener("timeupdate", sendProgress);
      player.removeEventListener("ended", sendProgress);
    };
  }, [video, token]);

  const streamUrl = `${api.base}/videos/${videoId}/stream?quality=${encodeURIComponent(selectedQuality)}`;
  const canUseNativeHls =
    typeof document !== "undefined" && document.createElement("video").canPlayType("application/vnd.apple.mpegurl") !== "";
  const playerSrc = canUseNativeHls && hlsUrl ? hlsUrl : streamUrl;

  if (!video) {
    return <p className={!error ? "loading" : undefined}>{error || "Загрузка..."}</p>;
  }

  return (
    <div className="video-page">
      <video ref={playerRef} controls src={playerSrc} className="player" />
      <div className="quality-row">
        <label htmlFor="quality-select">Качество:</label>
        <select
          id="quality-select"
          className="quality-select"
          value={selectedQuality}
          onChange={(e) => setSelectedQuality(e.target.value)}
        >
          {qualities.map((quality) => (
            <option key={quality} value={quality}>
              {quality === "source" ? "Оригинал" : quality}
            </option>
          ))}
        </select>
      </div>
      <h2>{video.title}</h2>
      <p>{video.description}</p>
      <div className="row-actions">
        <button
          disabled={!token}
          onClick={async () => {
            if (!token) {
              return;
            }
            if (isLiked) {
              await api.unlikeVideo(video.id, token);
            } else {
              await api.likeVideo(video.id, token);
            }
            const status = await api.getLikeStatus(video.id, token);
            setIsLiked(status.is_liked);
            setVideo((prev) => (prev ? { ...prev, likes_count: status.likes_count } : prev));
          }}
        >
          {isLiked ? "Убрать лайк" : "Лайк"} ({video.likes_count})
        </button>
        <button
          disabled={!token}
          onClick={async () => {
            if (!token) {
              return;
            }
            if (isSubscribed) {
              await api.unsubscribe(video.channel_id, token);
            } else {
              await api.subscribe(video.channel_id, token);
            }
            const state = await api.getSubscriptionStatus(video.channel_id, token);
            setIsSubscribed(state.is_subscribed);
          }}
        >
          {isSubscribed ? "Отписаться" : "Подписаться"}
        </button>
        <button
          disabled={!token}
          onClick={async () => {
            if (!token || !video) {
              return;
            }
            if (watchLaterSaved) {
              await api.removeWatchLater(video.id, token);
              setWatchLaterSaved(false);
            } else {
              await api.addWatchLater(video.id, token);
              setWatchLaterSaved(true);
            }
          }}
        >
          {watchLaterSaved ? "Убрать из смотреть позже" : "Смотреть позже"}
        </button>
        <button
          disabled={!token}
          onClick={async () => {
            if (!token || !video) {
              return;
            }
            const reason = window.prompt("Причина жалобы на видео:");
            if (!reason?.trim()) {
              return;
            }
            await api.reportVideo(video.id, token, reason.trim());
          }}
        >
          Пожаловаться
        </button>
      </div>
      <section className="panel">
        <h3>Комментарии ({video.comments_count})</h3>
        {token ? (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (!text.trim()) {
                return;
              }
              if (!token) {
                return;
              }
              const comment = await api.postComment(video.id, token, text);
              setComments((prev) => [...prev, comment]);
              setText("");
            }}
            className="comment-form"
          >
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Напишите комментарий"
              required
            />
            <button>Отправить</button>
          </form>
        ) : (
          <p>Войдите, чтобы писать комментарии.</p>
        )}
        <div className="comments">
          {comments.map((comment) => (
            <div className="comment" key={comment.id}>
              <b>{comment.username}</b>
              <p>{comment.text}</p>
              {token ? (
                <button
                  type="button"
                  className="comment-report-btn"
                  onClick={async () => {
                    if (!token) {
                      return;
                    }
                    const reason = window.prompt("Причина жалобы на комментарий:");
                    if (!reason?.trim()) {
                      return;
                    }
                    await api.reportComment(comment.id, token, reason.trim());
                  }}
                >
                  Пожаловаться
                </button>
              ) : null}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function WatchLaterPage({ token }: { token: string | null }) {
  const [items, setItems] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      setItems([]);
      return;
    }
    setLoading(true);
    api.getWatchLater(token)
      .then(setItems)
      .finally(() => setLoading(false));
  }, [token]);

  if (!token) {
    return <Navigate to="/login" replace />;
  }
  if (loading) {
    return <p className="loading">Загрузка...</p>;
  }
  return (
    <section className="panel">
      <h2>Смотреть позже</h2>
      <div className="video-grid">
        {items.map((video) => (
          <VideoCard key={`later-${video.id}`} video={video} />
        ))}
      </div>
    </section>
  );
}

function NotificationsPage({ token }: { token: string | null }) {
  const [items, setItems] = useState<
    Array<{ id: number; type: string; message: string; is_read: boolean; created_at: string; payload: Record<string, unknown> }>
  >([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setItems([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    api.myNotifications(token)
      .then(setItems)
      .finally(() => setLoading(false));
  }, [token]);

  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return (
    <section className="panel">
      <h2>Уведомления</h2>
      {loading ? <p className="loading">Загрузка...</p> : null}
      <div className="notifications-list">
        {items.map((item) => (
          <div key={item.id} className={item.is_read ? "notification-item read" : "notification-item"}>
            <div>
              <b>{item.type}</b>
              <p>{item.message}</p>
            </div>
            {!item.is_read ? (
              <button
                onClick={async () => {
                  if (!token) {
                    return;
                  }
                  await api.markNotificationRead(token, item.id);
                  setItems((prev) => prev.map((row) => (row.id === item.id ? { ...row, is_read: true } : row)));
                }}
              >
                Прочитано
              </button>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function ModerationPage({ token, user }: { token: string | null; user: User | null }) {
  const [items, setItems] = useState<
    Array<{ kind: "video" | "comment"; report_id: number; target_id: number; reason: string; status: string; created_at: string }>
  >([]);
  const [loading, setLoading] = useState(true);
  const [pendingVideos, setPendingVideos] = useState<Video[]>([]);

  useEffect(() => {
    if (!token || !user?.is_admin) {
      setLoading(false);
      return;
    }
    setLoading(true);
    Promise.all([api.moderationReports(token), api.moderationPendingVideos(token)])
      .then(([reports, pending]) => {
        setItems(reports);
        setPendingVideos(pending);
      })
      .finally(() => setLoading(false));
  }, [token, user]);

  if (!token) {
    return <Navigate to="/login" replace />;
  }
  if (!user?.is_admin) {
    return <p className="error">Раздел доступен только администратору.</p>;
  }
  return (
    <section className="panel">
      <h2>Очередь модерации</h2>
      {loading ? <p className="loading">Загрузка...</p> : null}
      <h3>Видео на апрув</h3>
      <div className="moderation-list">
        {pendingVideos.map((video) => (
          <div key={`pending-video-${video.id}`} className="moderation-item">
            <div>
              <b>
                video #{video.id}
              </b>
              <p>{video.title}</p>
            </div>
            <div className="moderation-actions">
              <Link to={`/videos/${video.id}`}>Preview</Link>
              <button
                onClick={async () => {
                  if (!token) {
                    return;
                  }
                  await api.moderationVideoAction(token, video.id, "approve");
                  setPendingVideos((prev) => prev.filter((row) => row.id !== video.id));
                }}
              >
                Approve
              </button>
              <button
                onClick={async () => {
                  if (!token) {
                    return;
                  }
                  await api.moderationVideoAction(token, video.id, "reject");
                  setPendingVideos((prev) => prev.filter((row) => row.id !== video.id));
                }}
              >
                Reject
              </button>
            </div>
          </div>
        ))}
      </div>
      <div className="moderation-list">
        {items.map((item) => (
          <div key={`${item.kind}-${item.report_id}`} className="moderation-item">
            <div>
              <b>
                {item.kind} #{item.target_id}
              </b>
              <p>{item.reason}</p>
            </div>
            <div className="moderation-actions">
              <button onClick={async () => token && api.moderationAction(token, item.kind, item.report_id, "hide")}>Hide</button>
              <button onClick={async () => token && api.moderationAction(token, item.kind, item.report_id, "ban")}>Ban</button>
              <button onClick={async () => token && api.moderationAction(token, item.kind, item.report_id, "dismiss")}>
                Dismiss
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function ProfilePage({ user, token, onUserRefresh }: { user: User | null; token: string | null; onUserRefresh: () => Promise<void> }) {
  const [managedUserId, setManagedUserId] = useState("");
  const [message, setMessage] = useState("");
  const [myVideos, setMyVideos] = useState<Video[]>([]);
  const [videosLoading, setVideosLoading] = useState(false);
  const [analyticsByVideo, setAnalyticsByVideo] = useState<Record<number, VideoAnalytics>>({});
  const [studioDashboard, setStudioDashboard] = useState<{
    daily_views: Array<{ day: string; value: number }>;
    daily_watch_time_minutes: Array<{ day: string; value: number }>;
    traffic_sources: Array<{ source: string; impressions: number }>;
    watch_time_curve: Array<{ day: string; value: number }>;
    top_videos: Array<{ video_id: number; title: string; views: number; avg_watch_percent: number }>;
  } | null>(null);

  useEffect(() => {
    if (!user) {
      return;
    }
    setVideosLoading(true);
    api.listVideos(null, undefined, user.id, undefined, "home", token)
      .then((res) => setMyVideos(res.items))
      .finally(() => setVideosLoading(false));
  }, [user, token]);

  useEffect(() => {
    if (!token || myVideos.length === 0) {
      return;
    }
    let cancelled = false;
    Promise.all(
      myVideos.slice(0, 12).map(async (videoItem) => [videoItem.id, await api.getVideoAnalytics(videoItem.id, token)] as const)
    ).then((rows) => {
      if (cancelled) {
        return;
      }
      const next: Record<number, VideoAnalytics> = {};
      for (const [id, analytics] of rows) {
        next[id] = analytics;
      }
      setAnalyticsByVideo(next);
    });
    return () => {
      cancelled = true;
    };
  }, [myVideos, token]);

  useEffect(() => {
    if (!token) {
      setStudioDashboard(null);
      return;
    }
    api.studioDashboard(token, 14).then(setStudioDashboard).catch(() => setStudioDashboard(null));
  }, [token, myVideos.length]);

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <section className="panel profile">
      <h2>{user.username}</h2>
      <p>
        Роль: {user.is_admin ? "admin" : "user"} | can_upload: {String(user.can_upload)}
      </p>
      {user.is_admin && token && (
        <form
          className="form-inline"
          onSubmit={async (e) => {
            e.preventDefault();
            setMessage("");
            const id = Number(managedUserId);
            if (!id) {
              return;
            }
            await api.setUploadAccess(token, id, true);
            setMessage("Пользователь получил upload-доступ");
          }}
        >
          <input
            value={managedUserId}
            onChange={(e) => setManagedUserId(e.target.value)}
            placeholder="ID пользователя"
          />
          <button>Выдать can_upload</button>
        </form>
      )}
      <button
        onClick={async () => {
          await onUserRefresh();
          setMessage("Профиль обновлен");
        }}
      >
        Обновить профиль
      </button>
      {message && <p>{message}</p>}
      <h3>Мои видео</h3>
      {videosLoading ? <p className="loading">Загрузка...</p> : null}
      <div className="video-grid">
        {myVideos.map((video) => (
          <div className="profile-video-card" key={video.id}>
            <p>
              Статус:{" "}
              {video.moderation_status === "approved"
                ? "одобрено"
                : video.moderation_status === "pending"
                  ? "на проверке"
                  : "отклонено"}
            </p>
            <VideoCard video={video} />
            {token ? (
              <button
                className="danger-btn"
                onClick={async () => {
                  if (!token) {
                    return;
                  }
                  const confirmed = window.confirm(`Удалить видео "${video.title}"?`);
                  if (!confirmed) {
                    return;
                  }
                  await api.deleteVideo(video.id, token);
                  setMyVideos((prev) => prev.filter((item) => item.id !== video.id));
                  setAnalyticsByVideo((prev) => {
                    const next = { ...prev };
                    delete next[video.id];
                    return next;
                  });
                }}
              >
                Удалить видео
              </button>
            ) : null}
          </div>
        ))}
      </div>
      {token && myVideos.length > 0 ? (
        <>
          <h3>Studio аналитика</h3>
          <div className="analytics-grid">
            {myVideos.map((video) => {
              const analytics = analyticsByVideo[video.id];
              return (
                <div className="analytics-card" key={`analytics-${video.id}`}>
                  <h4>{video.title}</h4>
                  {analytics ? (
                    <>
                      <p>Уникальные просмотры: {analytics.unique_views}</p>
                      <p>Показы: {analytics.impressions}</p>
                      <p>CTR: {analytics.ctr_percent}%</p>
                      <p>Среднее удержание: {analytics.avg_watch_percent}%</p>
                      <div className="retention-row">
                        {analytics.retention.map((point) => (
                          <span key={point.bucket}>
                            {point.bucket}: {point.viewers}
                          </span>
                        ))}
                      </div>
                    </>
                  ) : (
                    <p className="loading">Считаем метрики...</p>
                  )}
                </div>
              );
            })}
          </div>
          {studioDashboard ? (
            <div className="studio-v2-grid">
              <div className="studio-card">
                <h4>Просмотры по дням</h4>
                {studioDashboard.daily_views.map((row) => (
                  <div key={`dv-${row.day}`} className="studio-line-row">
                    <span>{row.day}</span>
                    <b>{row.value}</b>
                  </div>
                ))}
              </div>
              <div className="studio-card">
                <h4>Watch time (мин) по дням</h4>
                {studioDashboard.daily_watch_time_minutes.map((row) => (
                  <div key={`wt-${row.day}`} className="studio-line-row">
                    <span>{row.day}</span>
                    <b>{row.value}</b>
                  </div>
                ))}
              </div>
              <div className="studio-card">
                <h4>Источники трафика</h4>
                {studioDashboard.traffic_sources.map((row) => (
                  <div key={`src-${row.source}`} className="studio-line-row">
                    <span>{row.source}</span>
                    <b>{row.impressions}</b>
                  </div>
                ))}
              </div>
              <div className="studio-card">
                <h4>Топ видео</h4>
                {studioDashboard.top_videos.map((row) => (
                  <div key={`top-${row.video_id}`} className="studio-line-row">
                    <span>{row.title}</span>
                    <b>
                      {row.views} / {row.avg_watch_percent}%
                    </b>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function ChannelPage({ token }: { token: string | null }) {
  const params = useParams();
  const channelId = useMemo(() => Number(params.id), [params.id]);
  const [channel, setChannel] = useState<Channel | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [subscribed, setSubscribed] = useState(false);

  useEffect(() => {
    if (!Number.isFinite(channelId) || channelId <= 0) {
      setError("Некорректный ID канала");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    api.getChannel(channelId)
      .then(async (channelInfo) => {
        setChannel(channelInfo);
        const channelVideos = await api.listVideos(null, undefined, channelInfo.owner_id, undefined, "home", token);
        setVideos(channelVideos.items);
        const status = await api.getSubscriptionStatus(channelInfo.id, token);
        setSubscribed(status.is_subscribed);
      })
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [channelId, token]);

  if (loading) {
    return <p className="loading">Загрузка канала...</p>;
  }
  if (error || !channel) {
    return <p className="error">{error || "Канал не найден"}</p>;
  }

  return (
    <section className="panel">
      <h2>{channel.name}</h2>
      <p>{channel.description || "Описание не указано"}</p>
      <p>Подписчиков: {channel.subscribers_count}</p>
      {token ? (
        <button
          type="button"
          onClick={async () => {
            if (!token) {
              return;
            }
            if (subscribed) {
              await api.unsubscribe(channel.id, token);
              setSubscribed(false);
            } else {
              await api.subscribe(channel.id, token);
              setSubscribed(true);
            }
          }}
        >
          {subscribed ? "Отписаться" : "Подписаться"}
        </button>
      ) : null}
      <h3>Видео канала</h3>
      <div className="video-grid">
        {videos.map((video) => (
          <VideoCard key={`channel-video-${video.id}`} video={video} />
        ))}
      </div>
    </section>
  );
}

function UploadPage({ token, user }: { token: string | null; user: User | null }) {
  const MAX_VIDEO_BYTES = 1024 * 1024 * 1024;
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [genre, setGenre] = useState("hoi4_letsplay");
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [thumbnail, setThumbnail] = useState<File | null>(null);
  const [thumbnailPreview, setThumbnailPreview] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [processingStatus, setProcessingStatus] = useState<string>("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (thumbnail) {
      const url = URL.createObjectURL(thumbnail);
      setThumbnailPreview(url);
      return () => URL.revokeObjectURL(url);
    }
    setThumbnailPreview(null);
  }, [thumbnail]);

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <form
      className="panel form"
      onSubmit={async (e) => {
        e.preventDefault();
        if (uploading) {
          return;
        }
        setError("");
        setMessage("");
        if (!videoFile || !token) {
          return;
        }
        if (videoFile.size > MAX_VIDEO_BYTES) {
          setError("Видео слишком большое. Максимум 1 ГБ.");
          return;
        }
        setUploading(true);
        setUploadProgress(0);
        const form = new FormData();
        form.append("title", title);
        form.append("description", description);
        form.append("genre", genre);
        form.append("video_file", videoFile);
        if (thumbnail) {
          form.append("thumbnail", thumbnail);
        }
        try {
          const uploaded = await api.uploadVideo(token, form, setUploadProgress);
          if (uploaded.moderation_status === "pending") {
            setMessage(`Видео загружено: ${uploaded.title}. Оно станет публичным после апрува админа.`);
          } else {
            setMessage(`Видео загружено: ${uploaded.title}`);
          }
          setProcessingStatus("processing");
          const pollStatus = async (attempt = 0) => {
            try {
              const statusRes = await api.getProcessingStatus(uploaded.id, token);
              setProcessingStatus(statusRes.status);
              if (statusRes.status === "processing") {
                const delayMs = Math.min(15000, 1500 * Math.pow(1.6, attempt));
                setTimeout(() => {
                  void pollStatus(attempt + 1);
                }, delayMs);
              }
            } catch (_err) {
              setProcessingStatus("");
            }
          };
          void pollStatus();
          setTitle("");
          setDescription("");
          setVideoFile(null);
          setThumbnail(null);
        } catch (err) {
          setError((err as Error).message);
        } finally {
          setUploading(false);
        }
      }}
    >
      <h2>Загрузка видео</h2>
      <p>Максимальный размер видео: 1 ГБ. Публикация после апрува админа.</p>
      <input placeholder="Название" value={title} onChange={(e) => setTitle(e.target.value)} required />
      <textarea
        placeholder="Описание"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        rows={4}
      />
      <select value={genre} onChange={(e) => setGenre(e.target.value)}>
        {GENRES.map((value) => (
          <option key={value}>{value}</option>
        ))}
      </select>
      <label>
        Видео
        <input type="file" accept="video/*" onChange={(e) => setVideoFile(e.target.files?.[0] || null)} required />
      </label>
      <div className="thumbnail-upload">
        <span className="thumbnail-label">Превью (по желанию)</span>
        <label
          className="thumbnail-dropzone"
          onDragOver={(e) => {
            e.preventDefault();
            e.currentTarget.classList.add("thumbnail-dragover");
          }}
          onDragLeave={(e) => {
            e.preventDefault();
            e.currentTarget.classList.remove("thumbnail-dragover");
          }}
          onDrop={(e) => {
            e.preventDefault();
            e.currentTarget.classList.remove("thumbnail-dragover");
            const file = e.dataTransfer.files?.[0];
            if (file?.type.startsWith("image/")) setThumbnail(file);
          }}
        >
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setThumbnail(e.target.files?.[0] || null)}
            className="thumbnail-input"
          />
          {thumbnailPreview ? (
            <div className="thumbnail-preview-wrap">
              <img src={thumbnailPreview} alt="Превью" className="thumbnail-preview" />
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  setThumbnail(null);
                }}
                className="thumbnail-remove"
                title="Удалить превью"
              >
                ×
              </button>
            </div>
          ) : (
            <div className="thumbnail-placeholder-upload">
              <span>Нажмите или перетащите изображение</span>
            </div>
          )}
        </label>
      </div>
      {error && <p className="error">{error}</p>}
      {message && <p>{message}</p>}
      {processingStatus ? <p>Обработка видео: {processingStatus}</p> : null}
      {uploading ? (
        <div className="upload-progress-wrap">
          <div className="upload-progress-header">
            <span>Загрузка видео...</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="upload-progress-track">
            <div className="upload-progress-fill" style={{ width: `${uploadProgress}%` }} />
          </div>
        </div>
      ) : null}
      <button disabled={uploading}>{uploading ? "Загружается..." : "Загрузить"}</button>
    </form>
  );
}

export function App() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");
  const [surface, setSurface] = useState("home");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const lastSuggestRequestAtRef = useRef(0);

  useEffect(() => {
    const q = searchQuery.trim();
    if (!q) {
      setSuggestions([]);
      return;
    }
    const timer = setTimeout(() => {
      const now = Date.now();
      if (now - lastSuggestRequestAtRef.current < 450) {
        return;
      }
      lastSuggestRequestAtRef.current = now;
      api.getSuggestions(q)
        .then((res) => setSuggestions(res.items))
        .catch(() => setSuggestions([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  if (auth.loading) {
    return <p className="loading">Проверка сессии...</p>;
  }

  return (
    <Layout
      user={auth.user}
      searchQuery={searchQuery}
      onSearchQueryChange={setSearchQuery}
      suggestions={suggestions}
      onSuggestionPick={(value) => {
        setSearchQuery(value);
        setSuggestions([]);
        navigate("/");
      }}
      onLogout={() => {
        auth.logout();
        navigate("/");
      }}
    >
      <Routes>
        <Route
          path="/"
          element={<HomePage token={auth.token} searchQuery={searchQuery} surface={surface} onSurfaceChange={setSurface} />}
        />
        <Route path="/videos/:id" element={<VideoPage token={auth.token} />} />
        <Route path="/channels/:id" element={<ChannelPage token={auth.token} />} />
        <Route path="/login" element={<LoginPage onLogin={auth.login} />} />
        <Route path="/register" element={<RegisterPage onRegister={auth.register} />} />
        <Route
          path="/profile"
          element={
            <ProfilePage
              user={auth.user}
              token={auth.token}
              onUserRefresh={async () => {
                if (!auth.token) {
                  return;
                }
                const me = await api.me(auth.token);
                auth.setUser(me);
              }}
            />
          }
        />
        <Route path="/notifications" element={<NotificationsPage token={auth.token} />} />
        <Route path="/moderation" element={<ModerationPage token={auth.token} user={auth.user} />} />
        <Route path="/watch-later" element={<WatchLaterPage token={auth.token} />} />
        <Route path="/upload" element={<UploadPage token={auth.token} user={auth.user} />} />
      </Routes>
    </Layout>
  );
}
