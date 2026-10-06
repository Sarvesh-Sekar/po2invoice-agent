import { useMemo, useState } from "react";
import { EmptyState } from "@/components/ui/EmptyState";

export interface ReviewDocumentPanelProps {
  file?: File | null;
  sourceFileUrl?: string;
}

type PreviewKind = "pdf" | "image" | "none";

function resolveSource(sourceFileUrl?: string): string | null {
  if (!sourceFileUrl) return null;
  if (/^https?:\/\//i.test(sourceFileUrl)) return sourceFileUrl;
  return null;
}

export function ReviewDocumentPanel({ file, sourceFileUrl }: ReviewDocumentPanelProps) {
  const [zoom, setZoom] = useState(1);

  const objectUrl = useMemo(() => {
    if (!file) return null;
    return URL.createObjectURL(file);
  }, [file]);

  const { kind, url } = useMemo<{ kind: PreviewKind; url: string | null }>(() => {
    if (file) {
      const type = file.type;
      if (type === "application/pdf") return { kind: "pdf", url: objectUrl };
      if (type.startsWith("image/")) return { kind: "image", url: objectUrl };
      return { kind: "none", url: objectUrl };
    }
    const remote = resolveSource(sourceFileUrl);
    if (remote) {
      if (/\.pdf($|\?)/i.test(remote)) return { kind: "pdf", url: remote };
      if (/\.(png|jpe?g|webp|gif)($|\?)/i.test(remote)) return { kind: "image", url: remote };
      return { kind: "pdf", url: remote };
    }
    return { kind: "none", url: null };
  }, [file, sourceFileUrl, objectUrl]);

  return (
    <div className="flex h-full flex-col rounded-lg border border-gray-200 bg-white">
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
        <h3 className="text-sm font-semibold text-gray-900">Original Document</h3>
        {kind !== "none" && (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setZoom((z) => Math.max(0.75, Math.round((z - 0.25) * 100) / 100))}
              className="h-7 w-7 rounded-md border border-gray-300 text-sm text-gray-600 hover:bg-gray-50"
            >
              −
            </button>
            <span className="w-10 text-center text-xs text-gray-500">{Math.round(zoom * 100)}%</span>
            <button
              type="button"
              onClick={() => setZoom((z) => Math.min(2, Math.round((z + 0.25) * 100) / 100))}
              className="h-7 w-7 rounded-md border border-gray-300 text-sm text-gray-600 hover:bg-gray-50"
            >
              +
            </button>
          </div>
        )}
      </div>
      <div className="flex-1 overflow-auto bg-gray-50 p-3">
        {kind === "pdf" && url ? (
          <iframe
            src={url}
            title="Purchase order document"
            className="h-full min-h-[480px] w-full rounded-md border border-gray-200 bg-white"
          />
        ) : kind === "image" && url ? (
          <img
            src={url}
            alt="Purchase order document"
            style={{ transform: `scale(${zoom})`, transformOrigin: "top left" }}
            className="rounded-md border border-gray-200 bg-white"
          />
        ) : (
          <EmptyState
            title="No document preview"
            description={
              sourceFileUrl
                ? "The document is stored remotely and cannot be previewed inline."
                : "The original document is not available for this workflow run."
            }
            action={
              sourceFileUrl ? (
                <a
                  href={sourceFileUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm font-medium text-indigo-600 hover:text-indigo-700"
                >
                  Open document
                </a>
              ) : undefined
            }
          />
        )}
      </div>
    </div>
  );
}