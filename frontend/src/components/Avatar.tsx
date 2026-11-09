"use client";

import { useEffect, useState } from "react";
import { getPhotos } from "@/lib/api";

// A round picture of a creator: their public YouTube channel photo when we have one, otherwise a coloured circle with their initials (also used when the picture
// fails to load). The photo link comes from GET /passport/photos; the app only links to it, it does not store the picture.

const TINTS = ["#33cccc", "#f5b83d", "#6aa9ff", "#ff7ab6", "#46d68a", "#b38cff"];

function initialsOf(name: string): string {
  const words = name.replace(/\(.*?\)/g, "").split(/\s+/).filter(Boolean);
  return ((words[0]?.[0] ?? "?") + (words.length > 1 ? words[words.length - 1][0] : "")).toUpperCase();
}

function tintOf(name: string): string {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return TINTS[h % TINTS.length];
}

export default function Avatar({ creatorId, name, size = 32 }: { creatorId: string; name: string; size?: number }) {
  const [photos, setPhotos] = useState<Record<string, string>>({});
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    getPhotos().then((p) => live && setPhotos(p));
    return () => {
      live = false;
    };
  }, []);
  const url = photos[creatorId];
  const box = { width: size, height: size, minWidth: size };
  if (url && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- a small remote avatar; next/image would need every YouTube host whitelisted
      <img src={url} alt="" width={size} height={size} referrerPolicy="no-referrer" onError={() => setFailed(true)} style={box} className="rounded-full border border-line object-cover" />
    );
  }
  return (
    <span aria-hidden style={{ ...box, background: tintOf(name), fontSize: Math.max(10, size * 0.38) }} className="inline-grid place-items-center rounded-full font-semibold text-[#0a1016]">
      {initialsOf(name)}
    </span>
  );
}
