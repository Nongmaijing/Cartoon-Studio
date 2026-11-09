import type { Asset } from "../types";

export function Gallery({ assets }: { assets: Asset[] }) {
  if (!assets.length) {
    return <div className="empty">Generated frames and clips will appear here.</div>;
  }
  return (
    <div className="gallery">
      {assets.map((asset) => (
        <a key={asset.id} className="thumb" href={asset.url} target="_blank" rel="noreferrer">
          {asset.kind === "video" ? (
            <video src={asset.url} muted loop playsInline preload="metadata" />
          ) : asset.kind === "audio" ? (
            <div className="thumb-audio" aria-label={asset.filename}>
              <span>♪</span>
            </div>
          ) : (
            <img src={asset.url} alt={asset.filename} loading="lazy" />
          )}
          <div className="thumb-cap">
            <span className="wrap">{asset.filename}</span>
            <span>{asset.kind}</span>
          </div>
        </a>
      ))}
    </div>
  );
}
