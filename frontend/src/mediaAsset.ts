export type MediaAsset = {
  id: string;
  url: string;
  metadata: Record<string, unknown>;
};
export type MediaChange = {favorite?: boolean; trashed?: boolean};
const record = (value: unknown): Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
const text = (value: unknown) => (typeof value === 'string' ? value : '');

export function mediaPrompt(metadata: Record<string, unknown>): string {
  const request = record(metadata.request),
    payload = record(request.payload);
  return (
    text(metadata.prompt) ||
    text(request.prompt) ||
    text(record(payload.input).prompt) ||
    text(payload.prompt) ||
    text(record(request.input).prompt)
  );
}
export function mediaModel(metadata: Record<string, unknown>): string {
  const request = record(metadata.request),
    payload = record(request.payload);
  return (
    text(metadata.requested_model) ||
    text(metadata.model) ||
    text(request.model_id) ||
    text(request.model) ||
    text(payload.task_type) ||
    text(payload.model) ||
    text(metadata.provider)
  );
}
export function sourceChat(metadata: Record<string, unknown>): string | null {
  const thread = text(metadata.thread_id);
  if (metadata.provider === 'codex_chat' && /^[a-zA-Z0-9_-]{16,100}$/.test(thread))
    return 'codex://threads/' + thread;
  try {
    const url = new URL(text(metadata.chat_url));
    if (
      url.protocol === 'https:' &&
      !url.username &&
      !url.password &&
      ['chatgpt.com', 'www.chatgpt.com', 'chat.openai.com'].includes(url.hostname)
    )
      return url.href;
  } catch {
    /* No verified source chat is available. */
  }
  return null;
}
export function assetIdFromUrl(url: string): string | undefined {
  return /^\/api\/library\/([a-zA-Z0-9_-]+)\/(?:file|thumbnail)(?:\?|$)/.exec(url)?.[1];
}
export function withoutMediaItem<T extends {url: string; assetId?: string}>(
  view: {items: T[]; index: number},
  id: string
): {items: T[]; index: number} | null {
  const current = view.items[view.index];
  const items = view.items.filter(item => (item.assetId || assetIdFromUrl(item.url)) !== id);
  if (!items.length) return null;
  const retained = items.indexOf(current);
  return {items, index: retained >= 0 ? retained : Math.min(view.index, items.length - 1)};
}
/** Never show a fake success when the clipboard is absent or permission was denied. */
export async function copyMediaPrompt(
  prompt: string,
  clipboard?: Pick<Clipboard, 'writeText'>
): Promise<boolean> {
  if (!prompt || !clipboard) return false;
  try {
    await clipboard.writeText(prompt);
    return true;
  } catch {
    return false;
  }
}
