import useSWR from "swr";
import clsx from "clsx";

const FEEDS = [
  { name: "CoinTelegraph", url: "https://cointelegraph.com/rss", tag: "CT" },
  { name: "Decrypt",       url: "https://decrypt.co/feed",       tag: "DC" },
  { name: "CoinDesk",      url: "https://www.coindesk.com/arc/outboundfeeds/rss/", tag: "CD" },
];

async function fetchNews() {
  const RSS2JSON = "https://api.rss2json.com/v1/api.json?rss_url=";
  const results = await Promise.allSettled(
    FEEDS.map(f =>
      fetch(RSS2JSON + encodeURIComponent(f.url))
        .then(r => r.json())
        .then(d => (d.items ?? []).map(item => ({
          id: item.guid || item.link,
          title: item.title,
          url: item.link,
          body: item.description?.replace(/<[^>]*>/g, "").slice(0, 200),
          imageurl: item.thumbnail || item.enclosure?.link || "",
          published_on: Math.floor(new Date(item.pubDate).getTime() / 1000),
          source: f.name,
          tag: f.tag,
          categories: f.name,
        })))
    )
  );
  const all = results.flatMap(r => r.status === "fulfilled" ? r.value : []);
  return all.sort((a, b) => b.published_on - a.published_on);
}

const CATEGORIES = ["All","Bitcoin","Ethereum","Altcoin","DeFi","NFT","Regulation","Trading"];

function timeAgo(ts) {
  const diff = Math.floor(Date.now() / 1000) - ts;
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
}

function NewsCard({ article, featured }) {
  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className={clsx(
        "block bg-bg-card border border-border rounded-xl overflow-hidden hover:border-border-light transition-all group",
        featured ? "col-span-2" : ""
      )}
    >
      {article.imageurl && (
        <div className={clsx("overflow-hidden bg-gradient-to-br from-brand-blue/20 to-purple-600/20", featured ? "h-48" : "h-28")}>
          <img
            src={article.imageurl}
            alt=""
            loading="lazy"
            className="w-full h-full object-cover opacity-80 group-hover:opacity-100 group-hover:scale-105 transition-all duration-300"
            style={{ maxWidth: "100%", height: "100%" }}
            onError={e => { e.target.style.display = "none"; }}
          />
        </div>
      )}
      <div className="p-3">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-[10px] font-semibold text-tx-muted uppercase tracking-wider">{article.source}</span>
          <span className="text-[10px] text-tx-dim">·</span>
          <span className="text-[10px] text-tx-dim">{timeAgo(article.published_on)}</span>
          {article.categories && (
            <span className="ml-auto text-[10px] font-medium px-1.5 py-0.5 rounded bg-brand-blue/10 text-brand-blue border border-brand-blue/20">
              {article.categories.split("|")[0]}
            </span>
          )}
        </div>
        <h3 className={clsx(
          "font-semibold text-tx leading-snug group-hover:text-brand-blue transition-colors line-clamp-2",
          featured ? "text-sm" : "text-xs"
        )}>
          {article.title}
        </h3>
        {featured && (
          <p className="text-xs text-tx-muted mt-1.5 line-clamp-2 leading-relaxed">{article.body?.slice(0,160)}…</p>
        )}
      </div>
    </a>
  );
}

export default function NewsView() {
  const { data: news, isLoading, error } = useSWR("crypto-news", fetchNews, {
    refreshInterval: 300000, // refresh every 5 min
    revalidateOnFocus: false,
  });

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="shrink-0 border-b border-border px-5 py-3 flex items-center gap-4">
        <h1 className="text-sm font-bold text-tx">Crypto News</h1>
        <div className="flex items-center gap-1.5 text-[10px] text-tx-muted ml-auto">
          <div className="w-1.5 h-1.5 rounded-full bg-brand-green animate-pulse" />
          Live · via CryptoCompare
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto no-scrollbar p-4">
        {isLoading && (
          <div className="flex items-center justify-center h-48 gap-2 text-tx-muted">
            <div className="w-5 h-5 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">Loading news…</span>
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center justify-center h-48 text-tx-muted gap-2">
            <span className="text-sm">Failed to load news</span>
            <span className="text-xs">Check your internet connection</span>
          </div>
        )}

        {news && news.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {/* Featured top story */}
            <div className="md:col-span-2 lg:col-span-2">
              <NewsCard article={news[0]} featured />
            </div>
            <div className="flex flex-col gap-3">
              {news.slice(1, 4).map(a => (
                <NewsCard key={a.id} article={a} />
              ))}
            </div>
            {/* Rest of the news */}
            {news.slice(4).map(a => (
              <NewsCard key={a.id} article={a} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
